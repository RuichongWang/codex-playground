# Testing the Enhanced Coding Agent

## Quick Test Example

Create a simple diagram in Lucidchart with these components:

### Example 1: Joke Generator (Your Original Idea)
```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│ User Input  │─────▶│ LLM Joke     │─────▶│   Output    │
│             │      │ Generator    │      │  Display    │
└─────────────┘      └──────────────┘      └─────────────┘
```

**Components:**
1. **User Input** (type: UI)
2. **LLM Joke Generator** (type: LLM)
3. **Output Display** (type: UI)

**Connections:**
- User Input → LLM Joke Generator (label: "user message")
- LLM Joke Generator → Output Display (label: "joke response")

### Example 2: Todo App
```
┌──────────┐    ┌───────────┐    ┌──────────┐
│   UI     │───▶│  Backend  │───▶│  Storage │
│  Form    │    │    API    │    │ (Memory) │
└──────────┘    └───────────┘    └──────────┘
```

**Components:**
1. **UI Form** (type: UI)
2. **Backend API** (type: API)
3. **Storage** (type: Database)

### Example 3: AI Chat with History
```
┌────────┐    ┌─────────┐    ┌───────┐    ┌─────────┐
│  User  │───▶│ Process │───▶│  LLM  │───▶│ Display │
│ Input  │    │ History │    │       │    │         │
└────────┘    └─────────┘    └───────┘    └─────────┘
```

## How to Export from Lucidchart

1. Create your diagram in Lucidchart
2. Go to **File → Download As**
3. Choose **VSDX** (recommended) or export as PNG
4. Upload the file to the Enhanced Coding Agent

## Expected Output

The system will generate:
- **React Frontend**: Complete UI with components for each box
- **Python Backend**: FastAPI endpoints for each connection
- **LLM Integration**: Claude API calls for LLM-labeled components
- **Working Code**: Ready to run with `npm install && npm run dev`

## Testing Without a Diagram

If you don't have Lucidchart, you can create a simple PNG with any drawing tool:
1. Draw boxes with clear labels
2. Draw arrows between them
3. Save as PNG
4. Upload (Claude Vision will parse it)

## Troubleshooting

**VSDX parsing fails?**
- Try PNG upload as fallback
- Make sure Lucidchart export is VSDX format

**Generation takes too long?**
- Complex diagrams may take 30-60 seconds
- Check your ANTHROPIC_API_KEY is set correctly

**Generated code has errors?**
- Start with simple 3-component diagrams
- Use clear, descriptive labels
- Ensure LLM components are clearly marked

## Next Steps After Download

1. Extract the generated ZIP file
2. Follow the README in the generated app
3. Install dependencies: `npm install` (frontend) and `pip install -r requirements.txt` (backend)
4. Add ANTHROPIC_API_KEY to backend/.env if app uses LLM
5. Run: `npm run dev` (frontend) and `uvicorn main:app` (backend)
