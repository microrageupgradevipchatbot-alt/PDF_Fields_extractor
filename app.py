# app5.py - Enhanced Version
"""
Backend for extracting multiple services from PDF with proper child pricing.
Environment: GOOGLE_API_KEY in .env
"""

import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API")
if not api_key:
    raise RuntimeError("Please set GOOGLE_API_KEY in your environment (or .env).")

genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"
print("Using Gemini model:", MODEL_NAME)

def get_model():
    return genai.GenerativeModel(MODEL_NAME)

# Template for single service
SERVICE_TEMPLATE = {
    "service_name": "", # anmep of the particular service.
    "title": "", #title of the pdf document.
    "airport": "", # airport name.
    "max_passengers_allowed": None,
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
    "travel_type": "",# arrival or departure or transfer etc.
    "status": "", # active or non-active 
    "meeting_point": "",
    "fast_track": "", # yes or no or Expedited
    "service_details": [], # details of the service in bullet points.
    "transportation_inside_airport": "", # Foot or Vehicle
    "assistance_with_pieces_of_luggage": "", 
    "lounge_access": "", # yes or no
    "farewell": "",
    "special_announcement": "",
    "duration_minutes": None,
    "fee_ooh": "",
    "late_booking_fee": "",
    "usp": "",
    "refund_policy_hours": None
}

def _make_prompt():
    template_json = json.dumps(SERVICE_TEMPLATE, indent=2)
    
    prompt = f"""
You are extracting service information from a PDF. The PDF may contain MULTIPLE SERVICES.

IMPORTANT: Return a JSON ARRAY with one object for each service found.

Each service object must follow this template:
{template_json}

PRICING RULES - VERY IMPORTANT:
1. Extract BOTH adult AND child prices separately for EACH service
2. Look for phrases like "Price per child" or "Children (2-16yrs old)" 
3. Calculate multi-passenger pricing:
   - 1_pax adults = first person price
   - 1_pax children = child price (if stated separately otherwise put Null there).
   and son on....   

4. If child rate is same as additional person rate, use it. If different, extract the child-specific rate.
5. If child price is not mentioned, set it to null.
6. If price is written but not clear whom it applies whether child or adult then you must put it under 'service_details' also show the VAT if mentioned for that price.

SERVICE IDENTIFICATION:
- service_name: Extract the exact service name (e.g., "Departure or Arrival", "Transfer (Transit)", etc).
- If PDF has more than 1 services with different prices, return multiple objects in the array
- If PDF has 1 service, return 1 object in the array


OUTPUT FORMAT:
Return ONLY valid JSON array. No markdown, no backticks, no explanations.

Example for PDF with more than 1 services:
[
  {{"service_name": "Service 1", "pricing": {{"1_pax": {{"adults": 475, "children": 330}}, ...}}, ...}},
  {{"service_name": "Service 2", "pricing": {{"1_pax": {{"adults": 520, "children": 345}}, ...}}, ...}}
  ...
] and so on.

Important: 
- Do not invent or assume any data by yourself and try to write it if its not present i.e "Terms & Conditions apply."
Rates subject to change.
Note: amounts are to nearest euro, decimal charge may apply. etc.
- if price is only written without any clarity whom it applies whether child or adult
  then you must put it under 'service_details' also show the VAT if mentioned for that price.
- 'service_details' must start with 1,2 and son on ...
  ---

Now extract ALL services from the PDF.

"""
    return prompt

def extract_fields_ai(pdf_file):
    """
    Main extraction function.
    Returns: List of service dicts or error dict
    """
    pdf_bytes = pdf_file.read()
    mime_type = getattr(pdf_file, "type", "application/pdf")

    model = get_model()
    prompt = _make_prompt()

    try:
        response = model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [
                        {"mime_type": mime_type, "data": pdf_bytes},
                        {"text": prompt}
                    ]
                }
            ],
            generation_config={
                "temperature": 0.1,
                #"max_output_tokens": 8192,
            }
        )
    except Exception as e:
        return {"error": "model_call_failed", "detail": str(e)}

    # Extract response text
    print("Raw response:", response)
    cleaned = response.text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    print("Cleaned response:", cleaned)
    # Parse JSON
    try:
        parsed = json.loads(cleaned)
        
        # Ensure array format
        if isinstance(parsed, dict):
            parsed = [parsed]
        
        return parsed
    except json.JSONDecodeError as e:
        return {"error": "invalid_json", "raw": cleaned, "detail": str(e)}