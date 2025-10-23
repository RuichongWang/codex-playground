# Enhanced Coding Agent

An AI-powered system that generates complete, runnable applications from architecture diagrams.

## Overview

Upload a system architecture diagram (VSDX or PNG) and get a fully working React + Python application.

### Example
Draw: `User Input → LLM Joke Writer → Output`
Get: A complete chat app where users send messages and receive AI-generated jokes.

## Architecture

```
┌─────────────────────────────────────┐
│   React Frontend (Vite)             │
│   - Upload diagram (VSDX/PNG)       │
│   - Preview generated code          │
│   - Download application            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Python Backend (FastAPI)          │
│   - Parse VSDX/PNG diagrams         │
│   - Analyze architecture            │
│   - Generate code via Claude API    │
│   - Return complete app             │
└─────────────────────────────────────┘
```

## Tech Stack

- **Frontend**: React + Vite + TypeScript
- **Backend**: Python + FastAPI
- **Diagram Parsing**: VSDX (primary), Claude Vision (PNG fallback)
- **Code Generation**: Claude API (Sonnet)
- **Output**: React + Python Flask/FastAPI apps

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Anthropic API key ([Get one here](https://console.anthropic.com/))

### Automated Setup
```bash
# Run setup script
./setup.sh

# Add your API key to backend/.env
# ANTHROPIC_API_KEY=your_key_here

# Start both frontend and backend
./dev.sh
```

Visit `http://localhost:5173` to use the application!

### Manual Setup

#### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Project Structure

```
codex-playground/
├── backend/           # Python FastAPI backend
│   ├── main.py       # FastAPI app
│   ├── parsers/      # VSDX and image parsers
│   ├── generators/   # Code generation logic
│   └── templates/    # App templates
├── frontend/         # React Vite frontend
│   └── src/
└── README.md
```

## Features

- **Smart Parsing**: Extract components and flows from VSDX diagrams
- **AI Generation**: Claude-powered code generation
- **Full Stack**: Generate complete React + Python applications
- **Instant Preview**: See generated code before download
- **MVP Focus**: Working code, no prod overhead

## Usage

1. **Upload Diagram**: Choose a VSDX file from Lucidchart or PNG screenshot
2. **View Architecture**: Review the parsed components and connections
3. **Generate Code**: Click to generate a complete application
4. **Preview & Download**: Review code and download as ZIP

### Diagram Tips
- Use clear labels for components (e.g., "User Input", "LLM Processor", "Output Display")
- Draw arrows to show data flow between components
- Label LLM components clearly to enable API integration
- Keep it simple for MVP - complex features can be added later

## API Endpoints

### Backend (http://localhost:8000)
- `GET /` - Health check
- `POST /api/parse-diagram` - Upload and parse diagram (VSDX/PNG)
- `POST /api/generate-preview` - Generate code preview (JSON)
- `POST /api/generate-app` - Download complete app (ZIP)

### Frontend (http://localhost:5173)
- Web interface for uploading diagrams and downloading apps

## Development

### Backend Structure
```
backend/
├── main.py                    # FastAPI app
├── parsers/
│   ├── vsdx_parser.py        # Parse VSDX files
│   └── image_parser.py       # Parse images with Claude Vision
└── generators/
    └── code_generator.py     # Generate apps with Claude API
```

### Frontend Structure
```
frontend/src/
├── App.tsx                   # Main component
├── App.css                   # Styling
└── main.tsx                  # Entry point
```

## Roadmap

- [x] Basic VSDX parsing
- [x] PNG fallback with vision AI
- [x] React + Python template generation
- [x] File upload and preview UI
- [ ] Enhanced component type detection
- [ ] Custom styling options for generated apps
- [ ] Database schema generation
- [ ] Authentication flow generation
- [ ] Deployment configuration (Docker, cloud)
