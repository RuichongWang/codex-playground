"""
Image Parser
Uses Claude Vision API to extract architecture from PNG/JPG diagrams
"""
import base64
import os
from typing import Dict, List, Any
import anthropic

class ImageParser:
    """Parser for image-based diagrams (PNG, JPG) using Claude Vision"""

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    async def parse(self, content: bytes) -> Dict[str, Any]:
        """
        Parse image diagram using Claude Vision API

        Args:
            content: Raw image file bytes

        Returns:
            Dictionary containing components, connections, and metadata
        """
        try:
            # Encode image to base64
            image_base64 = base64.standard_b64encode(content).decode('utf-8')

            # Create vision prompt
            prompt = """Analyze this system architecture diagram and extract:
1. Components (boxes, services, systems) - identify each component with a unique ID and label
2. Connections (arrows, flows) - identify data/control flow between components
3. Any labels or annotations on connections

Return the analysis in this JSON format:
{
  "components": [
    {"id": "comp1", "label": "Component Name", "type": "service/ui/database/llm/other"}
  ],
  "connections": [
    {"from": "comp1", "to": "comp2", "label": "description of flow"}
  ]
}

Be precise and include all components and connections you can identify."""

            # Call Claude Vision API
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )

            # Extract response
            response_text = message.content[0].text

            # Parse JSON from response (handle markdown code blocks)
            import json
            import re

            # Try to extract JSON from response
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                architecture = json.loads(json_match.group(1))
            else:
                # Try to parse as direct JSON
                architecture = json.loads(response_text)

            # Add metadata
            architecture["metadata"] = {
                "parser": "image_vision",
                "model": "claude-3-5-sonnet-20241022"
            }

            return architecture

        except Exception as e:
            # Return error structure
            return {
                "components": [],
                "connections": [],
                "metadata": {
                    "parser": "image_vision",
                    "error": str(e),
                    "fallback": True
                }
            }
