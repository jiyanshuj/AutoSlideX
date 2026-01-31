# AutoSlideX Backend

A powerful FastAPI-based backend service for AutoSlideX - an intelligent presentation generation platform powered by Google's Gemini AI.

## Overview

AutoSlideX Backend is a REST API service that leverages Google's Gemini AI to intelligently generate presentation content and creates professional PowerPoint presentations. It provides endpoints for generating slides, customizing presentation content, and exporting presentations in multiple formats.

## Tech Stack

- **Framework**: FastAPI 0.115
- **ASGI Server**: Uvicorn 0.32
- **AI Model**: Google Generative AI (Gemini)
- **Data Validation**: Pydantic 2.9
- **PowerPoint Generation**: python-pptx 1.0.2
- **HTTP Requests**: Requests 2.32
- **Image Processing**: Pillow 11.0
- **Environment Management**: Python-dotenv 1.0.1
- **Python Version**: 3.10+

## Features

- **AI-Powered Content Generation**: Generate intelligent slide content using Google Gemini AI
- **Two-Stage Generation**: Efficient content generation with model fallback support
- **PowerPoint Export**: Create professional presentations with customizable templates
- **Split-Screen Layouts**: Support for content with image combinations
- **Template Support**: Multiple professional themes (modern, professional)
- **CORS Enabled**: Ready for frontend integration
- **RESTful API**: Clean and intuitive API design
- **Error Handling**: Robust error handling with meaningful responses

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Google Gemini API key
- (Optional) Google Custom Search API key for image search

### Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory with required credentials:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here  # Optional
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id_here  # Optional
```

## Running the Server

### Development

Start the development server with auto-reload:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Production

Start the production server:
```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

### Using Render

The project includes `render.yaml` for deployment on Render:
- **Service Type**: Web Service
- **Runtime**: Python 3.10
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 10000`

## Project Structure

```
backend/
├── main.py                  # FastAPI application and API endpoints
├── pptx_generator.py        # PowerPoint generation logic
├── requirements.txt         # Python dependencies
├── render.yaml             # Render deployment configuration
├── .env.example            # Environment variables template
└── README.md               # This file
```

## API Endpoints

### 1. Generate Presentation Content
**Endpoint**: `POST /api/generate`

**Request Body**:
```json
{
  "topic": "Introduction to Machine Learning",
  "num_slides": 5,
  "additional_context": "Focus on practical applications"
}
```

**Response**:
```json
{
  "presentation_id": "uuid-string",
  "slides": [
    {
      "slide_number": 1,
      "title": "Introduction to Machine Learning",
      "content": ["Overview", "Key concepts"],
      "layout_type": "title",
      "image_query": null,
      "notes": "Speaker notes"
    }
  ]
}
```

### 2. Update Presentation
**Endpoint**: `PUT /api/update`

**Request Body**:
```json
{
  "presentation_id": "uuid-string",
  "slides": [
    {
      "slide_number": 1,
      "title": "Updated Title",
      "content": ["New content"],
      "layout_type": "content"
    }
  ]
}
```

### 3. Generate PowerPoint
**Endpoint**: `POST /api/generate_ppt`

**Request Body**:
```json
{
  "presentation_id": "uuid-string",
  "template": "modern",
  "export_format": "pptx"
}
```

**Response**: Binary PowerPoint file

### 4. Get Presentation Status
**Endpoint**: `GET /api/presentations/{presentation_id}`

**Response**:
```json
{
  "presentation_id": "uuid-string",
  "status": "completed",
  "created_at": "2024-02-01T10:00:00Z",
  "slides": [...]
}
```

## Pydantic Models

### SlideContent
- `slide_number` (int): Slide position
- `title` (str): Slide title
- `content` (List[str]): Slide bullet points
- `layout_type` (str): Layout template
- `image_query` (Optional[str]): Image search query
- `notes` (Optional[str]): Speaker notes

### PresentationRequest
- `topic` (str): Presentation topic
- `num_slides` (int): Number of slides to generate
- `additional_context` (Optional[str]): Additional context for content generation

### PresentationUpdate
- `presentation_id` (str): UUID of presentation
- `slides` (List[SlideContent]): Updated slides

### GeneratePPTRequest
- `presentation_id` (str): UUID of presentation
- `template` (Optional[str]): Template name (default: "modern")
- `export_format` (str): Export format (default: "pptx")

## Key Features

### AI Model Fallback
The system uses a fallback mechanism for Gemini models:
1. `models/gemini-2.5-flash`
2. `models/gemini-2.5-flash-lite`
3. `models/gemini-3-flash`

### Content Preprocessing
- Removes course unit information from topics
- Cleans up excessive formatting
- Truncates long topic descriptions intelligently

### PowerPoint Generation
- Supports multiple image formats: BMP, GIF, JPEG, PNG, TIFF, WMF
- Customizable color schemes and templates
- Split-screen layout support
- Professional formatting with proper font and spacing

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `GOOGLE_API_KEY` | Google Custom Search API key | No |
| `GOOGLE_SEARCH_ENGINE_ID` | Google Custom Search Engine ID | No |

## Development

### Code Structure

- **main.py**: 
  - FastAPI app initialization
  - CORS middleware configuration
  - API endpoints
  - Pydantic models for data validation

- **pptx_generator.py**:
  - `PPTXGenerator` class for PowerPoint creation
  - Theme color management
  - Layout and styling logic
  - Image integration

### Best Practices

1. **Error Handling**: All endpoints return appropriate HTTP status codes and error messages
2. **Validation**: Pydantic models ensure data integrity
3. **API Documentation**: Automatic Swagger UI at `/docs`
4. **CORS Support**: Configured to allow requests from any origin

## Testing

### Health Check
```bash
curl http://localhost:8000/
```

### Generate Presentation
```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Introduction to Python",
    "num_slides": 3,
    "additional_context": "Beginner level"
  }'
```

## Performance Considerations

- Gemini API calls are made sequentially with retry logic
- Model selection uses fallback mechanisms for reliability
- Image processing is optimized for supported formats only
- Presentations are cached in memory (presentations_db)

## Deployment

### Render

The `render.yaml` file is pre-configured for Render deployment:

```bash
# Deploy to Render
git push origin main
# Render will automatically deploy based on render.yaml configuration
```

### Docker

You can containerize the application by creating a Dockerfile:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
```

## Troubleshooting

### Common Issues

1. **GEMINI_API_KEY not set**
   - Solution: Add `GEMINI_API_KEY` to your `.env` file

2. **Model not available**
   - Solution: Check API quota and model availability

3. **Image format not supported**
   - Solution: Convert images to supported formats (PNG, JPEG, BMP, GIF, TIFF, WMF)

4. **CORS errors**
   - Solution: Check frontend URL is not blocked by CORS policy

## Future Enhancements

- [ ] Database persistence (replace in-memory storage)
- [ ] User authentication and authorization
- [ ] Caching layer for improved performance
- [ ] Support for more export formats (PDF, ODP)
- [ ] Webhook support for async operations
- [ ] Rate limiting
- [ ] Request logging and monitoring
- [ ] Image optimization pipeline

## Contributing

When contributing to the backend:

1. Follow PEP 8 code style guidelines
2. Add comprehensive docstrings to functions
3. Include error handling for edge cases
4. Test endpoints with sample data
5. Update documentation for new features

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Support

For issues, questions, or contributions, please refer to the main AutoSlideX project documentation.

## License

Part of the AutoSlideX project.
