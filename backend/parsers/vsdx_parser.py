"""
VSDX Parser
Extracts architecture components from VSDX/VDX files
"""
import zipfile
import io
from lxml import etree
from typing import Dict, List, Any

class VSDXParser:
    """Parser for VSDX and VDX diagram files"""

    def __init__(self):
        self.namespaces = {
            'visio': 'http://schemas.microsoft.com/office/visio/2012/main'
        }

    async def parse(self, content: bytes) -> Dict[str, Any]:
        """
        Parse VSDX file and extract architecture components

        Args:
            content: Raw VSDX file bytes

        Returns:
            Dictionary containing components, connections, and metadata
        """
        try:
            # VSDX is a zip file containing XML files
            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                # Read the page content (usually page1.xml)
                page_files = [f for f in zip_file.namelist() if 'page' in f.lower() and f.endswith('.xml')]

                if not page_files:
                    raise ValueError("No page content found in VSDX file")

                # Parse the first page
                page_content = zip_file.read(page_files[0])
                root = etree.fromstring(page_content)

                # Extract shapes (components)
                components = self._extract_shapes(root)

                # Extract connectors (data flows)
                connections = self._extract_connectors(root)

                return {
                    "components": components,
                    "connections": connections,
                    "metadata": {
                        "parser": "vsdx",
                        "page_count": len(page_files)
                    }
                }

        except Exception as e:
            # Fallback to basic structure
            return {
                "components": [],
                "connections": [],
                "metadata": {
                    "parser": "vsdx",
                    "error": str(e),
                    "fallback": True
                }
            }

    def _extract_shapes(self, root: etree.Element) -> List[Dict[str, Any]]:
        """Extract shape components from XML"""
        shapes = []

        # Find all shapes in the document
        for shape in root.xpath('.//visio:Shape', namespaces=self.namespaces):
            shape_id = shape.get('ID')

            # Get shape text/label
            text_elements = shape.xpath('.//visio:Text', namespaces=self.namespaces)
            text = text_elements[0].text if text_elements and text_elements[0].text else f"Component {shape_id}"

            # Get shape type from name or master
            shape_type = shape.get('Type', 'box')

            shapes.append({
                "id": shape_id,
                "label": text.strip() if text else "",
                "type": shape_type
            })

        return shapes

    def _extract_connectors(self, root: etree.Element) -> List[Dict[str, Any]]:
        """Extract connector relationships from XML"""
        connectors = []

        # Find all connectors
        for connect in root.xpath('.//visio:Connect', namespaces=self.namespaces):
            from_id = connect.get('FromSheet')
            to_id = connect.get('ToSheet')

            if from_id and to_id:
                connectors.append({
                    "from": from_id,
                    "to": to_id,
                    "type": "flow"
                })

        return connectors
