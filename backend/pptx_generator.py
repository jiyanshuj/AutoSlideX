from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import requests
from io import BytesIO
from typing import Dict, List
import os
import re

class PPTXGenerator:
    """
    PowerPoint generator with split-screen layout
    Only accepts: BMP, GIF, JPEG, PNG, TIFF, WMF
    """
    
    # Supported image formats
    SUPPORTED_FORMATS = ['bmp', 'gif', 'jpeg', 'jpg', 'png', 'tiff', 'tif', 'wmf']
    
    def __init__(self, template="modern"):
        self.prs = Presentation()
        self.prs.slide_width = Inches(10)
        self.prs.slide_height = Inches(7.5)
        self.template = template
        self.theme_colors = self._get_theme_colors(template)
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")
        self.google_cx = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
    
    def _get_theme_colors(self, template):
        """Color schemes"""
        themes = {
            "modern": {
                "primary": RGBColor(41, 128, 185),
                "secondary": RGBColor(52, 73, 94),
                "accent": RGBColor(231, 76, 60),
                "background": RGBColor(248, 249, 250),
                "text": RGBColor(33, 33, 33),
                "light_text": RGBColor(255, 255, 255)
            },
            "professional": {
                "primary": RGBColor(31, 58, 147),
                "secondary": RGBColor(67, 97, 238),
                "accent": RGBColor(76, 175, 80),
                "background": RGBColor(255, 255, 255),
                "text": RGBColor(33, 33, 33),
                "light_text": RGBColor(255, 255, 255)
            }
        }
        return themes.get(template, themes["modern"])
    
    def _is_valid_image_format(self, url: str) -> bool:
        """Check if URL ends with supported format"""
        url_lower = url.lower()
        return any(url_lower.endswith(f'.{fmt}') for fmt in self.SUPPORTED_FORMATS)
    
    def _get_image_from_google(self, query: str, max_attempts: int = 3):
        """
        Search Google Images with format filtering
        Only returns: BMP, GIF, JPEG, PNG, TIFF, WMF
        """
        for attempt in range(max_attempts):
            try:
                if not self.google_api_key or not self.google_cx:
                    print("✗ Google API credentials missing")
                    return None
                
                print(f"🔍 Google Search (attempt {attempt + 1}): '{query}'")
                
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": self.google_api_key,
                    "cx": self.google_cx,
                    "q": query,
                    "searchType": "image",
                    "num": 10,  # Get more results
                    "imgSize": "large",
                    "imgType": "photo",
                    "safe": "active",
                    "fileType": "jpg,png,gif,bmp"  # Specify formats
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        # Try each result
                        for item in data["items"]:
                            image_url = item["link"]
                            
                            # Check format
                            if not self._is_valid_image_format(image_url):
                                print(f"   ⊘ Skipping unsupported format: {image_url[-20:]}")
                                continue
                            
                            # Try download
                            try:
                                print(f"   ↓ Downloading: {image_url[-30:]}")
                                img_response = requests.get(image_url, timeout=15, headers={
                                    'User-Agent': 'Mozilla/5.0'
                                })
                                if img_response.status_code == 200:
                                    # Verify it's a valid image
                                    from PIL import Image
                                    img = Image.open(BytesIO(img_response.content))
                                    img.verify()
                                    print(f"   ✓ Valid image: {img.format}")
                                    return BytesIO(img_response.content)
                            except Exception as e:
                                print(f"   ✗ Download failed: {str(e)[:50]}")
                                continue
                        
                        print(f"   ⚠️ No valid images in results")
                    else:
                        print(f"   ⚠️ No results")
                elif response.status_code == 429:
                    print(f"   ⚠️ Rate limit")
                else:
                    print(f"   ✗ API error: {response.status_code}")
                
            except Exception as e:
                print(f"   ✗ Error: {str(e)[:50]}")
            
            # Retry with modified query
            if attempt < max_attempts - 1:
                query = f"{query} illustration diagram"
                print(f"   🔄 Retrying with: '{query}'")
        
        return None
    
    def _get_image_from_unsplash(self, query: str):
        """Unsplash fallback"""
        try:
            print(f"🔄 Unsplash fallback: '{query}'")
            clean_query = query.replace(' ', ',')
            image_url = f"https://source.unsplash.com/1600x900/?{clean_query}"
            
            response = requests.get(image_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                print(f"   ✓ Downloaded from Unsplash")
                return BytesIO(response.content)
        except Exception as e:
            print(f"   ✗ Unsplash error: {e}")
        return None
    
    def _get_fallback_image(self, query: str):
        """Lorem Picsum fallback"""
        try:
            seed_num = abs(hash(query)) % 1000
            image_url = f"https://picsum.photos/seed/{seed_num}/1600/900"
            print(f"🔄 Picsum fallback...")
            
            response = requests.get(image_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                print(f"   ✓ Fallback image")
                return BytesIO(response.content)
        except Exception as e:
            print(f"   ✗ Picsum error: {e}")
        return None
    
    def _get_image(self, query: str):
        """
        Get image with format validation
        Priority: Google (with format filter) → Unsplash → Picsum
        """
        # Try Google with format filtering
        result = self._get_image_from_google(query)
        if result:
            return result
        
        # Try Unsplash
        result = self._get_image_from_unsplash(query)
        if result:
            return result
        
        # Final fallback
        result = self._get_fallback_image(query)
        if result:
            return result
        
        # Ultimate fallback
        try:
            response = requests.get("https://picsum.photos/1600/900", timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return BytesIO(response.content)
        except:
            pass
        
        return None
    
    def add_title_slide(self, title: str, subtitle: str = ""):
        """Title slide with background"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        
        print(f"📸 Title slide background...")
        bg_query = f"{title} professional background"
        bg_image = self._get_image(bg_query)
        
        if bg_image:
            pic = slide.shapes.add_picture(
                bg_image, Inches(0), Inches(0),
                width=self.prs.slide_width,
                height=self.prs.slide_height
            )
            slide.shapes._spTree.remove(pic._element)
            slide.shapes._spTree.insert(2, pic._element)
            
            # Dark overlay
            overlay = slide.shapes.add_shape(1, 0, 0, self.prs.slide_width, self.prs.slide_height)
            overlay.fill.solid()
            overlay.fill.fore_color.rgb = RGBColor(0, 0, 0)
            overlay.fill.transparency = 0.4
            overlay.line.fill.background()
            slide.shapes._spTree.remove(overlay._element)
            slide.shapes._spTree.insert(3, overlay._element)
        else:
            bg = slide.shapes.add_shape(1, 0, 0, self.prs.slide_width, self.prs.slide_height)
            bg.fill.solid()
            bg.fill.fore_color.rgb = self.theme_colors["secondary"]
            bg.line.fill.background()
        
        # Title
        title_box = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(8), Inches(2))
        title_frame = title_box.text_frame
        title_frame.text = title
        title_frame.word_wrap = True
        title_para = title_frame.paragraphs[0]
        title_para.font.size = Pt(60)
        title_para.font.bold = True
        title_para.font.color.rgb = RGBColor(255, 255, 255)
        title_para.alignment = PP_ALIGN.CENTER
        
        # Subtitle
        if subtitle:
            subtitle_box = slide.shapes.add_textbox(Inches(1), Inches(4.8), Inches(8), Inches(1))
            subtitle_frame = subtitle_box.text_frame
            subtitle_frame.text = subtitle
            subtitle_para = subtitle_frame.paragraphs[0]
            subtitle_para.font.size = Pt(28)
            subtitle_para.font.color.rgb = RGBColor(240, 240, 240)
            subtitle_para.alignment = PP_ALIGN.CENTER
    
    def add_content_slide(self, title: str, content: List[str], notes: str = "", image_query: str = None):
        """Split-screen: IMAGE LEFT, CONTENT RIGHT"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        
        # Use provided query or title
        query = image_query if image_query else f"{title} diagram"
        
        print(f"📸 Slide: {title}")
        print(f"   Query: '{query}'")
        content_image = self._get_image(query)
        
        if content_image:
            # Image on LEFT (40%)
            try:
                pic = slide.shapes.add_picture(
                    content_image, Inches(0), Inches(0),
                    width=Inches(4), height=self.prs.slide_height
                )
                print(f"   ✓ Image on LEFT side")
            except Exception as e:
                print(f"   ✗ Failed: {e}")
        
        # White background on RIGHT (60%)
        right_bg = slide.shapes.add_shape(
            1, Inches(4), Inches(0), Inches(6), self.prs.slide_height
        )
        right_bg.fill.solid()
        right_bg.fill.fore_color.rgb = RGBColor(255, 255, 255)
        right_bg.line.fill.background()
        
        # Title on right
        title_box = slide.shapes.add_textbox(
            Inches(4.3), Inches(0.5), Inches(5.4), Inches(1)
        )
        title_frame = title_box.text_frame
        title_frame.text = title
        title_frame.word_wrap = True
        title_para = title_frame.paragraphs[0]
        title_para.font.size = Pt(32)
        title_para.font.bold = True
        title_para.font.color.rgb = RGBColor(33, 33, 33)
        title_para.alignment = PP_ALIGN.LEFT
        
        # Divider
        divider = slide.shapes.add_shape(
            1, Inches(4.3), Inches(1.6), Inches(5.4), Inches(0.02)
        )
        divider.fill.solid()
        divider.fill.fore_color.rgb = self.theme_colors["accent"]
        divider.line.fill.background()
        
        # Content on right
        content_box = slide.shapes.add_textbox(
            Inches(4.3), Inches(2), Inches(5.2), Inches(5)
        )
        text_frame = content_box.text_frame
        text_frame.word_wrap = True
        text_frame.margin_left = Inches(0.2)
        text_frame.margin_right = Inches(0.2)
        
        # Font size
        total_chars = sum(len(point) for point in content)
        num_points = len(content)
        
        if num_points <= 3 and total_chars < 300:
            base_font_size = 20
        elif num_points <= 4 and total_chars < 450:
            base_font_size = 18
        else:
            base_font_size = 16
        
        # Bullet points
        for i, point in enumerate(content):
            if i > 0:
                text_frame.add_paragraph()
            p = text_frame.paragraphs[i]
            p.text = f"• {point}"
            p.font.size = Pt(base_font_size)
            p.font.color.rgb = RGBColor(50, 50, 50)
            p.space_before = Pt(12)
            p.space_after = Pt(8)
            p.line_spacing = 1.4
        
        # Notes
        if notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = notes[:500]
    
    def save(self, filepath: str):
        """Save presentation"""
        self.prs.save(filepath)


def create_presentation(presentation_data: Dict, output_path: str, template: str = "modern"):
    """
    Create presentation with IMAGE LEFT, CONTENT RIGHT
    Strict image format validation: BMP, GIF, JPEG, PNG, TIFF, WMF only
    """
    print(f"\n{'='*60}")
    print(f"Creating: {presentation_data['title']}")
    print(f"{'='*60}\n")
    
    generator = PPTXGenerator(template=template)
    
    # Title slide
    print(f"[Title Slide] {presentation_data['title']}")
    generator.add_title_slide(
        presentation_data["title"],
        "Generated by AutoSlideX"
    )
    
    # Content slides (IMAGE LEFT)
    for idx, slide_data in enumerate(presentation_data["slides"], 1):
        title = slide_data["title"]
        content = slide_data["content"]
        notes = slide_data.get("notes", "")
        image_query = slide_data.get("image_query")
        
        print(f"\n[Slide {idx}/{len(presentation_data['slides'])}] {title}")
        generator.add_content_slide(title, content, notes, image_query)
    
    # Thank you slide
    print(f"\n[Thank You Slide]")
    generator.add_title_slide("Thank You", "Questions?")
    
    # Save
    generator.save(output_path)
    
    print(f"\n{'='*60}")
    print(f"✅ Saved: {output_path}")
    print(f"📊 Slides: {len(presentation_data['slides']) + 2}")
    print(f"🎨 Layout: Image LEFT + Content RIGHT")
    print(f"📸 Formats: BMP, GIF, JPEG, PNG, TIFF, WMF only")
    print(f"{'='*60}\n")
    
    return output_path