import os
import json
from pypdf import PdfReader
from langchain_google_genai import GoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API")

def get_llm():
    llm = GoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,  # Replace with your actual API key or use env var
        temperature=0.7,
        max_output_tokens=512,
        timeout=30,
        max_retries=6,
    )
    return llm


def extract_text_from_pdf(pdf_file):
    """Reads all text from the PDF."""
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def extract_fields_ai(pdf_file):
    """
    1. Extract text from PDF
    2. Ask AI to extract fields: name, roll_no, date, class
    3. Return dictionary with null for missing values
    """

    text = extract_text_from_pdf(pdf_file)

    prompt = f"""
You are an AI data extractor. Extract the following fields from the PDF text:

- name
- roll_no
- date
- class

If any field is missing, return null.

Return the output strictly in this JSON format:

{{
  "name": "...",
  "roll_no": "...",
  "date": "...",
  "class": null
}}

Here is the PDF text:

{text}
"""

    llm = get_llm()
    response = llm.invoke(prompt)
    raw_output = response.strip()
    print("Raw AI Output:", raw_output)
    cleaned_output = raw_output.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned_output)
    except:
        data = {"error": "Invalid JSON from model", "raw": cleaned_output}

    return data
