### Approach: AI Extraction (Using LLM: Gemini)

⭐ Best for:

PDFs with unpredictable format or different templates.

---

🔧 Tools:

OpenAI GPT-4o / GPT-5
Gemini 2.0 Flash / Pro
Llama 3.1
etc

---

🔄 Flow:
PDF -> Extract text -> Send to LLM ->
LLM returns structured JSON with fields -> Fill missing with null

---

👍 Pros:

Works for ANY layout
No regex needed
Very accurate

👎 Cons:

Needs API key
Costs a bit

### Features

- Frontend (streamlit)
- Can upload multiple pdf files
- Each file max size range is 200mb
- OUTPUT:
  2 Boxes
  - What did he extracted {}
  - In human format result.
- Also you can Copy, Download as .txt and .pdf .
