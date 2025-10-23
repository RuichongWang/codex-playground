#!/bin/bash

echo "=== Enhanced Coding Agent Setup ==="
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Backend setup
echo "📦 Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created Python virtual environment"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
echo "✅ Installed backend dependencies"

# Setup .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚠️  Created .env file - Please add your ANTHROPIC_API_KEY"
fi

cd ..

# Frontend setup
echo ""
echo "📦 Setting up frontend..."
cd frontend

npm install
echo "✅ Installed frontend dependencies"

# Setup .env
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created frontend .env file"
fi

cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add your ANTHROPIC_API_KEY to backend/.env"
echo "2. Run 'npm run dev' to start the application"
echo ""
