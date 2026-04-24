# app_v2.py — PDF Extractor Backend (v4)
# ─────────────────────────────────────────────────────────────────────────────
# CHANGES vs v3:
#   • Removed per-model retry loop — replaced with model fallback chain
#   • FALLBACK_MODELS: 2.5-flash → 2.5-pro → 3.1-flash-image-preview → 2.0-flash
#   • Each model gets ONE clean attempt; failures move to next model
#   • Retryable errors (503, 429, 500) trigger fallback; others abort immediately
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import time
import random
# from dotenv import load_dotenv
from google import genai
from google.genai import types

import streamlit as st
# ── ENV ───────────────────────────────────────────────────────────────────────
# load_dotenv()
# api_key = os.getenv("GOOGLE_API")
api_key = st.secrets["GOOGLE_API"]
if not api_key:
    raise RuntimeError("Please set GOOGLE_API in your environment (.env).")

print("🔑 [Init] Loaded environment variables and API key.")


# ── MODEL FALLBACK CHAIN ──────────────────────────────────────────────────────
FALLBACK_MODELS = [
    "gemini-2.5-flash",                  # 🥇 Primary   — best speed + multimodal PDF
    "gemini-3.1-flash-image-preview",    # 🥉 Fallback 2 — image-specialized, scanned PDFs
    "gemini-2.5-pro",                    # 🥈 Fallback 1 — stronger reasoning, complex layouts
    "gemini-2.0-flash",                  # 4️⃣ Fallback 3 — rock solid, almost never 503s
]

print(f"🔗 [Init] Model fallback chain loaded — {len(FALLBACK_MODELS)} models ready.")


# ── CLIENT ────────────────────────────────────────────────────────────────────
def get_client():
    print("🤖 [Gemini] Creating Gemini client instance.")
    return genai.Client(api_key=api_key)


# ── SERVICE TEMPLATE ──────────────────────────────────────────────────────────
SERVICE_TEMPLATE = {
    "service_name": "",
    "service_category": "",
    "title": "",
    "airport": "",
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
        "10_pax": {"adults": None, "children": None},
    },
    "travel_type": "",        # "arrival" | "departure" | "transfer" — never "both"
    "meeting_point": "",
    "fast_track": {
        "departure": {
            "security": None  # "fast track" | "expedited" | "assistance" | "no assistance" | null
        },
        "arrival": {
            "immigration": None,
            "customs":     None,
        }
    },
    "service_details": [],
    "transportation_inside_airport": "Foot",   # "Foot" | "Vehicle"
    "assistance_with_pieces_of_luggage": "",
    "lounge_access": "no",
    "farewell": "no",
    "duration_minutes": "",
    "per_additional_hour_fee": "",
    "fee_ooh": "",
    "late_booking_fee": "",
    "cancellation_policy": "",
    "vat_percentage": "",
    "usp": "",
    "100%_refund_policy_hours": ""
}


# ── PROMPT ────────────────────────────────────────────────────────────────────
def _make_prompt() -> str:
    print("📝 [Prompt] Building extraction prompt.")
    template_json = json.dumps(SERVICE_TEMPLATE, indent=2)

    return f"""
You are extracting airport VIP service information from a single PDF document.

Return a JSON ARRAY where each element is ONE service for ONE travel direction.

Each object must follow this template exactly:
{template_json}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — ARRIVAL / DEPARTURE SPLIT  ⚠️ CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- travel_type must be EXACTLY one of: "arrival" | "departure" | "transfer"
- The value "both" is STRICTLY FORBIDDEN. Never use it.

- If a service applies to BOTH arrival and departure:
    → Create TWO objects: one travel_type="arrival", one travel_type="departure"
    → Name them clearly: e.g. "VIP Arrival" and "VIP Departure"
    → If pricing is shared (e.g. "each way €475"): copy same pricing into both objects
    → If pricing differs per direction: use correct price for each object
    → Fill meeting_point, farewell, fast_track, service_details
      with direction-specific info for each object

- Transfer / Transit services → travel_type = "transfer"

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
      "security": <value>
    }},
    "arrival": {{
      "immigration": <value>,
      "customs":     <value>
    }}
  }}

Allowed values:
  "fast track" | "expedited" | "assistance" | "no assistance" | null

Direction rules:
  • ARRIVAL object   → fill arrival.immigration + arrival.customs; departure.security = null
  • DEPARTURE object → fill departure.security; arrival fields = null
  • TRANSFER object  → fill all three if mentioned

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — PRICING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 1_pax adults  = price for the first / only person
- 2_pax adults  = cumulative total for 2 people
  … continue cumulatively per tier
- children: extract ONLY if explicitly stated; otherwise null

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4 — GENERAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Every object MUST contain ALL template fields — no field may be omitted
- Do NOT invent data not present in this PDF
- cancellation_policy: include full tiers if available
- 100%_refund_policy_hours: full-refund window in hours only
- vat_percentage: exact % or null
- per_additional_hour_fee: fee + currency (e.g. "€50") or null
- duration_minutes: convert hours to minutes if needed

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON array. No markdown, no backticks, no explanation text.

Now extract ALL services from this PDF.
"""


# ── EXTRACTION — MODEL FALLBACK CHAIN ────────────────────────────────────────
def extract_fields_ai(pdf_file) -> list | dict:
    filename = getattr(pdf_file, "name", "unknown")
    print(f"\n📄 [Extract] Starting extraction for: {filename}")

    pdf_bytes = pdf_file.read()
    mime_type = getattr(pdf_file, "type", "application/pdf")
    client    = get_client()
    prompt    = _make_prompt()

    # Retryable error signals — these trigger fallback to next model
    RETRYABLE = ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL")

    for idx, model in enumerate(FALLBACK_MODELS):
        position = f"{idx + 1}/{len(FALLBACK_MODELS)}"
        print(f"\n🚀 [Gemini] Trying model {position}: {model}")

        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=pdf_bytes, mime_type=mime_type),
                            types.Part.from_text(text=prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(temperature=0)
            )
            raw = response.text.strip()

            print(f"✅ [Gemini] Success with model: {model}")

        except Exception as e:
            err_str = str(e)

            # Check if this error is worth falling back for
            is_retryable = any(code in err_str for code in RETRYABLE)

            if not is_retryable:
                # Hard error (auth, bad request etc.) — no point trying other models
                print(f"💀 [Gemini] Non-retryable error on {model} — aborting.")
                print(f"   ↳ {err_str}")
                return {"error": "model_call_failed", "detail": err_str}

            # Soft error — try next model
            if idx + 1 < len(FALLBACK_MODELS):
                next_model = FALLBACK_MODELS[idx + 1]
                delay = round(random.uniform(1, 3), 1)
                print(f"⚠️  [Gemini] {model} failed — moving to next model.")
                print(f"   ↳ Reason    : {err_str[:80]}")
                print(f"   ↳ Next model: {next_model}")
                print(f"   ↳ Waiting   : {delay}s...")
                time.sleep(delay)
            else:
                print(f"🛑 [Gemini] All {len(FALLBACK_MODELS)} models failed — giving up.")
                print(f"   ↳ Last error: {err_str}")
                return {"error": "all_models_failed", "detail": err_str}

            continue  # move to next model in loop

        # ── PARSE ─────────────────────────────────────────────────────────────
        print(f"🔍 [Parser] Parsing response from {model}...")
        cleaned = raw.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                parsed = [parsed]
            print(f"🎉 [Parser] Parsed {len(parsed)} service(s) successfully!")
            return parsed

        except json.JSONDecodeError as e:
            print(f"💥 [Parser] JSON parse failed from {model}.")
            print(f"   ↳ Error : {str(e)}")
            print(f"   ↳ Raw   : {cleaned[:200]}{'...' if len(cleaned) > 200 else ''}")
            return {"error": "invalid_json", "raw": cleaned, "detail": str(e)}

    # Should never reach here but just in case
    return {"error": "all_models_failed", "detail": "Exhausted all models in fallback chain."}


# ── MISSING FIELD CHECKER ─────────────────────────────────────────────────────
def flag_missing_fields(service_list: list) -> list:
    """
    Recursively walks each service and reports fields that are
    null / empty string / empty list / empty dict.

    Returns:
      [{"service_index": int, "service_name": str, "missing_fields": [str]}]
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
            "service_index":  idx,
            "service_name":   service.get("service_name", f"Service {idx + 1}"),
            "missing_fields": _collect_missing(service)
        })
    return result
