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
import re
import time

load_dotenv()

app = FastAPI(title="AutoSlideX API - Fixed")

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
model = genai.GenerativeModel('models/gemini-2.0-flash-lite')

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
    """
    Clean up long course descriptions to extract main topic
    Handles inputs like "UNIT-I 10 HOURS Introduction to IoT:Architectural..."
    """
    # Remove unit markers and hours
    topic = re.sub(r'\bUNIT[-–]?[IVX\d]+\b', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'\b\d+\s*HOURS?\b', '', topic, flags=re.IGNORECASE)
    
    # Split on colons and take first meaningful part
    if ':' in topic:
        parts = topic.split(':')
        # Take introduction part if it exists
        for part in parts:
            if 'introduction to' in part.lower():
                topic = part
                break
        else:
            topic = parts[0]
    
    # Clean up whitespace
    topic = ' '.join(topic.split())
    
    # If still too long (>15 words), take first sentence or phrase
    words = topic.split()
    if len(words) > 15:
        # Try to find natural break points
        for i, word in enumerate(words[:15]):
            if word.endswith((',', '.', ';')):
                topic = ' '.join(words[:i+1]).rstrip('.,;')
                break
        else:
            topic = ' '.join(words[:12])
    
    return topic.strip()


def call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    """
    Call Gemini API with exponential backoff for rate limits
    """
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limit error
            if '429' in error_msg or 'quota' in error_msg.lower():
                if attempt < max_retries - 1:
                    # Extract retry delay if available
                    retry_match = re.search(r'retry in (\d+\.?\d*)', error_msg)
                    if retry_match:
                        wait_time = float(retry_match.group(1)) + 1
                    else:
                        # Exponential backoff: 5s, 10s, 20s
                        wait_time = 5 * (2 ** attempt)
                    
                    print(f"   ⏳ Rate limit hit, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"   ❌ Rate limit exceeded after {max_retries} attempts")
                    raise
            else:
                # Other error, don't retry
                raise
    
    raise Exception("Failed after all retries")


def generate_short_title(topic: str, additional_context: str = None) -> str:
    """Generate concise presentation title (3-6 words max)"""
    # Preprocess topic first
    clean_topic = preprocess_topic(topic)
    
    prompt = f"""
    Create a SHORT, professional presentation title for: "{clean_topic}"
    
    STRICT RULES:
    1. Maximum 6 words (prefer 3-5 words)
    2. No colons, no subtitles
    3. Clear and professional
    4. Return ONLY the title
    
    Examples:
    Topic: "Introduction to Soft Computing"
    Output: "Soft Computing Fundamentals"
    
    Topic: "Introduction to IoT Architectural Overview"
    Output: "IoT Architecture Overview"
    """
    
    try:
        title = call_gemini_with_retry(prompt)
        title = title.replace('"', '').replace("'", "")
        
        # Force short title
        words = title.split()
        if len(words) > 6:
            title = " ".join(words[:5])
        
        return title
        
    except Exception as e:
        print(f"✗ Title generation error: {e}")
        # Smart fallback based on cleaned topic
        words = clean_topic.split()[:4]
        return " ".join(words)


def generate_slide_topics(topic: str, num_slides: int, additional_context: str = None) -> List[str]:
    """Generate EXACTLY num_slides topics with balanced coverage"""
    clean_topic = preprocess_topic(topic)
    
    prompt = f"""
    Create {num_slides} slide topics for: "{clean_topic}"
    
    REQUIREMENTS:
    1. EXACTLY {num_slides} topics
    2. Each topic must be 3-7 words (SHORT and CLEAR)
    3. Cover all aspects of the main topic equally
    4. Progressive flow from basics to advanced
    
    STRUCTURE:
    - Slide 1: Introduction/Overview
    - Slides 2 to {num_slides-1}: Core concepts (balanced)
    - Slide {num_slides}: Conclusion/Applications
    
    Return ONLY valid JSON:
    {{
      "topics": [
        "Topic 1 (3-7 words)",
        "Topic 2 (3-7 words)",
        ...
      ]
    }}
    """
    
    try:
        response_text = call_gemini_with_retry(prompt)
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        data = json.loads(response_text)
        topics = data.get("topics", [])
        
        # Enforce exact count
        if len(topics) > num_slides:
            topics = topics[:num_slides]
        elif len(topics) < num_slides:
            base = clean_topic.split()[0] if clean_topic else "Topic"
            while len(topics) < num_slides:
                topics.append(f"{base} Concepts {len(topics) + 1}")
        
        # Shorten any long titles
        topics = [" ".join(t.split()[:7]) for t in topics]
        
        print(f"✓ Generated {len(topics)} topics")
        return topics
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return generate_fallback_topics(clean_topic, num_slides)


def generate_fallback_topics(topic: str, num_slides: int) -> List[str]:
    """Generate fallback topics"""
    topics = [f"Introduction to {topic}"]
    
    if num_slides >= 2:
        topics.append("Core Concepts")
    if num_slides >= 3:
        topics.append("Key Principles")
    if num_slides >= 4:
        topics.append("Applications")
    if num_slides >= 5:
        topics.append("Implementation Details")
    
    while len(topics) < num_slides - 1:
        topics.append(f"Advanced Topic {len(topics)}")
    
    if num_slides > 1:
        topics.append("Summary and Conclusion")
    
    return topics[:num_slides]


def generate_fallback_content_with_unique_query(slide_title: str, slide_number: int, main_topic: str) -> dict:
    """
    Generate fallback content with UNIQUE image query per slide
    """
    clean_topic = preprocess_topic(main_topic)
    
    # Generate unique image queries based on slide number and content
    image_queries = {
        1: f"{clean_topic} overview diagram illustration",
        2: f"{clean_topic} architecture layers diagram",
        3: f"{clean_topic} components system diagram",
        4: f"{clean_topic} application examples diagram",
        5: f"{clean_topic} implementation architecture",
    }
    
    # Get unique query or generate one
    image_query = image_queries.get(
        slide_number,
        f"{slide_title} {clean_topic} technical diagram"
    )
    
    print(f"   🎨 Fallback image query: {image_query}")
    
    return {
        "title": slide_title,
        "content": [
            f"Comprehensive overview of {slide_title.lower()} including key technical concepts, definitions, and fundamental principles",
            f"Detailed exploration of methodologies, techniques, and approaches used in {slide_title.lower()} with specific examples",
            f"Real-world applications, practical implementations, and industry best practices for {slide_title.lower()}"
        ],
        "image_query": image_query,
        "notes": f"Detailed technical discussion of {slide_title} in the context of {clean_topic}"
    }


def is_generic_content(content: List[str]) -> bool:
    """Check if content is generic"""
    if not content or len(content) < 3:
        return True
    
    forbidden = [
        "key concept about", "important aspect", "related insight",
        "additional key insight", "core concepts and fundamentals",
        "practical applications and real-world use cases",
        "key considerations and best practices"
    ]
    
    for point in content:
        point_lower = point.lower()
        for phrase in forbidden:
            if phrase in point_lower:
                return True
        if len(point.split()) < 8:
            return True
    
    return False


def generate_smart_image_query(slide_title: str, content: List[str], main_topic: str) -> str:
    """
    Generate HIGHLY SPECIFIC image query based on content analysis
    Prioritizes diagrams, architectures, and technical illustrations
    """
    clean_topic = preprocess_topic(main_topic)
    full_text = f"{slide_title} {' '.join(content)} {clean_topic}".lower()
    
    # Priority 1: Specific diagram patterns
    diagram_patterns = {
        r'\b(iot\s+architecture|iot\s+layers)\b': 'IoT architecture layers diagram illustration',
        r'\b(iot\s+system\s+architecture)\b': 'IoT system architecture diagram components',
        r'\b(iot\s+protocol\s+stack)\b': 'IoT protocol stack layers diagram',
        r'\b(iot\s+gateway\s+architecture)\b': 'IoT gateway architecture diagram',
        r'\b(mqtt\s+architecture|mqtt\s+protocol)\b': 'MQTT protocol architecture diagram',
        r'\b(coap\s+architecture|coap\s+protocol)\b': 'CoAP protocol architecture diagram',
        r'\b(sensor\s+network\s+architecture)\b': 'wireless sensor network architecture diagram',
        r'\b(m2m\s+architecture|machine\s+to\s+machine)\b': 'M2M architecture diagram communication',
        r'\b(cloud\s+iot\s+architecture)\b': 'cloud IoT architecture diagram',
        r'\b(edge\s+computing\s+architecture)\b': 'edge computing architecture diagram',
        r'\b(smart\s+home\s+architecture)\b': 'smart home IoT architecture diagram',
        r'\b(industrial\s+iot|iiot)\b': 'industrial IoT architecture diagram',
        
        # UML Diagrams
        r'\b(class\s+diagram)\b': 'UML class diagram software engineering',
        r'\b(sequence\s+diagram)\b': 'UML sequence diagram interaction',
        r'\b(use\s+case\s+diagram)\b': 'UML use case diagram',
        r'\b(activity\s+diagram)\b': 'UML activity diagram workflow',
        r'\b(state\s+diagram)\b': 'state machine diagram',
        
        # OS Architecture
        r'\b(os\s+architecture|operating\s+system\s+architecture)\b': 'operating system architecture layers diagram',
        r'\b(layered\s+architecture.*os)\b': 'operating system layered architecture diagram',
        r'\b(kernel\s+architecture)\b': 'kernel architecture layers diagram',
        r'\b(monolithic\s+kernel)\b': 'monolithic kernel architecture diagram',
        r'\b(microkernel)\b': 'microkernel architecture diagram',
        r'\b(hybrid\s+kernel)\b': 'hybrid kernel architecture diagram',
        
        # Network Architecture
        r'\b(network\s+architecture)\b': 'network architecture topology diagram',
        r'\b(tcp/ip\s+model)\b': 'TCP IP protocol stack layers diagram',
        r'\b(osi\s+model)\b': 'OSI model 7 layers diagram',
        
        # Database
        r'\b(er\s+diagram|entity\s+relationship)\b': 'ER diagram database schema',
        r'\b(database\s+architecture)\b': 'database architecture diagram',
        
        # Software Architecture
        r'\b(microservices\s+architecture)\b': 'microservices architecture diagram',
        r'\b(mvc\s+architecture|model\s+view\s+controller)\b': 'MVC architecture diagram',
        r'\b(three\s+tier|3\s+tier)\b': 'three tier architecture diagram',
        r'\b(client\s+server)\b': 'client server architecture diagram',
        
        # Process Diagrams
        r'\b(flowchart)\b': 'flowchart diagram process flow',
        r'\b(data\s+flow\s+diagram|dfd)\b': 'data flow diagram DFD',
        r'\b(workflow)\b': 'workflow process diagram',
    }
    
    for pattern, query in diagram_patterns.items():
        if re.search(pattern, full_text):
            print(f"   🎯 Detected diagram: {query}")
            return query
    
    # Priority 2: IoT-specific concepts
    iot_patterns = {
        r'\b(sensing|sensors|actuators)\b': 'IoT sensors actuators devices diagram',
        r'\b(rfid|nfc)\b': 'RFID NFC technology diagram',
        r'\b(zigbee|bluetooth|wifi)\b': 'wireless communication protocols diagram',
        r'\b(smart\s+city)\b': 'smart city IoT infrastructure diagram',
        r'\b(wearable|wearables)\b': 'wearable IoT devices technology',
        r'\b(industrial\s+automation)\b': 'industrial automation IoT diagram',
    }
    
    for pattern, query in iot_patterns.items():
        if re.search(pattern, full_text):
            print(f"   🎯 IoT concept: {query}")
            return query
    
    # Priority 3: General technical topics
    if 'architecture' in full_text:
        return f"{slide_title} architecture diagram"
    if 'protocol' in full_text:
        return f"{slide_title} protocol diagram"
    if 'model' in full_text:
        return f"{slide_title} model diagram"
    if 'structure' in full_text:
        return f"{slide_title} structure diagram"
    if 'layer' in full_text:
        return f"{slide_title} layers diagram"
    
    # Fallback: use slide title + technical context
    query = f"{slide_title} {clean_topic} diagram illustration"
    print(f"   📝 Using: {query}")
    return query


def generate_slide_content_v3(slide_title: str, slide_number: int, total_slides: int,
                              main_topic: str, previous_slides: List[dict] = None,
                              additional_context: str = None) -> dict:
    """Enhanced content generation with better image queries and rate limit handling"""
    
    clean_topic = preprocess_topic(main_topic)
    
    previous_content_summary = ""
    if previous_slides and len(previous_slides) > 0:
        forbidden_content = []
        for prev_slide in previous_slides:
            for point in prev_slide.get("content", []):
                if len(point.split()) >= 5:
                    forbidden_content.append(point[:80])
        
        if forbidden_content:
            previous_content_summary = f"""
FORBIDDEN CONTENT (already used):
{chr(10).join(f"❌ {content}" for content in forbidden_content[-6:])}

Create COMPLETELY NEW content with DIFFERENT vocabulary and concepts.
"""
    
    prompt = f"""
    Create UNIQUE slide content for: "{clean_topic}"
    
    Slide #{slide_number} of {total_slides}: "{slide_title}"
    
    {previous_content_summary}
    
    STRICT REQUIREMENTS:
    1. Create EXACTLY 3-4 bullet points
    2. Each bullet: 15-25 words with SPECIFIC details
    3. Use technical terminology and concrete examples
    4. NO generic phrases
    5. Focus specifically on "{slide_title}"
    
    RESPONSE FORMAT (JSON only):
    {{
        "title": "{slide_title}",
        "content": [
            "Specific technical bullet (15-25 words)",
            "Another unique point (15-25 words)",
            "Third distinct insight (15-25 words)"
        ],
        "image_query": "specific diagram type",
        "notes": "Technical context"
    }}
    """
    
    max_attempts = 2  # Reduced to save API calls
    for attempt in range(max_attempts):
        try:
            response_text = call_gemini_with_retry(prompt)
            
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            slide_data = json.loads(response_text)
            
            # Clean content
            if "content" in slide_data:
                if len(slide_data["content"]) > 4:
                    slide_data["content"] = slide_data["content"][:4]
                elif len(slide_data["content"]) < 3:
                    while len(slide_data["content"]) < 3:
                        slide_data["content"].append(
                            f"Technical details about {slide_title} with specific implementation examples"
                        )
                
                cleaned = []
                for bullet in slide_data["content"]:
                    bullet = bullet.strip().lstrip("•-–— ")
                    words = bullet.split()
                    if len(words) > 30:
                        bullet = " ".join(words[:30])
                    cleaned.append(bullet)
                
                slide_data["content"] = cleaned
                
                if is_generic_content(slide_data["content"]):
                    if attempt < max_attempts - 1:
                        print(f"   ⚠️ Generic content, retry {attempt + 1}")
                        continue
            
            # Generate smart image query
            if not slide_data.get("image_query") or slide_data["image_query"] == slide_title:
                slide_data["image_query"] = generate_smart_image_query(
                    slide_title,
                    slide_data["content"],
                    clean_topic
                )
            
            return slide_data
            
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"   ⚠️ Attempt {attempt + 1} failed, retrying...")
                continue
            else:
                print(f"✗ Failed: {e}")
                return generate_fallback_content_with_unique_query(
                    slide_title, 
                    slide_number, 
                    clean_topic
                )
    
    return generate_fallback_content_with_unique_query(slide_title, slide_number, clean_topic)


@app.post("/api/generate-outline")
async def generate_outline(request: PresentationRequest):
    """Generate presentation with SHORT titles and SMART image queries"""
    try:
        # Preprocess the topic first
        clean_topic = preprocess_topic(request.topic)
        
        print(f"\n{'='*60}")
        print(f"📊 Original Topic: {request.topic[:100]}...")
        print(f"✨ Cleaned Topic: {clean_topic}")
        print(f"📝 Slides: {request.num_slides}")
        print(f"{'='*60}\n")
        
        # Step 1: Short title
        print(f"📌 Generating short title...")
        short_title = generate_short_title(request.topic, request.additional_context)
        print(f"   Title: {short_title}")
        
        # Step 2: Generate topics
        print(f"\n🎯 Generating {request.num_slides} slide topics...")
        slide_topics = generate_slide_topics(
            request.topic,
            request.num_slides,
            request.additional_context
        )
        
        # Step 3: Generate content with smart image queries
        print(f"\n📝 Generating content with smart image queries...")
        slides = []
        
        for idx, slide_title in enumerate(slide_topics, 1):
            print(f"   Slide {idx}/{len(slide_topics)}: {slide_title}")
            
            slide_content = generate_slide_content_v3(
                slide_title=slide_title,
                slide_number=idx,
                total_slides=len(slide_topics),
                main_topic=request.topic,
                previous_slides=slides,
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
            
            print(f"      Image query: {slide_content.get('image_query', 'default')}")
        
        print(f"\n✅ Generated {len(slides)} slides with:")
        print(f"   • Short, clear titles (3-7 words)")
        print(f"   • Smart diagram detection")
        print(f"   • Content-aware image queries")
        
        presentation_id = str(uuid.uuid4())
        
        presentations_db[presentation_id] = {
            "id": presentation_id,
            "topic": request.topic,
            "title": short_title,
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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.put("/api/update-slides")
async def update_slides(request: PresentationUpdate):
    """Update slide content"""
    try:
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
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
    """Get presentation data"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    return {"success": True, "data": presentations_db[presentation_id]}


@app.post("/api/generate-ppt")
async def generate_ppt(request: GeneratePPTRequest):
    """Generate PowerPoint"""
    try:
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        presentation_data = presentations_db[request.presentation_id]
        
        print(f"\n🎨 Generating PowerPoint...")
        print(f"   Title: {presentation_data['title']}")
        print(f"   Slides: {len(presentation_data['slides'])}")
        
        from pptx_generator import create_presentation
        
        output_dir = "generated_presentations"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{request.presentation_id}.pptx"
        filepath = os.path.join(output_dir, filename)
        
        create_presentation(presentation_data, filepath, request.template)
        
        presentations_db[request.presentation_id]["pptx_url"] = filepath
        presentations_db[request.presentation_id]["status"] = "completed"
        
        return {
            "success": True,
            "download_url": f"/api/download/{request.presentation_id}",
            "file_path": filepath
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{presentation_id}")
async def download_presentation(presentation_id: str):
    """Download presentation"""
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
        "message": "AutoSlideX API - Production Ready",
        "version": "3.1.0",
        "improvements": [
            "✅ Stable Gemini 1.5 Flash (better rate limits)",
            "✅ Rate limit handling with exponential backoff",
            "✅ Topic preprocessing (handles UNIT/HOURS format)",
            "✅ Unique image queries per slide (no duplicates)",
            "✅ Short titles (3-7 words)",
            "✅ Smart diagram detection"
        ]
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "presentations": len(presentations_db),
        "version": "3.1.0",
        "model": "gemini-1.5-flash"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)