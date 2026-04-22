# app_v2.py — PDF Extractor Backend (v3)
# ─────────────────────────────────────────────────────────────────────────────
# CHANGES vs previous version:
#   FIX 1 → Services that cover both arrival AND departure are now split into
#            TWO separate objects (one per direction). travel_type="both" is
#            banned — Gemini is explicitly told never to use it.
#
#   FIX 2 → extract_fields_ai() still accepts ONE pdf file at a time.
#            The Streamlit frontend calls it once per uploaded PDF in parallel
#            (ThreadPoolExecutor). Results are returned as a list of
#            (filename, result) tuples so the UI can show a header per file.
#
#   FIX 3 → fast_track is now a structured dict instead of a plain string:
#            {
#              "departure": { "security": <value> },
#              "arrival":   { "immigration": <value>, "customs": <value> }
#            }
#            Allowed values: "fast track" | "expedited" | "assistance" |
#                            "no assistance" | null
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

# ── ENV & MODEL ───────────────────────────────────────────────────────────────
load_dotenv()
api_key = os.getenv("GOOGLE_API")
if not api_key:
    raise RuntimeError("Please set GOOGLE_API in your environment (.env).")

genai.configure(api_key=api_key)
MODEL_NAME = "gemini-2.5-flash"
print(f"[Backend] Using model: {MODEL_NAME}")


def get_model():
    return genai.GenerativeModel(MODEL_NAME)


# ── SERVICE TEMPLATE ──────────────────────────────────────────────────────────
# FIX 3: fast_track is now a nested dict, not a plain "yes/no" string.
# FIX 1: travel_type is "arrival" | "departure" | "transfer" — never "both".
SERVICE_TEMPLATE = {
    "service_name": "",          # e.g. "VIP Arrival", "VIP Departure", "Transfer"
    "service_category": "",
    "title": "",                 # Title of the PDF document
    "airport": "",               # Airport name / code
    "pricing": {
        "1_pax":  {"adults": None, "children": None},
        "2_pax":  {"adults": None, "children": None},
        "3_pax":  {"adults": None, "children": None},
        "4_pax":  {"adults": None, "children": None},
        "5_pax":  {"adults": None, "children": None},
        "6_pax":  {"adults": None, "children": None},
        "7_pax":  {"adults": None, "children": None},
        "8_pax":  {"adults": None, "children": None},
        "9_pax":  {"adults": None, "children": None},
        "10_pax": {"adults": None, "children": None}
    },
    
    "travel_type": "",
    "meeting_point": "",

    
    "fast_track": {
        "departure": {
            # Allowed: "fast track" | "expedited" | "assistance" | "no assistance" | null
            "security": None
        },
        "arrival": {
            "immigration": None,   # same allowed values
            "customs":     None    # same allowed values
        }
    },

    "service_details": [],
    "transportation_inside_airport": "Foot",   # "Foot" | "Vehicle"
    "assistance_with_pieces_of_luggage": "",
    "lounge_access": "no",         # "yes" | "no"
    "farewell": "no",              # "yes" | "no"
    "duration_minutes": "",
    "per_additional_hour_fee": "",
    "fee_ooh": "",
    "late_booking_fee": "",
    "cancellation_policy": "",
    "vat_percentage": "",
    "usp": "",
    "100%_refund_policy_hours": ""
}


# ── PROMPT BUILDER ────────────────────────────────────────────────────────────
def _make_prompt() -> str:
    template_json = json.dumps(SERVICE_TEMPLATE, indent=2)

    return f"""
You are extracting airport VIP service information from a single PDF document.

Return a JSON ARRAY where each element is ONE service for ONE travel direction.

Each object must follow this template exactly:
{template_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — ARRIVAL / DEPARTURE SPLIT  ⚠️ CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• travel_type must be EXACTLY one of: "arrival" | "departure" | "transfer"
• The value "both" is STRICTLY FORBIDDEN. Never use it.

• If a service applies to BOTH arrival and departure:
    → Create TWO objects: one travel_type="arrival", one travel_type="departure"
    → Name them clearly: e.g. "VIP Arrival" and "VIP Departure"
    → If pricing is shared (e.g. "each way €475"): copy same pricing into both objects
    → If pricing differs per direction: use correct price for each object
    → Fill meeting_point, farewell, fast_track, service_details
      with direction-specific info for each object

• Transfer / Transit services → travel_type = "transfer"

Example — PDF says "Departure or Arrival €475 per person":
[
  {{"service_name": "VIP Arrival",    "travel_type": "arrival",    "pricing": {{"1_pax": {{"adults": 475}} }} }},
  {{"service_name": "VIP Departure",  "travel_type": "departure",  "pricing": {{"1_pax": {{"adults": 475}} }} }}
]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2 — STRUCTURED fast_track  ⚠️ CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
fast_track is a NESTED OBJECT — not a string, not "yes/no".

  "fast_track": {{
    "departure": {{
      "security": <value>          ← security lane / checkpoint at departure
    }},
    "arrival": {{
      "immigration": <value>,      ← passport control / immigration at arrival
      "customs":     <value>       ← customs checkpoint at arrival
    }}
  }}

Allowed values for every sub-field (use EXACTLY one of these):
  "fast track"    → supplier explicitly provides fast track / priority lane
  "expedited"     → supplier uses "expedited" or similar accelerated wording
  "assistance"    → agent assists the passenger through checkpoint (no dedicated lane)
  "no assistance" → document explicitly states no assistance at this checkpoint
  null            → not mentioned anywhere in this PDF

Direction rules:
  • For an ARRIVAL object    → fill arrival.immigration + arrival.customs;
                               set departure.security = null
  • For a DEPARTURE object   → fill departure.security;
                               set arrival.immigration = null, arrival.customs = null
  • For a TRANSFER object    → fill all three if the PDF mentions them

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — PRICING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 1_pax adults  = price for the first / only person
• 2_pax adults  = price for 1st person + 1 additional person (cumulative total)
  … continue cumulatively for each pax tier
• children: extract ONLY if explicitly stated; otherwise null
• If child price is unclear or mixed with adult pricing, put it in service_details

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4 — GENERAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• service_name: use "vip" or "transfer" as the base; chauffeur/parking/lounge
  add-ons go into service_details, not as separate top-level services
• Every object MUST contain ALL template fields — no field may be omitted
• Do NOT invent data not present in this PDF
• cancellation_policy: include full tiers if available
• 100%_refund_policy_hours: extract only the full-refund window in hours
• vat_percentage: extract exact % stated; if absent → null
• per_additional_hour_fee: fee + currency (e.g. "€50"); if absent → null
• duration_minutes: convert hours to minutes if needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON array. No markdown, no backticks, no explanation text.

Now extract ALL services from this PDF.
"""


# ── MAIN EXTRACTION FUNCTION ──────────────────────────────────────────────────
# FIX 2: Still accepts ONE pdf_file at a time.
#         The frontend calls this function once per uploaded PDF,
#         running them in parallel via ThreadPoolExecutor.
def extract_fields_ai(pdf_file) -> list | dict:
    """
    Extract service info from a single PDF file object.

    Args:
        pdf_file: A file-like object with .read() and optionally .type attribute.
                  (Streamlit UploadedFile works directly.)

    Returns:
        list  → success: list of service dicts
        dict  → failure: {"error": ..., "detail": ..., "raw": ...}
    """
    print(f"[extract_fields_ai] Processing: {getattr(pdf_file, 'name', 'unknown')}")

    # Read raw bytes
    pdf_bytes = pdf_file.read()
    mime_type = getattr(pdf_file, "type", "application/pdf")

    model  = get_model()
    prompt = _make_prompt()

    # ── Call Gemini ───────────────────────────────────────────────────────────
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
            generation_config={"temperature": 0.1}
        )
    except Exception as e:
        print(f"[extract_fields_ai] Gemini call failed: {e}")
        return {"error": "model_call_failed", "detail": str(e)}

    # ── Parse response ────────────────────────────────────────────────────────
    raw = response.text.strip()
    print(f"[extract_fields_ai] Raw response (first 300 chars): {raw[:300]}")

    # Strip markdown code fences if Gemini added them
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
        # Normalise: always return a list
        if isinstance(parsed, dict):
            parsed = [parsed]
        print(f"[extract_fields_ai] Parsed {len(parsed)} service(s).")
        return parsed

    except json.JSONDecodeError as e:
        print(f"[extract_fields_ai] JSON parse error: {e}")
        return {"error": "invalid_json", "raw": cleaned, "detail": str(e)}


# ── MISSING FIELD CHECKER ─────────────────────────────────────────────────────
def flag_missing_fields(service_list: list) -> list:
    """
    Walk each service dict recursively and report fields that are
    null / empty string / empty list / empty dict.

    Returns a list of dicts:
      [{"service_index": int, "service_name": str, "missing_fields": [str, ...]}]
    """
    def _collect_missing(obj, prefix=""):
        missing = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (dict, list)):
                    missing.extend(_collect_missing(v, path))
                elif v in (None, "", [], {}):
                    missing.append(path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                missing.extend(_collect_missing(item, f"{prefix}[{i}]"))
        return missing

    result = []
    for idx, service in enumerate(service_list):
        result.append({
            "service_index": idx,
            "service_name":  service.get("service_name", f"Service {idx + 1}"),
            "missing_fields": _collect_missing(service)
        })
    return result
