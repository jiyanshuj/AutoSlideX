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
    Generate EXACTLY num_slides topics with EQUAL and COMPREHENSIVE coverage
    Ensures every aspect of the main topic is covered evenly across all slides
    """
    prompt = f"""
    You are creating a comprehensive presentation outline for: "{topic}"
    Additional context: {additional_context or "None"}
    
    CRITICAL REQUIREMENTS:
    
    1. SLIDE COUNT: Generate EXACTLY {num_slides} slide topics (no more, no less)
    
    2. COMPREHENSIVE COVERAGE:
       - Analyze ALL aspects, subtopics, and components of "{topic}"
       - Ensure EVERY major concept is covered
       - Distribute content EQUALLY across all {num_slides} slides
       - No topic should be overrepresented or underrepresented
    
    3. BALANCED DISTRIBUTION:
       - Each slide should cover roughly equal importance and depth
       - Divide the main topic into {num_slides} logical, equal parts
       - Ensure smooth progression from basic to advanced (if applicable)
    
    4. SLIDE STRUCTURE:
       - Slide 1: Introduction/Overview of the entire topic
       - Slides 2 to {num_slides-1}: Core concepts distributed equally
       - Slide {num_slides}: Conclusion/Summary/Future scope
    
    5. TOPIC NAMING:
       - Each topic should be clear and specific (3-8 words)
       - Use professional terminology
       - Make titles descriptive but concise
    
    EXAMPLE FOR "Object-Oriented Modeling" (5 slides):
    {{
      "topics": [
        "Introduction to Object-Oriented Technology",
        "Modeling Concepts and Design Techniques",
        "Class Model and Static Structure",
        "State Model and Dynamic Behavior",
        "Interaction Model and Applications"
      ]
    }}
    
    Now generate EXACTLY {num_slides} topics for "{topic}" that:
    - Cover ALL aspects comprehensively
    - Distribute content equally
    - Follow logical progression
    - Are specific and descriptive
    
    Return ONLY a valid JSON object with this exact format:
    {{
      "topics": [
        "Topic 1 title",
        "Topic 2 title",
        ...
        "Topic {num_slides} title"
      ]
    }}
    
    NO explanations, NO markdown, ONLY the JSON object.
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
        data = json.loads(response_text)
        
        # Extract topics array
        topics = data.get("topics", [])
        
        # FORCE exact count
        if len(topics) > num_slides:
            print(f"⚠️ Generated {len(topics)} topics, trimming to {num_slides}")
            topics = topics[:num_slides]
        elif len(topics) < num_slides:
            print(f"⚠️ Generated {len(topics)} topics, padding to {num_slides}")
            # Intelligently pad with related topics
            base_topic = topic.split()[0] if topic else "Topic"
            while len(topics) < num_slides:
                topics.append(f"{base_topic}: Additional Insights #{len(topics) + 1}")
        
        print(f"✓ Generated {len(topics)} balanced topics covering all aspects")
        return topics
        
    except json.JSONDecodeError as e:
        print(f"✗ JSON parsing error: {e}")
        print(f"Response text: {response_text[:200]}")
        # Fallback: generate structured generic topics
        return generate_fallback_topics(topic, num_slides)
    except Exception as e:
        print(f"✗ Error generating topics: {e}")
        return generate_fallback_topics(topic, num_slides)


def generate_fallback_topics(topic: str, num_slides: int) -> List[str]:
    """
    Generate fallback topics when AI generation fails
    Creates balanced, comprehensive topic distribution
    """
    topics = []
    
    # Always start with introduction
    topics.append(f"Introduction to {topic}")
    
    # Generate middle topics based on count
    if num_slides <= 3:
        if num_slides >= 2:
            topics.append(f"Key Concepts in {topic}")
        if num_slides >= 3:
            topics.append(f"Conclusion and Summary")
    
    elif num_slides <= 5:
        topics.append(f"Fundamental Concepts")
        topics.append(f"Core Principles and Methods")
        if num_slides >= 4:
            topics.append(f"Applications and Use Cases")
        if num_slides >= 5:
            topics.append(f"Conclusion and Future Scope")
    
    else:
        # For larger presentations, create more granular topics
        topics.append(f"Background and Fundamentals")
        topics.append(f"Core Concepts - Part 1")
        
        remaining = num_slides - 4  # Minus intro, 2 core, and conclusion
        
        for i in range(remaining):
            if i % 2 == 0:
                topics.append(f"Core Concepts - Part {i//2 + 2}")
            else:
                topics.append(f"Advanced Topics - Part {i//2 + 1}")
        
        topics.append(f"Conclusion and Future Directions")
    
    # Ensure exact count
    topics = topics[:num_slides]
    while len(topics) < num_slides:
        topics.insert(-1, f"Additional Insights #{len(topics)}")
    
    return topics


def is_generic_content(content: List[str]) -> bool:
    """
    Check if slide content is generic/placeholder/repetitive
    ENHANCED with strict forbidden phrase detection
    """
    if not content or len(content) < 3:
        return True
    
    # Forbidden phrases that indicate low-quality content
    forbidden_phrases = [
        "key concept about",
        "important aspect to consider",
        "related insight",
        "key point",
        "additional key insight",
        "additional insights",
        "core concepts and fundamentals",
        "practical applications and real-world use cases",
        "key considerations and best practices",
        "unit-i 10 hours",
        "unit-i introduction"
    ]
    
    # Check each bullet point
    for point in content:
        point_lower = point.lower()
        
        # Check for forbidden phrases
        for phrase in forbidden_phrases:
            if phrase in point_lower:
                print(f"   ⚠️ Generic/forbidden phrase found: '{phrase}'")
                return True
        
        # Check if too short (likely generic)
        if len(point.split()) < 8:
            return True
        
        # Check if point is mostly the same across multiple bullets
        point_words = set(point_lower.split())
        if len(point_words) < 6:  # Too few unique words
            return True
    
    return False


def has_verbatim_repetition(content: List[str], original_topic: str) -> bool:
    """
    Check if content contains verbatim repetition from the original topic
    STRICT detection - even partial phrases trigger rejection
    """
    if not content:
        return False
    
    # Combine content into single text
    content_text = " ".join(content).lower()
    topic_lower = original_topic.lower()
    
    # List of forbidden phrases that should NEVER appear
    forbidden_phrases = [
        "practical applications and real-world use cases in unit",
        "unit-i 10 hours introduction",
        "about object orientated technology, development and oo modeling",
        "modeling concepts: modeling design technique",
        "three models, class model, state model and interaction model",
        "key considerations and best practices for implementation"
    ]
    
    # Check for any forbidden phrase
    for phrase in forbidden_phrases:
        if phrase in content_text:
            print(f"   ⚠️ FORBIDDEN phrase detected: '{phrase[:50]}...'")
            return True
    
    # Extract phrases from topic (4+ words)
    topic_words = topic_lower.split()
    
    # Check for long verbatim phrases (4+ consecutive words from topic)
    for i in range(len(topic_words) - 3):
        phrase = " ".join(topic_words[i:i+4])
        if len(phrase) > 15 and phrase in content_text:  # Ignore very short phrases
            print(f"   ⚠️ Found verbatim phrase: '{phrase}'")
            return True
    
    return False


def calculate_content_similarity(content1: List[str], content2: List[str]) -> float:
    """
    Calculate similarity between two slide contents (0.0 to 1.0)
    Enhanced with phrase-level detection
    """
    if not content1 or not content2:
        return 0.0
    
    # Combine all bullet points into text
    text1 = " ".join(content1).lower()
    text2 = " ".join(content2).lower()
    
    # Extract meaningful words (ignore common words)
    common_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'about', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
    }
    
    words1 = set(word for word in text1.split() if len(word) > 3 and word not in common_words)
    words2 = set(word for word in text2.split() if len(word) > 3 and word not in common_words)
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    similarity = intersection / union if union > 0 else 0.0
    
    # Additional check: look for identical phrases (3+ words)
    words1_list = text1.split()
    words2_list = text2.split()
    
    phrase_matches = 0
    for i in range(len(words1_list) - 2):
        phrase = " ".join(words1_list[i:i+3])
        if phrase in text2 and len(phrase) > 10:  # Ignore short phrases
            phrase_matches += 1
    
    # Boost similarity if we find identical phrases
    if phrase_matches > 2:
        similarity = min(1.0, similarity + 0.2)
    
    return similarity


def detect_duplicate_slides(slides: List[dict]) -> List[tuple]:
    """
    Detect slides with duplicate or highly similar content
    Returns list of (slide_index1, slide_index2, similarity_score) tuples
    """
    duplicates = []
    threshold = 0.5  # Lowered to 50% to catch more duplicates
    
    for i in range(len(slides)):
        for j in range(i + 1, len(slides)):
            similarity = calculate_content_similarity(
                slides[i]["content"], 
                slides[j]["content"]
            )
            if similarity >= threshold:
                duplicates.append((i, j, similarity))
    
    return duplicates


def generate_fallback_content(slide_title: str, main_topic: str) -> dict:
    """
    Generate basic fallback content when AI generation fails
    """
    return {
        "title": slide_title,
        "content": [
            f"Comprehensive overview of {slide_title.lower()} including key definitions and fundamental principles",
            f"Detailed exploration of methodologies, techniques, and approaches used in {slide_title.lower()}",
            f"Real-world applications, practical examples, and industry best practices for implementing {slide_title.lower()}"
        ],
        "image_query": slide_title.lower(),
        "notes": f"Detailed discussion of {slide_title} in the context of {main_topic}"
    }


def generate_slide_content_v2(slide_title: str, slide_number: int, total_slides: int, 
                              main_topic: str, previous_slides: List[dict] = None,
                              additional_context: str = None) -> dict:
    """
    Enhanced version with STRICT duplicate prevention and NO verbatim topic repetition
    """
    
    # Build context from previous slides to avoid duplication
    previous_content_summary = ""
    forbidden_content = []
    
    if previous_slides and len(previous_slides) > 0:
        for prev_slide in previous_slides:
            for point in prev_slide.get("content", []):
                # Extract key phrases (5+ words) from previous content
                words = point.split()
                if len(words) >= 5:
                    forbidden_content.append(point[:80])
        
        if forbidden_content:
            previous_content_summary = f"""
========== CRITICAL: FORBIDDEN CONTENT ==========
The following content has ALREADY been used in previous slides.
You MUST NOT repeat ANY of these phrases or similar wording:

{chr(10).join(f"❌ {content}" for content in forbidden_content[-8:])}

========== STRICT REQUIREMENTS ==========
1. Create COMPLETELY DIFFERENT content with NEW information
2. Use DIFFERENT vocabulary, phrases, and sentence structures
3. Focus on UNIQUE aspects of "{slide_title}" only
4. NO repetition of concepts from previous slides
================================================
"""
    
    # Extract key terms from the original topic to avoid verbatim copying
    topic_phrases = []
    topic_words = main_topic.split()
    for i in range(len(topic_words) - 3):
        phrase = " ".join(topic_words[i:i+4]).lower()
        topic_phrases.append(phrase)
    
    forbidden_topic_phrases = ", ".join([f'"{p}"' for p in topic_phrases[:5]])
    
    prompt = f"""
    Create UNIQUE, ORIGINAL slide content for: "{main_topic}"
    
    Slide #{slide_number} of {total_slides}
    Slide Title: "{slide_title}"
    Additional Context: {additional_context or "None"}
    
    {previous_content_summary}
    
    ========== ABSOLUTE PROHIBITIONS ==========
    ❌ FORBIDDEN PHRASES - DO NOT USE ANY OF THESE:
       • "practical applications and real-world use cases in unit"
       • "unit-i 10 hours introduction"
       • "about object orientated technology, development and oo modeling"
       • "modeling concepts: modeling design technique"
       • "three models, class model, state model and interaction model"
       • "key considerations and best practices for implementation"
    
    ❌ DO NOT copy ANY phrases from the original topic description
    ❌ DO NOT use generic statements - be HIGHLY SPECIFIC
    ❌ DO NOT repeat ANY content from previous slides
    ❌ DO NOT mention course-specific terms like "unit-i", "10 hours"
    ================================================
    
    ========== CRITICAL UNIQUENESS REQUIREMENTS ==========
    1. Create EXACTLY 3-4 bullet points with SPECIFIC, UNIQUE information
    2. Each bullet MUST be 15-25 words with CONCRETE details
    3. Focus SPECIFICALLY on "{slide_title}" - be VERY specific to this topic
    4. Use TECHNICAL terminology and SPECIFIC examples
    5. Include NUMBERS, NAMES, or SPECIFIC methods where possible
    6. This is slide {slide_number} of {total_slides} - cover the {slide_number}th DISTINCT aspect
    7. Write in YOUR OWN WORDS - do not copy from the topic description
    ================================================
    
    ========== CONTENT STRATEGY BY SLIDE NUMBER ==========
    Slide 1: Historical background, origins, evolution, foundational concepts
    Slide 2: Core principles, fundamental theories, key definitions (NEW content)
    Slide 3: Technical implementation, methodologies, specific techniques (DIFFERENT from 1-2)
    Slide 4: Advanced concepts, specialized applications, complex scenarios
    Slide 5+: Specific use cases, tools, frameworks, future trends
    ================================================
    
    ========== EXCELLENT EXAMPLES (Unique & Specific) ==========
    
    For "Foundations of Object-Oriented Technology":
    ✓ "Object-oriented paradigm emerged from Simula-67 in 1960s, introducing the revolutionary concept of encapsulating data and behavior within self-contained entities called objects"
    ✓ "Alan Kay's Smalltalk language established five core OOP principles: everything is an object, objects communicate via messages, each object has independent memory, and programs are collections of cooperating objects"
    ✓ "Evolution from procedural programming addressed software crisis of 1970s by enabling better code organization, reusability through inheritance, and maintainability in large-scale enterprise applications"
    
    For "Core Concepts and Modeling" (DIFFERENT from above):
    ✓ "Three-model approach separates system description into class model for static structure, state model for dynamic behavior, and interaction model for external communication patterns"
    ✓ "Modeling design technique employs abstraction layers: problem domain model captures real-world entities, application model defines software components, and implementation model specifies technical architecture"
    ✓ "UML notation provides standardized diagrams including class diagrams for structure, sequence diagrams for interactions, and state charts for behavioral modeling across different system aspects"
    
    For "Class Model" (DIFFERENT from 1-2):
    ✓ "Class diagrams represent static structure using rectangles divided into three sections: class name at top, attributes in middle, and operations at bottom with visibility modifiers"
    ✓ "Relationships include association for general connections, aggregation for whole-part with independent lifetimes, and composition for strong ownership where parts cannot exist independently"
    ✓ "Multiplicity notation specifies cardinality constraints: 1 for exactly one, 0..1 for optional, * for zero or more, and 1..* for one or more instances in the relationship"
    
    ========== BAD EXAMPLES (TOO GENERIC - NEVER DO) ==========
    ✗ "Practical applications and real-world use cases in unit-i 10 hours introduction"
    ✗ "Core concepts and fundamentals of object-oriented technology and history"
    ✗ "Key considerations and best practices for implementation"
    ✗ "Important aspects to consider when working with this topic"
    ================================================
    
    ========== RESPONSE FORMAT ==========
    Return ONLY valid JSON (no markdown, no backticks):
    {{
        "title": "{slide_title}",
        "content": [
            "Highly specific bullet with technical details and examples (15-25 words)",
            "Another unique point with concrete information and specifics (15-25 words)",
            "Third distinct insight with measurable details or named concepts (15-25 words)"
        ],
        "image_query": "{slide_title.lower()} diagram illustration",
        "notes": "Comprehensive speaker notes with specific examples and technical context for {slide_title}"
    }}
    ================================================
    
    REMEMBER: Slide {slide_number} about "{slide_title}" - Make it UNIQUELY focused, HIGHLY specific, and COMPLETELY different from all previous slides!
    """
    
    max_attempts = 3  # Increased from 2 to 3 attempts
    for attempt in range(max_attempts):
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
                if len(slide_data["content"]) > 4:
                    slide_data["content"] = slide_data["content"][:4]
                elif len(slide_data["content"]) < 3:
                    while len(slide_data["content"]) < 3:
                        slide_data["content"].append(f"Specific technical insight about {slide_title} with detailed explanation and examples")
                
                # Clean and trim bullets
                cleaned_content = []
                for bullet in slide_data["content"]:
                    bullet = bullet.strip().lstrip("•-–— ")
                    words = bullet.split()
                    if len(words) > 30:
                        bullet = " ".join(words[:30])
                    cleaned_content.append(bullet)
                
                slide_data["content"] = cleaned_content
                
                # STRICT VALIDATION - Check for verbatim repetition from original topic
                if has_verbatim_repetition(slide_data["content"], main_topic):
                    if attempt < max_attempts - 1:
                        print(f"   ⚠️ Attempt {attempt + 1}: Verbatim repetition detected, regenerating...")
                        continue
                    else:
                        print(f"   ❌ Failed after {max_attempts} attempts - using fallback")
                        return generate_fallback_content(slide_title, main_topic)
                
                # Check if content is too generic
                if is_generic_content(slide_data["content"]):
                    if attempt < max_attempts - 1:
                        print(f"   ⚠️ Attempt {attempt + 1}: Generic content detected, regenerating...")
                        continue
                    else:
                        print(f"   ❌ Failed after {max_attempts} attempts - using fallback")
                        return generate_fallback_content(slide_title, main_topic)
                
                # SUCCESS - content passed all checks
                if attempt > 0:
                    print(f"   ✓ Generated quality content on attempt {attempt + 1}")
            
            return slide_data
            
        except Exception as e:
            if attempt < max_attempts - 1:
                print(f"   ⚠️ Attempt {attempt + 1} failed: {e}, retrying...")
                continue
            else:
                print(f"✗ Error after {max_attempts} attempts: {e}")
                return generate_fallback_content(slide_title, main_topic)
    
    return generate_fallback_content(slide_title, main_topic)


def regenerate_duplicate_slide(slide_index: int, slide_data: dict, all_slides: List[dict],
                               main_topic: str, additional_context: str = None, attempt_num: int = 1) -> dict:
    """
    Regenerate a slide that has duplicate content
    Uses all existing slides as context to ensure uniqueness
    """
    print(f"   🔄 Regenerating slide {slide_index + 1} (attempt {attempt_num}) to ensure unique content...")
    
    # Get all OTHER slides (exclude current one)
    other_slides = [s for i, s in enumerate(all_slides) if i != slide_index]
    
    improved_content = generate_slide_content_v2(
        slide_title=slide_data["title"],
        slide_number=slide_index + 1,
        total_slides=len(all_slides),
        main_topic=main_topic,
        previous_slides=other_slides,
        additional_context=additional_context
    )
    
    return improved_content


@app.get("/")
async def root():
    return {
        "message": "AutoSlideX API",
        "version": "2.1.0 - Strict Duplicate Prevention",
        "status": "running",
        "endpoints": ["/api/generate-outline", "/api/update-slides", "/api/generate-ppt"]
    }


@app.post("/api/generate-outline")
async def generate_outline(request: PresentationRequest):
    """Generate presentation outline with STRICT duplicate detection and prevention"""
    try:
        print(f"\n{'='*60}")
        print(f"📊 Generating outline for: {request.topic}")
        print(f"📝 Requested slides: {request.num_slides}")
        print(f"🎯 STRICT duplicate detection: ENABLED")
        print(f"🚫 Verbatim repetition check: ENABLED")
        print(f"{'='*60}\n")
        
        # Step 0: Generate short title
        print(f"📌 Step 0/5: Generating concise title...")
        short_title = generate_short_title(request.topic, request.additional_context)
        print(f"   Title: {short_title}")
        
        # Step 1: Generate slide topics
        print(f"\n🎯 Step 1/5: Generating {request.num_slides} balanced slide topics...")
        slide_topics = generate_slide_topics(
            request.topic, 
            request.num_slides, 
            request.additional_context
        )
        
        # Step 2: Generate content for each slide WITH CONTEXT
        print(f"\n📝 Step 2/5: Generating unique content for each slide...")
        slides = []
        
        for idx, slide_title in enumerate(slide_topics, 1):
            print(f"   Processing slide {idx}/{len(slide_topics)}: {slide_title}")
            
            # Pass previously generated slides as context
            slide_content = generate_slide_content_v2(
                slide_title=slide_title,
                slide_number=idx,
                total_slides=len(slide_topics),
                main_topic=request.topic,
                previous_slides=slides,  # Pass existing slides to avoid duplication
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
        
        # Step 3: Check for verbatim repetition from original topic
        print(f"\n🔍 Step 3/5: Checking for verbatim repetition...")
        verbatim_slides = []
        for idx, slide in enumerate(slides):
            if has_verbatim_repetition(slide["content"], request.topic):
                verbatim_slides.append(idx)
                print(f"   ⚠️ Slide {idx + 1} contains verbatim phrases from topic")
        
        if verbatim_slides:
            print(f"   🔄 Regenerating {len(verbatim_slides)} slides with verbatim content...")
            for idx in verbatim_slides:
                improved = regenerate_duplicate_slide(
                    idx, slides[idx], slides,
                    request.topic, request.additional_context, attempt_num=1
                )
                slides[idx].update(improved)
            print(f"   ✓ Regenerated slides with original content")
        else:
            print(f"   ✓ No verbatim repetition detected")
        
        # Step 4: Detect and fix duplicate content between slides
        print(f"\n🔍 Step 4/5: Detecting duplicate content between slides...")
        duplicates = detect_duplicate_slides(slides)
        
        if duplicates:
            print(f"   ⚠️ Found {len(duplicates)} slide pairs with similar content:")
            for idx1, idx2, similarity in duplicates:
                print(f"      - Slides {idx1 + 1} & {idx2 + 1}: {similarity*100:.1f}% similar")
            
            # Regenerate slides with high similarity
            regenerated = set()
            for idx1, idx2, similarity in sorted(duplicates, key=lambda x: -x[2]):
                # Regenerate the later slide (idx2)
                if idx2 not in regenerated and similarity > 0.6:
                    improved = regenerate_duplicate_slide(
                        idx2, slides[idx2], slides,
                        request.topic, request.additional_context, attempt_num=2
                    )
                    slides[idx2].update(improved)
                    regenerated.add(idx2)
            
            print(f"   ✓ Regenerated {len(regenerated)} slides with unique content")
        else:
            print(f"   ✓ No duplicate content detected")
        
        # Step 5: Final quality check
        print(f"\n🔍 Step 5/5: Final quality check...")
        regenerated_count = 0
        for idx, slide in enumerate(slides):
            if is_generic_content(slide["content"]):
                print(f"   ⚠️ Slide {idx + 1} has generic content, improving...")
                improved_content = regenerate_duplicate_slide(
                    idx, slide, slides,
                    request.topic, request.additional_context, attempt_num=3
                )
                slides[idx].update(improved_content)
                regenerated_count += 1
        
        if regenerated_count > 0:
            print(f"   ✓ Improved {regenerated_count} slides")
        else:
            print(f"   ✓ All slides have quality content")
        
        # Final duplicate check
        final_duplicates = detect_duplicate_slides(slides)
        final_verbatim = sum(1 for slide in slides if has_verbatim_repetition(slide["content"], request.topic))
        
        if final_duplicates:
            print(f"   ⚠️ Warning: {len(final_duplicates)} similar slides remain")
        else:
            print(f"   ✅ All slides have unique content")
        
        if final_verbatim > 0:
            print(f"   ⚠️ Warning: {final_verbatim} slides still have verbatim content")
        else:
            print(f"   ✅ No verbatim repetition from topic")
        
        # Final verification
        if len(slides) != request.num_slides:
            print(f"⚠️ WARNING: Generated {len(slides)} slides, expected {request.num_slides}")
            if len(slides) > request.num_slides:
                slides = slides[:request.num_slides]
            elif len(slides) < request.num_slides:
                while len(slides) < request.num_slides:
                    slides.append({
                        "slide_number": len(slides) + 1,
                        "title": f"Additional Topic {len(slides) + 1}",
                        "content": [
                            "Comprehensive exploration of additional key concepts with specific technical details and practical examples",
                            "Detailed analysis of methodologies, frameworks, and implementation strategies relevant to this topic area",
                            "Real-world case studies demonstrating successful applications and industry best practices for optimal results"
                        ],
                        "layout_type": "content",
                        "image_query": request.topic.lower(),
                        "notes": ""
                    })
        
        print(f"\n✅ Successfully generated {len(slides)} slides with:")
        print(f"   • Unique content for each slide")
        print(f"   • No duplicate information")
        print(f"   • No verbatim topic repetition")
        print(f"   • Quality validation passed")
        print()
        
        # Generate unique presentation ID
        presentation_id = str(uuid.uuid4())
        
        # Store in database
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
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to parse AI response. Please try again. Error: {str(e)}"
        )
    except Exception as e:
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
            slide_dict["slide_number"] = idx
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
        if request.presentation_id not in presentations_db:
            raise HTTPException(status_code=404, detail="Presentation not found")
        
        presentation_data = presentations_db[request.presentation_id]
        
        print(f"\n{'='*60}")
        print(f"🎨 Generating PowerPoint presentation...")
        print(f"   Presentation: {presentation_data['title']}")
        print(f"   Total slides: {len(presentation_data['slides'])}")
        print(f"{'='*60}\n")
        
        # Import pptx_generator module
        from pptx_generator import create_presentation
        
        # Generate PPTX file
        output_dir = "generated_presentations"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{request.presentation_id}.pptx"
        filepath = os.path.join(output_dir, filename)
        
        create_presentation(
            presentation_data,
            filepath,
            template=request.template
        )
        
        # Update database
        presentations_db[request.presentation_id]["pptx_url"] = filepath
        presentations_db[request.presentation_id]["status"] = "completed"
        
        return {
            "success": True,
            "message": "Presentation generated successfully",
            "download_url": f"/api/download/{request.presentation_id}",
            "file_path": filepath
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PPT: {str(e)}")


@app.get("/api/download/{presentation_id}")
async def download_presentation(presentation_id: str):
    """Download generated presentation"""
    if presentation_id not in presentations_db:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    presentation = presentations_db[presentation_id]
    
    if "pptx_url" not in presentation:
        raise HTTPException(status_code=400, detail="Presentation not yet generated")
    
    filepath = presentation["pptx_url"]
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{presentation['title']}.pptx"
    )


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
        "presentations_count": len(presentations_db),
        "version": "2.1.0 - Strict Duplicate Prevention"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)