"""
Code Generator
Generates complete React + Python applications from architecture specifications
"""
import os
import json
from typing import Dict, Any
import anthropic

class CodeGenerator:
    """Generates full-stack applications using Claude API"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    async def generate(self, architecture: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate complete application from architecture

        Args:
            architecture: Parsed architecture with components and connections

        Returns:
            Dictionary mapping file paths to file contents
        """
        # Build generation prompt
        prompt = self._build_prompt(architecture)

        # Call Claude API for code generation
        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )

        # Extract generated code from response
        response_text = message.content[0].text

        # Parse the generated files
        files = self._parse_generated_code(response_text)

        return files

    def _build_prompt(self, architecture: Dict[str, Any]) -> str:
        """Build the code generation prompt"""
        components = architecture.get("components", [])
        connections = architecture.get("connections", [])

        prompt = f"""You are an expert full-stack developer. Generate a complete, working application based on this architecture:

**Components:**
{json.dumps(components, indent=2)}

**Connections (Data Flow):**
{json.dumps(connections, indent=2)}

**Requirements:**
1. Create a React frontend (using Vite + TypeScript)
2. Create a Python backend (using FastAPI)
3. Generate COMPLETE, WORKING code - not pseudocode or TODOs
4. Include all necessary files (package.json, requirements.txt, etc.)
5. Use in-memory storage (no database setup needed)
6. Integrate Claude API where LLM components are specified
7. Make it runnable immediately after extraction

**Application Flow:**
Analyze the components and connections to understand the data flow. Generate appropriate:
- Frontend UI components for user inputs/outputs
- API endpoints for backend operations
- LLM integrations where specified
- State management and API calls

**Output Format:**
Return files in this format:

```FILE: frontend/package.json
{{
  "name": "generated-app",
  ...
}}
```

```FILE: frontend/src/App.tsx
import React from 'react';
...
```

```FILE: backend/main.py
from fastapi import FastAPI
...
```

Generate ALL necessary files for a working MVP. Include:
- Frontend: package.json, index.html, vite.config.ts, tsconfig.json, src/App.tsx, src/main.tsx, src/index.css
- Backend: requirements.txt, main.py, .env.example

Make sure the frontend can communicate with the backend via API calls."""

        return prompt

    def _parse_generated_code(self, response: str) -> Dict[str, str]:
        """Parse generated code from Claude's response"""
        files = {}

        # Split by FILE markers
        import re
        file_pattern = r'```FILE:\s*([^\n]+)\n(.*?)```'

        matches = re.finditer(file_pattern, response, re.DOTALL)

        for match in matches:
            file_path = match.group(1).strip()
            content = match.group(2).strip()
            files[file_path] = content

        # If no files found, try alternative parsing
        if not files:
            files = self._fallback_parsing(response)

        return files

    def _fallback_parsing(self, response: str) -> Dict[str, str]:
        """Fallback parsing if FILE markers not found"""
        # Try to extract code blocks
        import re
        code_blocks = re.findall(r'```(\w+)?\n(.*?)```', response, re.DOTALL)

        files = {}
        file_counter = 0

        for lang, content in code_blocks:
            # Infer file type from language
            if lang == 'json':
                files[f"generated/file{file_counter}.json"] = content
            elif lang in ['python', 'py']:
                files[f"generated/file{file_counter}.py"] = content
            elif lang in ['typescript', 'tsx', 'ts']:
                files[f"generated/file{file_counter}.tsx"] = content
            else:
                files[f"generated/file{file_counter}.txt"] = content

            file_counter += 1

        return files
