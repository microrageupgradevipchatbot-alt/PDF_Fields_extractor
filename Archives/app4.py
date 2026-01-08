# 🏆 Final Verdict
# Scenario	Best Option
# PDF has images, flyers, screenshots, brochures	App3 (Vision)
# PDF has structured tables & text (pricing, bullet points)	App4 (Docling)
# You want cheapest & fastest	App4

# app4.py
"""
APP4: Extracts fields using Docling (PDF parsing + OCR) + Gemini text model.
This is cheaper and faster than Vision-only approach (App3),
but may slightly miss visual-only data that Vision reads.
"""

import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from docling.document_converter import DocumentConverter

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API")

if not GOOGLE_API_KEY:
    raise RuntimeError("Please set GOOGLE_API_KEY in .env")

genai.configure(api_key=GOOGLE_API_KEY)

MODEL_NAME = "gemini-2.0-flash"   # Text model works fine here


def get_model():
    return genai.GenerativeModel(MODEL_NAME)


# SAME JSON structure as client gave us 
JSON_TEMPLATE = {
    "service_type": "",
    "services": "",
    "title": "",
    "airport": "",
    "max_passengers_allowed": "",
    "pricing": {
        "1_pax": {"adults": None, "children": None},
        "2_pax": {"adults": None, "children": None},
        "3_pax": {"adults": None, "children": None},
        "4_pax": {"adults": None, "children": None},
        "5_pax": {"adults": None, "children": None},
        "6_pax": {"adults": None, "children": None},
        "7_pax": {"adults": None, "children": None},
        "8_pax": {"adults": None, "children": None},
        "9_pax": {"adults": None, "children": None},
        "10_pax": {"adults": None, "children": None}
    },
    "travel_type": "",
    "status": "",
    "meeting_point": "",
    "fast_track": "",
    "service_details": [],
    "transportation_inside_airport": "",
    "assistance_with_pieces_of_luggage": "",
    "lounge_access": "",
    "farewell": "",
    "special_announcement": "",
    "duration_minutes": None,
    "fee_ooh": "",
    "late_booking_fee": "",
    "usp": "",
    "refund_policy_hours": None
}

# what does extract_docling_text do?
# Uses Docling's DocumentConverter to process the PDF file.
# Handles tables, OCR (Optical Character Recognition), and layouts.
# Converts the PDF content into markdown text (including text, tables, and images as text).
# Returns the extracted markdown text.

def extract_docling_text(pdf_file):
    """
    Converts the PDF into markdown using Docling.
    Handles tables, OCR, layouts.
    """
    converter = DocumentConverter()
    doc = converter.convert(pdf_file)
    return doc.document.export_to_markdown()

# What extract_fields_ai_docling Does
# Step 1: Converts the PDF to markdown/text using Docling (OCR + tables):
# Step 2: Prepares a prompt with the strict JSON schema and the extracted text.
# Step 3: Sends the prompt to Gemini (Google Generative AI) to extract the required fields as JSON.
# Step 4: Parses the response and returns the JSON result.
def extract_fields_ai_docling(pdf_file):
    """
    Main function App4 calls:
    1. Parse PDF → text via Docling
    2. Send parsed text to Gemini
    3. Return cleaned JSON dict
    """

    parsed_text = extract_docling_text(pdf_file)

    template_json = json.dumps(JSON_TEMPLATE, indent=2)

    prompt = f"""
You are an expert data extractor. Below is text extracted from a PDF using Docling.
Extract and return JSON strictly matching this schema.
Missing values = null.

Template:
{template_json}

TEXT:
{parsed_text}
"""

    model = get_model()

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        return json.loads(raw)

    except Exception as e:
        return {"error": "invalid_json_or_model_failure", "detail": str(e), "raw": raw}
