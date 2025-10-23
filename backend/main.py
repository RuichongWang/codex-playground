"""
Enhanced Coding Agent Backend
FastAPI service for parsing diagrams and generating applications
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import os
from typing import Optional
import json
import io
import zipfile

from parsers.vsdx_parser import VSDXParser
from parsers.image_parser import ImageParser
from generators.code_generator import CodeGenerator

app = FastAPI(
    title="Enhanced Coding Agent",
    description="Generate complete applications from architecture diagrams",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
vsdx_parser = VSDXParser()
image_parser = ImageParser()
code_generator = CodeGenerator()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Enhanced Coding Agent",
        "version": "1.0.0"
    }

@app.post("/api/parse-diagram")
async def parse_diagram(file: UploadFile = File(...)):
    """
    Parse uploaded diagram (VSDX or PNG) and extract architecture
    Returns structured representation of components and flows
    """
    try:
        # Read file content
        content = await file.read()
        file_extension = file.filename.split('.')[-1].lower()

        # Parse based on file type
        if file_extension in ['vsdx', 'vdx']:
            architecture = await vsdx_parser.parse(content)
        elif file_extension in ['png', 'jpg', 'jpeg']:
            architecture = await image_parser.parse(content)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}"
            )

        return JSONResponse({
            "success": True,
            "architecture": architecture,
            "file_type": file_extension
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-app")
async def generate_app(architecture: dict):
    """
    Generate complete application code from parsed architecture
    Returns generated files as a zip archive
    """
    try:
        # Generate application code
        generated_files = await code_generator.generate(architecture)

        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path, content in generated_files.items():
                zip_file.writestr(file_path, content)

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=generated-app.zip"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-preview")
async def generate_preview(architecture: dict):
    """
    Generate application code and return as JSON for preview
    Does not return zip, just the file structure
    """
    try:
        # Generate application code
        generated_files = await code_generator.generate(architecture)

        return JSONResponse({
            "success": True,
            "files": generated_files
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
