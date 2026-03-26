# app5.py - Enhanced Version
"""
Backend for extracting multiple services from PDF with proper child pricing.
Environment: GOOGLE_API_KEY in .env
"""

import os
import json
import google.generativeai as genai
import streamlit as st

api_key = st.secrets["API_KEY"]
if not api_key:
    raise RuntimeError("Please set API_KEY in Streamlit secrets.")
    
genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"
print("Using Gemini model:", MODEL_NAME)

def get_model():
    return genai.GenerativeModel(MODEL_NAME)

# Template for single service
SERVICE_TEMPLATE = {
    "service_name": "", # "airport vip" or "transfer".
    "service category": "", 
    "title": "", #title of the pdf document only.
    "airport": "", # airport name.
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
    "travel_type": "",# "arrival" or "departure" or "both".
    "meeting_point": "",
    "fast_track": "no", # "yes" or "no" or "Expedited" .
    "service_details": [], # details of the service in bullet points.
    "transportation_inside_airport": "Foot", # "Foot" or "Vehicle". if not mentioned then put by default "Foot".
    "assistance_with_pieces_of_luggage": "", 
    "lounge_access": "no", # "yes" or "no". if not mentioned then put by default "no".
    "farewell": "no",      # "yes" or "no"
    "duration_minutes": "", # if written in hours so convert them in minutes.
    "per_additional_hour_fee": "",     # fee + currency for each extra hour
    "fee_ooh": "", # Out of hours fee, mention time and price both if written.
    "late_booking_fee": "",
    "cancellation_policy": "",         # full cancellation tiers, e.g. "Free cancellation up to 24h, 50% charge within 12h" etc
    "vat_percentage": "",              # e.g. "10%", "20% included" etc
    "usp": "",
    "100% refund_policy_hours": ""
}

def _make_prompt():
    template_json = json.dumps(SERVICE_TEMPLATE, indent=2)
    
    prompt = f"""
You are extracting service information from a PDF. The PDF may contain MULTIPLE SERVICES i.e airport vip , transfer.

IMPORTANT: Return a JSON ARRAY with one object for each service found.

Each service object must follow this template:
{template_json}

**PRICING RULES - VERY IMPORTANT:**
1. Extract BOTH adult AND child prices separately for EACH service
2. Look for phrases like "Price per child" or "Children (2-16yrs old)" 
3. Calculate multi-passenger pricing:
   - 1_pax adults = first person price
   - 1_pax children = child price (if stated separately otherwise put Null there).
   and son on....   

4. If child rate is same as additional person rate, use it. If different, extract the child-specific rate.
5. If child price is not mentioned Explicitly then, set it to null.
6. If price is written but not clear whom it applies whether child or adult then you must put it under 'service_details' also show the VAT if mentioned for that price.

**SERVICE IDENTIFICATION:**
- service_name: Extract the exact service name ( "vip" or "Transfer (Transit)").
- If PDF have both vip amd transfer than return multiple objects in the array
NOTE: service_name should be either vip or tranfser other services like chauffer, car parking etc details should go in 'service_details' field where description also go.

**travel_type IDENTIFICATION:**
- if only arrival is mentioned then travel_type is "arrival"
- if only departure is mentioned then travel_type is "departure"
- if both arrival and departure mentioned then travel_type is "both"

farewell: "yes" if service mentions farewell/send-off, else "no".
cancellation_policy: Extract full policy with all tiers/windows. If absent, null.
100% refund_policy_hours: Extract only the full-refund window in hours.
vat_percentage: Extract exact VAT % stated (e.g. "10%", "20% included"). If absent, null. Do NOT invent.
per_additional_hour_fee: Extract fee per extra hour with currency (e.g. "€50"). If absent, null.

**OUTPUT FORMAT:**
Return ONLY valid JSON array. No markdown, no backticks, no explanations.

Example for PDF with more than 1 services:
[
  {{"service_name": "Service 1", "pricing": {{"1_pax": {{"adults": 475, "children": 330}}, ...}}, ...}},
  {{"service_name": "Service 2", "pricing": {{"1_pax": {{"adults": 520, "children": 345}}, ...}}, ...}}
  
] 

**Important:**
- Every service object MUST contain ALL fields from the template. No field may be omitted.
- For every field, actively search the PDF before setting null.
- You are strictly prohibited from inventing any data not present in the PDF.


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
    # NEW CODE:
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
            return {"error": "quota_exceeded", "detail": "Quota is over for the API key"}
        return {"error": "model_call_failed", "detail": error_msg}
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

def flag_missing_fields(service_list):
    """
    Returns a list of dicts, each with missing/incomplete fields for a service.
    """
    missing_info = []
    for idx, service in enumerate(service_list):
        missing_fields = []
        for key, value in service.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    if isinstance(subval, dict):
                        for subsubkey, subsubval in subval.items():
                            if subsubval in [None, "", [], {}]:
                                missing_fields.append(f"{key}.{subkey}.{subsubkey}")
                    elif subval in [None, "", [], {}]:
                        missing_fields.append(f"{key}.{subkey}")
            elif value in [None, "", [], {}]:
                missing_fields.append(key)
        missing_info.append({
            "service_index": idx,
            "service_name": service.get("service_name", f"Service {idx+1}"),
            "missing_fields": missing_fields
        })
    return missing_info
