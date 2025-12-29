from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
from datetime import datetime
import uuid
import os
import json
import re
import time

load_dotenv()

app = FastAPI(title="AutoSlideX API - Two Stage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)

MODEL_FALLBACKS = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-3-flash"
]

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

presentations_db = {}


def preprocess_topic(topic: str) -> str:
    """Clean up long course descriptions"""
    topic = re.sub(r'\bUNIT[-–]?[IVX\d]+\b', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'\b\d+\s*HOURS?\b', '', topic, flags=re.IGNORECASE)
    
    if ':' in topic:
        parts = topic.split(':')
        for part in parts:
            if 'introduction to' in part.lower():
                topic = part
                break
        else:
            topic = parts[0]
    
    topic = ' '.join(topic.split())
    words = topic.split()
    if len(words) > 15:
        for i, word in enumerate(words[:15]):
            if word.endswith((',', '.', ';')):
                topic = ' '.join(words[:i+1]).rstrip('.,;')
                break
        else:
            topic = ' '.join(words[:12])
    
    return topic.strip()


def call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini API with model fallback"""
    for model_name in MODEL_FALLBACKS:
        for attempt in range(max_retries):
            try:
                print(f"   🤖 Trying: {model_name} (attempt {attempt + 1})")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                print(f"   ✓ Success with {model_name}")
                return response.text.strip()
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'quota' in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = 5 * (2 ** attempt)
                        print(f"   ⏳ Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"   ❌ {model_name} failed, trying next...")
                        break
                else:
                    print(f"   ⚠️ Error: {error_msg[:100]}")
                    break
    
    raise Exception("All models failed")


def generate_short_title(topic: str) -> str:
    """Generate short title (3-6 words)"""
    clean_topic = preprocess_topic(topic)
    
    prompt = f"""
    Create a SHORT presentation title for: "{clean_topic}"
    
    Rules:
    - Maximum 6 words
    - No colons
    - Professional
    - Return ONLY the title
    
    Example: "Machine Learning Fundamentals"
    """
    
    try:
        title = call_gemini_with_retry(prompt)
        title = title.replace('"', '').replace("'", "")
        words = title.split()
        if len(words) > 6:
            title = " ".join(words[:5])
        return title
    except:
        words = clean_topic.split()[:4]
        return " ".join(words)


def generate_slide_headings_only(topic: str, num_slides: int) -> List[dict]:
    """
    STAGE 1: Generate ONLY slide titles (no content)
    Returns headings for preview
    """
    clean_topic = preprocess_topic(topic)
    
    prompt = f"""
    Create {num_slides} slide TITLES ONLY for: "{clean_topic}"
    
    Requirements:
    1. EXACTLY {num_slides} titles
    2. Each title: 3-7 words
    3. Progressive flow: Intro → Core topics → Conclusion
    4. Include image query for each
    
    Return JSON:
    {{
      "slides": [
        {{
          "title": "Short Title",
          "image_query": "specific diagram query"
        }}
      ]
    }}
    """
    
    try:
        response_text = call_gemini_with_retry(prompt)
        
        # Clean JSON
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        data = json.loads(response_text.strip())
        slides = data.get("slides", [])
        
        # Ensure exact count
        if len(slides) > num_slides:
            slides = slides[:num_slides]
        elif len(slides) < num_slides:
            while len(slides) < num_slides:
                slides.append({
                    "title": f"{clean_topic} Topic {len(slides) + 1}",
                    "image_query": f"{clean_topic} diagram"
                })
        
        # Format for preview (NO CONTENT YET)
        formatted = []
        for idx, slide in enumerate(slides, 1):
            formatted.append({
                "slide_number": idx,
                "title": slide.get("title", f"Slide {idx}"),
                "content": [],  # Empty - content generated later
                "layout_type": "content",
                "image_query": slide.get("image_query", f"{clean_topic} diagram"),
                "notes": ""
            })
        
        print(f"✓ Generated {len(formatted)} headings (NO CONTENT)")
        return formatted
        
    except Exception as e:
        print(f"✗ Error: {e}")
        # Fallback
        fallback = []
        for i in range(num_slides):
            fallback.append({
                "slide_number": i + 1,
                "title": f"{clean_topic} - Topic {i + 1}",
                "content": [],
                "layout_type": "content",
                "image_query": f"{clean_topic} diagram",
                "notes": ""
            })
        return fallback


def generate_detailed_slide_content(slide_title: str, slide_number: int, 
                                   total_slides: int, main_topic: str) -> dict:
    """
    STAGE 2: Generate detailed content for ONE slide
    Called during PPT generation
    """
    clean_topic = preprocess_topic(main_topic)
    
    prompt = f"""
    Create detailed content for slide: "{slide_title}"
    
    Topic: {clean_topic}
    Slide {slide_number} of {total_slides}
    
    Requirements:
    1. EXACTLY 3-4 bullet points
    2. Each: 15-25 words with SPECIFIC details
    3. Technical terminology and examples
    4. NO generic phrases
    
    Return JSON:
    {{
        "content": [
            "Detailed technical point (15-25 words)",
            "Another specific point (15-25 words)",
            "Third unique insight (15-25 words)"
        ],
        "notes": "Speaker notes"
    }}
    """
    
    try:
        response_text = call_gemini_with_retry(prompt)
        
        # Clean JSON
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        data = json.loads(response_text.strip())
        content = data.get("content", [])
        
        # Ensure 3-4 points
        if len(content) > 4:
            content = content[:4]
        elif len(content) < 3:
            while len(content) < 3:
                content.append(f"Technical details about {slide_title}")
        
        # Clean bullets
        cleaned = []
        for bullet in content:
            bullet = bullet.strip().lstrip("•-–— ")
            words = bullet.split()
            if len(words) > 30:
                bullet = " ".join(words[:30])
            cleaned.append(bullet)
        
        return {
            "content": cleaned,
            "notes": data.get("notes", f"Details about {slide_title}")
        }
        
    except Exception as e:
        print(f"✗ Content gen error: {e}")
        return {
            "content": [
                f"Overview of {slide_title} including technical concepts",
                f"Key methodologies and approaches in {slide_title}",
                f"Applications and implementations of {slide_title}"
            ],
            "notes": f"Technical discussion of {slide_title}"
        }


@app.post("/api/generate-outline")
async def generate_outline(request: PresentationRequest):
    """
    STAGE 1: Generate outline with titles ONLY (no content)
    """
    try:
        clean_topic = preprocess_topic(request.topic)
        
        print(f"\n{'='*60}")
        print(f"📊 STAGE 1: Generating Outline")
        print(f"✨ Topic: {clean_topic}")
        print(f"📝 Slides: {request.num_slides}")
        print(f"{'='*60}\n")
        
        # Generate title
        print("📌 Generating title...")
        short_title = generate_short_title(request.topic)
        print(f"   Title: {short_title}")
        
        # Generate headings ONLY
        print(f"\n🎯 Generating {request.num_slides} slide headings...")
        slides = generate_slide_headings_only(request.topic, request.num_slides)
        
        print(f"\n✅ Preview ready: {len(slides)} headings (content will be generated on PPT creation)")
        
        presentation_id = str(uuid.uuid4())
        
        presentations_db[presentation_id] = {
            "id": presentation_id,
            "topic": request.topic,
            "title": short_title,
            "num_slides": len(slides),
            "slides": slides,
            "status": "draft",
            "content_generated": False,  # Flag
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "presentation_id": presentation_id,
            "data": presentations_db[presentation_id]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/update-slides")
async def update_slides(request: PresentationUpdate):
    """Update slide titles (user customization)"""
    try:
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Not found")
        
        updated_slides = []
        for idx, slide in enumerate(request.slides, 1):
            slide_dict = slide.dict()
            slide_dict["slide_number"] = idx
            updated_slides.append(slide_dict)
        
        presentations_db[request.presentation_id]["slides"] = updated_slides
        presentations_db[request.presentation_id]["updated_at"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "data": presentations_db[request.presentation_id]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/presentation/{presentation_id}")
async def get_presentation(presentation_id: str):
    """Get presentation"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True, "data": presentations_db[presentation_id]}


@app.post("/api/generate-ppt")
async def generate_ppt(request: GeneratePPTRequest):
    """
    STAGE 2: Generate detailed content and create PPT
    """
    try:
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Not found")
        
        presentation_data = presentations_db[request.presentation_id]
        
        print(f"\n{'='*60}")
        print(f"🎨 STAGE 2: Generating Detailed Content")
        print(f"   Title: {presentation_data['title']}")
        print(f"   Slides: {len(presentation_data['slides'])}")
        print(f"{'='*60}\n")
        
        # Generate content for each slide
        updated_slides = []
        for idx, slide in enumerate(presentation_data["slides"], 1):
            print(f"📝 Slide {idx}: {slide['title']}")
            
            # Generate detailed content NOW
            detailed = generate_detailed_slide_content(
                slide_title=slide["title"],
                slide_number=idx,
                total_slides=len(presentation_data["slides"]),
                main_topic=presentation_data["topic"]
            )
            
            # Update with content
            slide["content"] = detailed["content"]
            slide["notes"] = detailed.get("notes", "")
            updated_slides.append(slide)
            
            print(f"   ✓ Generated {len(detailed['content'])} points")
        
        # Update database
        presentation_data["slides"] = updated_slides
        presentation_data["content_generated"] = True
        
        print(f"\n🎨 Creating PowerPoint...")
        
        from pptx_generator import create_presentation
        
        output_dir = "generated_presentations"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{request.presentation_id}.pptx"
        filepath = os.path.join(output_dir, filename)
        
        create_presentation(presentation_data, filepath, request.template)
        
        presentations_db[request.presentation_id]["pptx_url"] = filepath
        presentations_db[request.presentation_id]["status"] = "completed"
        presentations_db[request.presentation_id]["slides"] = updated_slides
        
        print(f"\n✅ PowerPoint created!")
        
        return {
            "success": True,
            "download_url": f"/api/download/{request.presentation_id}",
            "file_path": filepath
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{presentation_id}")
async def download_presentation(presentation_id: str):
    """Download PPT"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Not found")
    
    presentation = presentations_db[presentation_id]
    
    if "pptx_url" not in presentation:
        raise HTTPException(status_code=400, detail="Not generated")
    
    filepath = presentation["pptx_url"]
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{presentation['title']}.pptx"
    )


@app.get("/")
async def root():
    return {
        "message": "AutoSlideX API - Two Stage Generation",
        "version": "5.0.0",
        "workflow": [
            "Stage 1: Generate slide titles only (preview)",
            "User: Add/edit/delete slides",
            "Stage 2: Generate detailed content when creating PPT"
        ],
        "models": MODEL_FALLBACKS
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "presentations": len(presentations_db),
        "version": "5.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)