from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
from datetime import datetime
import uuid
import os
import json
import traceback

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="AutoSlideX API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-pro')

# Pydantic Models
class SlideContent(BaseModel):
    slide_number: int
    title: str
    content: List[str]
    layout_type: str = "content"
    image_query: Optional[str] = None
    notes: Optional[str] = None

class PresentationRequest(BaseModel):
    topic: str
    num_slides: int
    additional_context: Optional[str] = None

class PresentationUpdate(BaseModel):
    presentation_id: str
    slides: List[SlideContent]

class GeneratePPTRequest(BaseModel):
    presentation_id: str
    template: Optional[str] = "modern"
    export_format: str = "pptx"

# In-memory storage
presentations_db = {}


def generate_short_title(topic: str, additional_context: str = None) -> str:
    """
    Generate a concise, professional presentation title (max 8 words)
    """
    prompt = f"""
    Create a SHORT, professional presentation title for: "{topic}"
    Additional context: {additional_context or "None"}
    
    CRITICAL RULES:
    1. Maximum 8 words (prefer 3-6 words)
    2. Clear and concise
    3. Professional and engaging
    4. No unnecessary words
    5. Return ONLY the title, nothing else
    
    Examples:
    Topic: "Introduction to Soft Computing, Historical Development, Definitions, advantages and disadvantages"
    Good: "Soft Computing: Concepts and Applications"
    Bad: "Introduction to Soft Computing, Historical Development, Definitions, advantages and disadvantages"
    
    Topic: "Machine Learning basics and applications"
    Good: "Machine Learning Fundamentals"
    Bad: "Introduction to Machine Learning basics and applications in industry"
    """
    
    try:
        response = model.generate_content(prompt)
        title = response.text.strip().replace('"', '').replace("'", "")
        
        # Fallback: If still too long, truncate intelligently
        if len(title.split()) > 8:
            words = topic.split()[:5]
            title = " ".join(words)
        
        return title
        
    except Exception as e:
        print(f"✗ Error generating title: {e}")
        # Fallback: Use first 5 words of topic
        words = topic.split()[:5]
        return " ".join(words)


def generate_slide_topics(topic: str, num_slides: int, additional_context: str = None) -> List[str]:
    """
    Generate EXACTLY num_slides topics/subtopics for the presentation
    This ensures strict adherence to user-requested slide count
    """
    prompt = f"""
    For the topic: "{topic}"
    Additional context: {additional_context or "None"}
    
    Generate EXACTLY {num_slides} slide topics (subtopics) that comprehensively cover this subject.
    
    CRITICAL RULES:
    1. Return EXACTLY {num_slides} topics, no more, no less
    2. Each topic should be a clear, concise slide title (3-8 words)
    3. Topics should logically flow and cover the subject comprehensively
    4. First slide should be introduction/overview
    5. Last slide should be conclusion/summary
    6. Middle slides should cover key concepts in logical order
    
    Return ONLY a JSON array of strings:
    ["Topic 1", "Topic 2", ..., "Topic {num_slides}"]
    
    Example for "Cloud Computing" with 5 slides:
    ["Introduction to Cloud Computing", "Cloud Service Models", "Cloud Deployment Types", "Benefits and Challenges", "Future of Cloud Computing"]
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        topics = json.loads(response_text)
        
        # FORCE exact count
        if len(topics) > num_slides:
            topics = topics[:num_slides]
            print(f"⚠️ Trimmed topics to {num_slides}")
        elif len(topics) < num_slides:
            # Pad with generic topics
            while len(topics) < num_slides:
                topics.append(f"Additional Insights #{len(topics) + 1}")
            print(f"⚠️ Padded topics to {num_slides}")
        
        print(f"✓ Generated {len(topics)} topics")
        return topics
        
    except Exception as e:
        print(f"✗ Error generating topics: {e}")
        # Fallback: generate generic topics
        return [f"Topic {i+1}" for i in range(num_slides)]


def is_generic_content(content: List[str]) -> bool:
    """
    Check if slide content is generic/placeholder
    """
    generic_phrases = [
        "key concept about this topic",
        "important aspect to consider",
        "related insight or application",
        "key point",
        "additional key insight"
    ]
    
    if len(content) < 3:
        return True
    
    for point in content:
        point_lower = point.lower()
        if any(phrase in point_lower for phrase in generic_phrases):
            return True
    
    return False


def regenerate_slide_content(slide_title: str, slide_number: int, total_slides: int, 
                             main_topic: str, additional_context: str = None) -> dict:
    """
    Regenerate content for slides with generic/placeholder content
    Uses stronger prompting to ensure quality content
    """
    prompt = f"""
    Create DETAILED, PROFESSIONAL slide content for: "{main_topic}"
    
    Slide #{slide_number} of {total_slides}
    Slide Title: "{slide_title}"
    Additional Context: {additional_context or "None"}
    
    CRITICAL REQUIREMENTS:
    1. Create EXACTLY 3-4 bullet points with REAL, DETAILED information
    2. Each bullet MUST be 12-20 words with specific details
    3. NO generic phrases like "key concept", "important aspect", "consider", etc.
    4. Include specific examples, data, or technical details
    5. Make content educational and informative
    
    FORBIDDEN PHRASES (DO NOT USE):
    - "Key concept about this topic"
    - "Important aspect to consider"
    - "Related insight or application"
    - "Key point"
    - "Additional insight"
    
    REQUIRED STYLE:
    - Specific and detailed
    - Include real-world examples
    - Use technical terminology appropriately
    - Provide actionable information
    
    GOOD EXAMPLES:
    ✓ "Neural networks consist of interconnected layers of nodes that process information through weighted connections, enabling pattern recognition and complex decision-making capabilities"
    ✓ "Backpropagation algorithm adjusts weights by calculating gradients through chain rule, allowing networks to learn from errors and improve prediction accuracy over training iterations"
    ✓ "Convolutional layers extract spatial features from images using learnable filters, reducing parameters through weight sharing while maintaining translation invariance for robust visual recognition"
    
    BAD EXAMPLES (NEVER DO THIS):
    ✗ "Key concept about neural networks"
    ✗ "Important aspect to consider"
    ✗ "Neural networks are useful"
    
    Return ONLY valid JSON:
    {{
        "title": "{slide_title}",
        "content": [
            "Detailed, specific bullet point with examples (12-20 words)",
            "Another comprehensive point with technical details (12-20 words)",
            "Third informative bullet with real-world context (12-20 words)"
        ],
        "image_query": "specific technical diagram search terms",
        "notes": "Detailed speaker notes with examples and technical context"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        slide_data = json.loads(response_text)
        
        # Validate content quality
        if "content" in slide_data:
            if len(slide_data["content"]) > 4:
                slide_data["content"] = slide_data["content"][:4]
            elif len(slide_data["content"]) < 3:
                # If still insufficient, make one more attempt
                print(f"⚠️ Insufficient content generated, using fallback")
                return generate_fallback_content(slide_title, main_topic)
            
            # Clean bullets
            cleaned_content = []
            for bullet in slide_data["content"]:
                bullet = bullet.strip().lstrip("•-–— ")
                words = bullet.split()
                if len(words) > 25:
                    bullet = " ".join(words[:25])
                cleaned_content.append(bullet)
            
            slide_data["content"] = cleaned_content
        
        return slide_data
        
    except Exception as e:
        print(f"✗ Error regenerating slide content: {e}")
        return generate_fallback_content(slide_title, main_topic)


def generate_fallback_content(slide_title: str, main_topic: str) -> dict:
    """
    Generate basic fallback content when AI generation fails
    """
    return {
        "title": slide_title,
        "content": [
            f"Core concepts and fundamentals of {slide_title.lower()}",
            f"Practical applications and real-world use cases in {main_topic.lower()}",
            f"Key considerations and best practices for implementation"
        ],
        "image_query": slide_title.lower(),
        "notes": f"Detailed discussion of {slide_title} in the context of {main_topic}"
    }


def generate_slide_content(slide_title: str, slide_number: int, total_slides: int, 
                          main_topic: str, additional_context: str = None) -> dict:
    """
    Generate content for a SINGLE slide with PROFESSIONAL DEPTH
    Creates detailed, informative content suitable for technical/academic presentations
    """
    prompt = f"""
    Create PROFESSIONAL slide content for a presentation about: "{main_topic}"
    
    Slide #{slide_number} of {total_slides}
    Slide Title: "{slide_title}"
    Additional Context: {additional_context or "None"}
    
    CRITICAL INSTRUCTIONS - PROFESSIONAL DEPTH:
    1. Create EXACTLY 3-4 bullet points (3 for simple topics, 4 for complex ones)
    2. Each bullet should be 10-20 WORDS - provide real explanations
    3. Include specific details, examples, and context
    4. Use technical terminology appropriately
    5. Make content informative and educational
    
    EXCELLENT PROFESSIONAL EXAMPLES (detailed explanations):
    ✓ "Infrastructure as a Service (IaaS): Provides virtualized computing resources like servers, storage, and networking over the internet with pay-as-you-go pricing"
    ✓ "Platform as a Service (PaaS): Offers complete development and deployment environment where developers can build applications without managing underlying infrastructure"
    ✓ "Software as a Service (SaaS): Delivers fully functional applications over the internet, accessible through web browsers without local installation or maintenance"
    ✓ "Examples include AWS EC2 for IaaS, Google App Engine for PaaS, and Microsoft 365 for SaaS offerings"
    
    BAD EXAMPLES (too brief - NEVER do this):
    ✗ "Cloud is scalable" (lacks detail)
    ✗ "Pay-per-use pricing" (needs explanation)
    ✗ "IaaS provides infrastructure" (too obvious)
    
    IMAGE QUERY INSTRUCTIONS:
    - For service models (IaaS/PaaS/SaaS): Use "IaaS PaaS SaaS comparison diagram illustration"
    - For architectures: Use "cloud architecture layers diagram illustration"
    - For security: Use "cloud security diagram illustration"
    - For storage: Use "cloud storage types diagram illustration"
    - For deployment: Use "cloud deployment models diagram illustration"
    - For technical concepts: Use "[concept name] diagram illustration technical"
    - ALWAYS add "diagram illustration" for technical topics to get proper diagrams
    
    SPEAKER NOTES:
    - Provide 3-5 sentences with deeper explanation
    - Include real-world examples, use cases, or scenarios
    - Add technical details that support the bullet points
    - Mention specific tools, platforms, or technologies where relevant
    
    Return ONLY valid JSON (no markdown):
    {{
        "title": "{slide_title}",
        "content": [
            "Detailed bullet point with explanation (10-20 words)",
            "Another comprehensive point with specifics (10-20 words)",
            "Third informative bullet with context (10-20 words)",
            "Optional fourth point for complex topics (10-20 words)"
        ],
        "image_query": "specific technical diagram search terms",
        "notes": "Comprehensive speaker notes with examples and technical details"
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Clean up response
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        slide_data = json.loads(response_text)
        
        # Validate and clean content
        if "content" in slide_data:
            # Allow 3-4 bullets for professional depth
            if len(slide_data["content"]) > 4:
                slide_data["content"] = slide_data["content"][:4]
            elif len(slide_data["content"]) < 3:
                while len(slide_data["content"]) < 3:
                    slide_data["content"].append("Additional key insight to explore further")
            
            # Trim overly long bullets (max 25 words for professional content)
            cleaned_content = []
            for bullet in slide_data["content"]:
                bullet = bullet.strip().lstrip("•-–— ")
                words = bullet.split()
                if len(words) > 25:
                    bullet = " ".join(words[:25])
                cleaned_content.append(bullet)
            
            slide_data["content"] = cleaned_content
        
        return slide_data
        
    except Exception as e:
        print(f"✗ Error generating slide content: {e}")
        # Fallback content
        return {
            "title": slide_title,
            "content": [
                "Key concept about this topic",
                "Important aspect to consider",
                "Related insight or application"
            ],
            "image_query": slide_title.lower(),
            "notes": f"Discussion points for {slide_title}"
        }


@app.get("/")
async def root():
    return {
        "message": "AutoSlideX API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": ["/api/generate-outline", "/api/update-slides", "/api/generate-ppt"]
    }


# ✅ FIX: Add HEAD endpoint for health checks
@app.head("/")
async def root_head():
    return {}


@app.post("/api/generate-outline")
async def generate_outline(request: PresentationRequest):
    """Generate presentation outline using Gemini Pro - STRICTLY follows slide count"""
    try:
        print(f"\n{'='*60}")
        print(f"📊 Generating outline for: {request.topic}")
        print(f"📝 Requested slides: {request.num_slides}")
        print(f"{'='*60}\n")
        
        # Step 0: Generate short title
        print(f"📌 Step 0/3: Generating concise title...")
        short_title = generate_short_title(request.topic, request.additional_context)
        print(f"   Title: {short_title}")
        
        # Step 1: Generate EXACT number of slide topics
        print(f"\n🎯 Step 1/3: Generating {request.num_slides} slide topics...")
        slide_topics = generate_slide_topics(
            request.topic, 
            request.num_slides, 
            request.additional_context
        )
        
        # Step 2: Generate content for each slide
        print(f"\n📝 Step 2/3: Generating detailed content for each slide...")
        slides = []
        
        for idx, slide_title in enumerate(slide_topics, 1):
            print(f"   Processing slide {idx}/{len(slide_topics)}: {slide_title}")
            
            slide_content = generate_slide_content(
                slide_title=slide_title,
                slide_number=idx,
                total_slides=len(slide_topics),
                main_topic=request.topic,
                additional_context=request.additional_context
            )
            
            slides.append({
                "slide_number": idx,
                "title": slide_content.get("title", slide_title),
                "content": slide_content.get("content", []),
                "layout_type": "content",
                "image_query": slide_content.get("image_query", ""),
                "notes": slide_content.get("notes", "")
            })
        
        # Step 3: Quality check and regenerate generic content
        print(f"\n🔍 Step 3/3: Quality check - detecting generic content...")
        regenerated_count = 0
        for idx, slide in enumerate(slides):
            if is_generic_content(slide["content"]):
                print(f"   ⚠️ Slide {idx + 1} has generic content, regenerating...")
                improved_content = regenerate_slide_content(
                    slide_title=slide["title"],
                    slide_number=idx + 1,
                    total_slides=len(slides),
                    main_topic=request.topic,
                    additional_context=request.additional_context
                )
                slides[idx].update(improved_content)
                regenerated_count += 1
        
        if regenerated_count > 0:
            print(f"   ✓ Regenerated {regenerated_count} slides with better content")
        else:
            print(f"   ✓ All slides have quality content")
        
        # Verify exact count
        if len(slides) != request.num_slides:
            print(f"⚠️ WARNING: Generated {len(slides)} slides, expected {request.num_slides}")
            # Force correction
            if len(slides) > request.num_slides:
                slides = slides[:request.num_slides]
            elif len(slides) < request.num_slides:
                while len(slides) < request.num_slides:
                    slides.append({
                        "slide_number": len(slides) + 1,
                        "title": f"Additional Topic {len(slides) + 1}",
                        "content": ["Key point one", "Key point two", "Key point three"],
                        "layout_type": "content",
                        "image_query": request.topic.lower(),
                        "notes": ""
                    })
        
        print(f"\n✅ Successfully generated {len(slides)} slides with quality content\n")
        
        # Generate unique presentation ID
        presentation_id = str(uuid.uuid4())
        
        # Store in database
        presentations_db[presentation_id] = {
            "id": presentation_id,
            "topic": request.topic,
            "title": short_title,  # Use short title
            "num_slides": len(slides),
            "slides": slides,
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "data": presentations_db[presentation_id]
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to parse AI response. Please try again. Error: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Error generating outline: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating outline: {str(e)}"
        )


@app.put("/api/update-slides")
async def update_slides(request: PresentationUpdate):
    """Update slide content before generating PPT"""
    try:
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        # Convert slides to dict and renumber them sequentially
        updated_slides = []
        for idx, slide in enumerate(request.slides, 1):
            slide_dict = slide.dict()
            slide_dict["slide_number"] = idx  # Renumber sequentially
            updated_slides.append(slide_dict)
        
        # Update slides
        presentations_db[request.presentation_id]["slides"] = updated_slides
        presentations_db[request.presentation_id]["updated_at"] = datetime.now().isoformat()
        presentations_db[request.presentation_id]["status"] = "updated"
        presentations_db[request.presentation_id]["num_slides"] = len(updated_slides)
        
        print(f"✓ Updated presentation {request.presentation_id}")
        print(f"  Total slides: {len(updated_slides)}")
        
        return {
            "success": True,
            "message": "Slides updated successfully",
            "data": presentations_db[request.presentation_id]
        }
        
    except Exception as e:
        print(f"❌ Error updating slides: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error updating slides: {str(e)}")


@app.get("/api/presentation/{presentation_id}")
async def get_presentation(presentation_id: str):
    """Retrieve presentation data"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    return {
        "success": True,
        "data": presentations_db[presentation_id]
    }


@app.post("/api/generate-ppt")
async def generate_ppt(request: GeneratePPTRequest):
    """Generate final PowerPoint file"""
    try:
        print(f"\n{'='*60}")
        print(f"🎨 Starting PPT generation...")
        print(f"   Presentation ID: {request.presentation_id}")
        print(f"{'='*60}\n")
        
        if request.presentation_id not in presentations_db:
            print(f"❌ Presentation not found: {request.presentation_id}")
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        presentation_data = presentations_db[request.presentation_id]
        
        print(f"✓ Found presentation: {presentation_data['title']}")
        print(f"   Total slides: {len(presentation_data['slides'])}")
        
        # Import pptx_generator module
        print(f"\n📦 Importing pptx_generator...")
        try:
            from pptx_generator import create_presentation
            print(f"✓ pptx_generator imported successfully")
        except ImportError as ie:
            print(f"❌ Failed to import pptx_generator: {ie}")
            print(traceback.format_exc())
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to import pptx_generator module: {str(ie)}"
            )
        
        # Generate PPTX file
        output_dir = "generated_presentations"
        print(f"\n📁 Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{request.presentation_id}.pptx"
        filepath = os.path.join(output_dir, filename)
        print(f"   Output path: {filepath}")
        
        print(f"\n🎨 Generating PowerPoint presentation...")
        try:
            create_presentation(
                presentation_data,
                filepath,
                template=request.template
            )
            print(f"✓ Presentation generated successfully")
        except Exception as pptx_error:
            print(f"❌ Error in create_presentation: {pptx_error}")
            print(traceback.format_exc())
            raise
        
        # Verify file was created
        if not os.path.exists(filepath):
            print(f"❌ File was not created: {filepath}")
            raise HTTPException(
                status_code=500,
                detail="Presentation file was not created"
            )
        
        file_size = os.path.getsize(filepath)
        print(f"✓ File created successfully")
        print(f"   Size: {file_size} bytes")
        
        # Update database
        presentations_db[request.presentation_id]["pptx_url"] = filepath
        presentations_db[request.presentation_id]["status"] = "completed"
        
        print(f"\n{'='*60}")
        print(f"✅ PPT Generation Complete!")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "Presentation generated successfully",
            "download_url": f"/api/download/{request.presentation_id}",
            "file_path": filepath
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error in generate_ppt: {e}")
        print(f"Error type: {type(e).__name__}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating PPT: {str(e)}"
        )


@app.get("/api/download/{presentation_id}")
async def download_presentation(presentation_id: str):
    """Download generated presentation"""
    try:
        if presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        presentation = presentations_db[presentation_id]
        
        if "pptx_url" not in presentation:
            raise HTTPException(status_code=400, detail="Presentation not yet generated")
        
        filepath = presentation["pptx_url"]
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail="File not found")
        
        print(f"📥 Downloading: {filepath}")
        
        return FileResponse(
            filepath,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=f"{presentation['title']}.pptx"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in download: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error downloading: {str(e)}")


@app.delete("/api/presentation/{presentation_id}")
async def delete_presentation(presentation_id: str):
    """Delete presentation and associated files"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    presentation = presentations_db[presentation_id]
    
    # Delete file if exists
    if "pptx_url" in presentation and os.path.exists(presentation["pptx_url"]):
        os.remove(presentation["pptx_url"])
    
    # Remove from database
    del presentations_db[presentation_id]
    
    return {
        "success": True,
        "message": "Presentation deleted successfully"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "presentations_count": len(presentations_db)
    }


if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print(f"🚀 Starting AutoSlideX API Server")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)