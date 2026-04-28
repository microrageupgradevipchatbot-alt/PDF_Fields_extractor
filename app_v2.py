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
    # "models/gemini-2.5-flash",              # Fast, supports PDF/image
    # "models/gemini-2.5-flash-image",        # Explicit image support
    "models/gemini-3.1-flash-image-preview",# Newest, image-specialized
    "models/gemini-3-pro-image-preview",    # Advanced, image-specialized
]

MODEL_TIMEOUT_SECONDS = 30   # PDF extraction needs time — 30s was too short

print(f"🔗 [Init] Model fallback chain: {FALLBACK_MODELS}")


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
    "travel_type": "",
    "meeting_point": "",
    "fast_track": {
        "departure": {"security": None},
        "arrival":   {"immigration": None, "customs": None}
    },
    "service_details": [],
    "transportation_inside_airport": "Foot",
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
    → If pricing is shared: copy same pricing into both objects
    → Fill meeting_point, farewell, fast_track, service_details with direction-specific info

- Transfer / Transit services → travel_type = "transfer"

Example — PDF says "Departure or Arrival €475 per person":
[
  {{"service_name": "VIP Arrival",   "travel_type": "arrival",   "pricing": {{"1_pax": {{"adults": 475}} }} }},
  {{"service_name": "VIP Departure", "travel_type": "departure", "pricing": {{"1_pax": {{"adults": 475}} }} }}
]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2 — STRUCTURED fast_track  ⚠️ CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
fast_track is a NESTED OBJECT — not a string, not "yes/no".

  "fast_track": {{
    "departure": {{ "security": <value> }},
    "arrival":   {{ "immigration": <value>, "customs": <value> }}
  }}

Allowed values: "fast track" | "expedited" | "assistance" | "no assistance" | null

  • ARRIVAL object   → fill arrival fields; departure.security = null
  • DEPARTURE object → fill departure.security; arrival fields = null
  • TRANSFER object  → fill all three if mentioned

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — PRICING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 1_pax adults  = price for the first / only person
- 2_pax adults  = cumulative total for 2 people … continue cumulatively
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
Return ONLY a valid JSON array. No markdown, no backticks, no explanation.
Ensure the JSON is complete and properly closed — never truncate.

Now extract ALL services from this PDF.
"""


# ── FILE UPLOAD HELPER ────────────────────────────────────────────────────────
def _upload_pdf(client, pdf_bytes: bytes, filename: str):
    """Uploads PDF bytes to Gemini Files API. Returns the file object."""
    print(f"📤 [Upload] Uploading {filename} to Gemini Files API...")
    pdf_stream = io.BytesIO(pdf_bytes)
    pdf_stream.name = filename

    uploaded = client.files.upload(
        file=pdf_stream,
        config={"mime_type": "application/pdf", "display_name": filename}
    )
    print(f"✅ [Upload] File uploaded — URI: {uploaded.uri}")
    return uploaded


def _delete_file(client, uploaded_file):
    """Best-effort cleanup of uploaded file from Gemini server."""
    try:
        client.files.delete(name=uploaded_file.name)
        print(f"🗑️  [Upload] Cleaned up remote file: {uploaded_file.name}")
    except Exception as e:
        print(f"⚠️  [Upload] Could not delete remote file: {e}")


# ── STREAMING CALL WITH TIMEOUT ───────────────────────────────────────────────
def _call_streaming_with_timeout(client, model, uploaded_file, prompt, timeout=MODEL_TIMEOUT_SECONDS):
    """
    Streams the Gemini response in a background thread.
    Returns (full_text, None) on success or (None, error_str) on failure/timeout.
    """
    result = {"text": None, "error": None}

    def _stream():
        try:
            chunks = []
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded_file.uri,
                                mime_type="application/pdf"
                            ),
                            types.Part.from_text(text=prompt),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(temperature=0)
            ):
                if chunk.text:
                    chunks.append(chunk.text)
            result["text"] = "".join(chunks).strip()
        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=_stream, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        return None, f"TIMEOUT after {timeout}s"

    return result["text"], result["error"]


# ── JSON REPAIR ───────────────────────────────────────────────────────────────
def _repair_json(raw: str) -> list | None:
    """Three-strategy recovery for malformed/truncated JSON."""

    # Strategy 1: json_repair library (pip install json-repair)
    try:
        from json_repair import repair_json
        repaired = repair_json(raw, return_objects=True)
        if isinstance(repaired, list) and repaired:
            print("🔧 [Repair] json_repair recovered the JSON.")
            return repaired
        if isinstance(repaired, dict):
            return [repaired]
    except ImportError:
        pass

    # Strategy 2: close unclosed brackets
    print("🔧 [Repair] Attempting bracket-close repair...")
    attempt = raw.rstrip()
    if attempt.endswith(","):
        attempt = attempt[:-1]
    attempt += "}" * max(attempt.count("{") - attempt.count("}"), 0)
    attempt += "]" * max(attempt.count("[") - attempt.count("]"), 0)

    try:
        parsed = json.loads(attempt)
        if isinstance(parsed, list):
            print(f"🔧 [Repair] Bracket-close succeeded — {len(parsed)} service(s).")
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Strategy 3: salvage complete objects
    print("🔧 [Repair] Attempting object-by-object salvage...")
    objects, depth, start = [], 0, None
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    objects.append(json.loads(raw[start:i + 1]))
                except json.JSONDecodeError:
                    pass
                start = None

    if objects:
        print(f"🔧 [Repair] Salvaged {len(objects)} object(s).")
        return objects

    return None


# ── MAIN EXTRACTION ───────────────────────────────────────────────────────────
def extract_fields_ai(pdf_file) -> list | dict:
    filename = getattr(pdf_file, "name", "document.pdf")
    print(f"\n📄 [Extract] Starting extraction for: {filename}")

    pdf_bytes = pdf_file.read()
    client    = get_client()
    prompt    = _make_prompt()

    RETRYABLE = ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "TIMEOUT")

    # Upload PDF once — shared across all model attempts
    try:
        uploaded_file = _upload_pdf(client, pdf_bytes, filename)
    except Exception as e:
        print(f"💀 [Upload] Failed to upload PDF: {e}")
        return {"error": "upload_failed", "detail": str(e)}

    try:
        for idx, model in enumerate(FALLBACK_MODELS):
            position = f"{idx + 1}/{len(FALLBACK_MODELS)}"
            print(f"\n🚀 [Gemini] Trying model {position}: {model}  (timeout={MODEL_TIMEOUT_SECONDS}s)")

            raw, err = _call_streaming_with_timeout(client, model, uploaded_file, prompt)

            # ── Handle errors ──────────────────────────────────────────────
            if err:
                is_retryable = any(code in err for code in RETRYABLE)

                if not is_retryable:
                    print(f"💀 [Gemini] Non-retryable error on {model}.")
                    print(f"   ↳ {err}")
                    return {"error": "model_call_failed", "detail": err}

                if idx + 1 < len(FALLBACK_MODELS):
                    delay = round(random.uniform(1, 3), 1)
                    print(f"⚠️  [Gemini] {model} failed — moving to next model.")
                    print(f"   ↳ Reason    : {err[:120]}")
                    print(f"   ↳ Next model: {FALLBACK_MODELS[idx + 1]}")
                    print(f"   ↳ Waiting   : {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"🛑 [Gemini] All models failed.")
                    return {"error": "all_models_failed", "detail": err}

                continue

            print(f"✅ [Gemini] Got response from: {model}")

            # ── Parse ──────────────────────────────────────────────────────
            print("🔍 [Parser] Parsing response...")
            cleaned = raw.replace("```json", "").replace("```", "").strip()

            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                print(f"🎉 [Parser] Clean parse — {len(parsed)} service(s).")
                return parsed
            except json.JSONDecodeError as e:
                print(f"⚠️  [Parser] Clean parse failed: {e} — attempting repair...")

            repaired = _repair_json(cleaned)
            if repaired:
                print(f"🎉 [Parser] Repaired — {len(repaired)} service(s).")
                return repaired

            print(f"💥 [Parser] Repair failed on {model}.")
            print(f"   ↳ Snippet: {cleaned[:200]}{'...' if len(cleaned) > 200 else ''}")

            if idx + 1 < len(FALLBACK_MODELS):
                print(f"   ↳ Trying next model: {FALLBACK_MODELS[idx + 1]}")
                continue

            return {"error": "invalid_json", "raw": cleaned, "detail": "Repair failed on all models."}

    finally:
        _delete_file(client, uploaded_file)

    return {"error": "all_models_failed", "detail": "Exhausted all models."}


# ── MISSING FIELD CHECKER ─────────────────────────────────────────────────────
def flag_missing_fields(service_list: list) -> list:
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

    return [
        {
            "service_index":  idx,
            "service_name":   svc.get("service_name", f"Service {idx + 1}"),
            "missing_fields": _collect_missing(svc)
        }
        for idx, svc in enumerate(service_list)
    ]
