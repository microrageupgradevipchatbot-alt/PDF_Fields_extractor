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
    "service Category": "", # "airport vip" or "transfer".
    "service name": "",# full name of that service 
    "Company_title": "", #  brand/company near the logo.
    "airport": "", #  # FULL airport name exactly as printed (e.g., "London Heathrow Airport(LHR)"). Never just IATA codes like LHR/JFK.
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
    "VAT": "", # VAT rate or details if present.
    "cancellation_policy": "", # Cancellation policy details if present.
    "travel_type": "",# "arrival" or "departure" or "both".
    "meeting_point": "",
    "fast_track": "no", # "yes" or "no" or "Expedited" .
    "service_details": [], # details of the service in bullet points.
    "transportation_inside_airport": "Foot", # "Foot" or "Vehicle". if not mentioned then put by default "Foot".
    "no.of_bags_assistance": "", # store ONLY the NUMBER of free checked bags/pieces per person (e.g., 2). DO NOT include text or units.
    "assistance_with_your_luggage": "", # store the FULL description of the luggage/baggage service, including free allowance and extra charges, VAT, and price if mentioned.
    "lounge_access": "no", # "yes" or "no". if not mentioned then put by default "no".
    "duration_minutes": "", # if written in hours so convert them in minutes.
    "fee_ooh": "", # Out of hours fee, mention time and price both if written.
    "late_booking_fee": "",
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

PRICING RULES - VERY IMPORTANT:
1. Extract BOTH adult AND child prices separately for EACH service
2. Look for phrases like "Price per child" or "Children (2-16yrs old)" 
3. Calculate multi-passenger pricing:
   - 1_pax adults = first person price
   - 1_pax children = child price (if stated separately otherwise put Null there).
   and son on....   

4. If child rate is same as additional person rate, use it. If different, extract the child-specific rate.
5. If child price is not mentioned Explicitly then, set it to null.
6. If price is written but not clear whom it applies whether child or adult then you must put it under 'service_details' also show the VAT if mentioned for that price.

service Category IDENTIFICATION:
- service Category: Extract the exact service name ( "vip" or "Transfer (Transit)").
- You must to put only "vip" or "transfer" in service_name field.

-> Airport VIP: Fast-track, meet & greet, lounge access, porter, concierge assistance at airports.
-> Airport Transfers: Private chauffeur service to/from airports with luxury vehicles.

- If PDF have both vip amd transfer than return multiple objects in the array
NOTE: service Category should be either vip or transfer. ALL the other services like chauffer, car parking etc details must go in 'service_details' field where description also goes.


travel_type IDENTIFICATION:
- if only arrival is mentioned then travel_type is "arrival"
- if only departure is mentioned then travel_type is "departure"
- if both arrival and departure mentioned then travel_type is "both"

Company_title IDENTIFICATION:
- Company_title must be the brand/company printed near the logo/header.
- If both brand and a generic header appear, return ONLY the brand.

BAGGAGE FIELDS EXTRACTION RULES:
- "no.of_bags_assistance": Extract ONLY the NUMBER of free checked bags/pieces per person (e.g., 2). DO NOT include any text, units, or descriptions.
- "assistance_with_your_luggage": Extract the FULL description of the luggage/baggage service, including the free allowance, extra charges, VAT, and price if mentioned. Example: "Two checked pieces per person Free of charge. Each additional piece of checked luggage 23% VAT and price €10.00."


OUTPUT FORMAT:
Return ONLY valid JSON array. No markdown, no backticks, no explanations.

Example for PDF with more than 1 services:
[
  {{"service_name": "Service 1", "pricing": {{"1_pax": {{"adults": 475, "children": 330}}, ...}}, ...}},
  {{"service_name": "Service 2", "pricing": {{"1_pax": {{"adults": 520, "children": 345}}, ...}}, ...}}
  
] 

Important: 
- You are strictly prohibited to invent any data not present in the PDF.
- Do not invent any data by yourself .



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
