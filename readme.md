# PDF Extraction Project Overview
Extract different PDF of various vendors to get specific information.

Main fields required are:
- Service Type
- Services
- Airport 
Maximum Passenger



### Approach: AI Vision Extraction (Using LLM: Gemini)
File: app.py
⭐ Best for:

PDFs that contain images, tables, mixed formatting, or different templates.

### 🔧 Tools:

Gemini 2.5 Flash (Vision Model)
Streamlit
ReportLab
python-dotenv

### 🔄 Flow:

PDF → Send full file to Gemini Vision →
LLM reads images + text →
Returns structured JSON → Missing fields = null

👍 Pros:

Works with ANY layout (images + text)
Super accurate
No regex or OCR required

👎 Cons:

Needs API key
Costs per request


### Features
Frontend (Streamlit)
Upload multiple PDF files
Works even if PDF contains only images

### OUTPUT:
JSON (structured fields)
Human formatted text
Copy result ✔
Download as .txt ✔
Download as .pdf ✔