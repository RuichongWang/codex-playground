# Example: What Gets Generated

## Input Diagram (Conceptual)
```
User Input → LLM Joke Writer → Output
```

## Parsed Architecture (JSON)
```json
{
  "components": [
    {"id": "1", "label": "User Input", "type": "ui"},
    {"id": "2", "label": "LLM Joke Writer", "type": "llm"},
    {"id": "3", "label": "Output", "type": "ui"}
  ],
  "connections": [
    {"from": "1", "to": "2", "label": "user message"},
    {"from": "2", "to": "3", "label": "joke response"}
  ]
}
```

## Generated Files

The system would generate these files in a zip:

### Frontend Files
- `frontend/package.json` - React app dependencies
- `frontend/src/App.tsx` - Chat UI with input and output
- `frontend/src/index.css` - Styling
- `frontend/vite.config.ts` - Build config

### Backend Files
- `backend/main.py` - FastAPI with `/joke` endpoint
- `backend/requirements.txt` - Python dependencies (FastAPI, Anthropic)
- `backend/.env.example` - Template for API keys

### Example Generated Code Snippet

**backend/main.py:**
```python
from fastapi import FastAPI
from anthropic import Anthropic
import os

app = FastAPI()
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

@app.post("/api/joke")
async def generate_joke(message: dict):
    user_input = message.get("text", "")

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Write a funny joke about: {user_input}"
        }]
    )

    return {"joke": response.content[0].text}
```

**frontend/src/App.tsx:**
```tsx
function App() {
  const [input, setInput] = useState("")
  const [joke, setJoke] = useState("")

  const handleSubmit = async () => {
    const response = await axios.post("/api/joke", { text: input })
    setJoke(response.data.joke)
  }

  return (
    <div>
      <h1>Joke Generator</h1>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button onClick={handleSubmit}>Get Joke</button>
      <div>{joke}</div>
    </div>
  )
}
```

This would be a complete, runnable app!
