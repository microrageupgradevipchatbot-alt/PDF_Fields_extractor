# PDF Extraction Project Overview
Extract different PDF of various vendors to get specific information.

Main fields required are:
- Service Type
- Services
- Airport 
Maximum Passenger




## Techincal Details
### Installation

pip install pdfplumber
pip install reportlab

### Approach
Simple Text Extraction + Regex (Easiest / Fastest)

---
🔧 Tools:

pdfplumber / PyPDF2 -> extract_text_from_pdf

Python regex (re) -> extract_fields

---

🔄 Flow:
Input -> PDF -> Extract all text -> Run regex patterns ->
Found? value : null -> Output as JSON

---

👍 Pros:

Very easy
Very fast
Works offline

👎 Cons:

Fails if PDF layout is messy / images / scanned

### Features

- Frontend (streamlit)
- Can upload multiple pdf files
- Each file max size range is 200mb
- OUTPUT:
  2 Boxes
  - What did he extracted {}
  - In human format result.
- Also you can Copy, Download as .txt and .pdf .
