# PDF Extraction Project — App4 (Docling + Gemini)

Extract specific information from PDFs using Docling (OCR + tables) and Gemini text model.  
**App4 is optimized for speed and cost, best for PDFs with structured tables and text.**

---

## Main Fields Extracted

- Service Type
- Services
- Title
- Airport
- Maximum Passengers Allowed
- Pricing (1-10 pax, adults/children)
- Travel Type
- Status
- Meeting Point
- Fast Track
- Service Details
- Transportation Inside Airport
- Assistance With Luggage
- Lounge Access
- Farewell
- Special Announcement
- Duration (minutes)
- Fee OOH
- Late Booking Fee
- USP
- Refund Policy (hours)

---

## Approach: Docling + Gemini Text Extraction

**File:** `app4.py`  
**Best for:**  
PDFs with structured tables, bullet points, and readable text.

---

### 🔧 Tools Used

- Docling (PDF parsing, OCR, tables)
- Gemini 2.0 Flash (Text Model)
- Streamlit
- ReportLab
- python-dotenv

---

### 🔄 Flow

1. **PDF → Docling:**  
   PDF is parsed using Docling, extracting text, tables, and layout as markdown.
2. **Docling → Gemini:**  
   Extracted markdown text is sent to Gemini with a strict JSON schema prompt.
3. **Gemini → Output:**  
   Gemini returns structured JSON with required fields. Missing fields = null.

---

### 👍 Pros

- Fast and cost-effective
- Handles tables and structured text well
- Works with most vendor PDFs
- No manual regex required

### 👎 Cons

- May miss purely visual data (images, flyers, screenshots)
- Requires API key
- Some accuracy loss on image-only PDFs

---

## Features

- **Frontend (Streamlit):**
  - Upload multiple PDF files
  - Each PDF processed individually
  - Results shown as JSON
  - Download as .txt or .pdf

---

## OUTPUT

- Structured JSON (all required fields)
- Human-readable text summary
- Download as TXT ✔
- Download as PDF ✔

---

## When to Use App4?

| Scenario                                      | Best Option |
|-----------------------------------------------|-------------|
| PDF has images, flyers, screenshots, brochures| App3 (Vision) |
| PDF has structured tables & text              | **App4 (Docling)** |
| You want cheapest & fastest                   | **App4 (Docling)** |

---

## Example Flow

```
User uploads PDFs → Docling parses PDF → Gemini extracts fields → JSON result → Download
```