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

## Getting Started

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
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

## Roadmap

- [ ] Basic VSDX parsing
- [ ] PNG fallback with vision AI
- [ ] React + Python template generation
- [ ] Advanced features (auth, databases) from diagram annotations
