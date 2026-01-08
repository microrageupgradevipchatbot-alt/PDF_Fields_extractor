# app4_streamlit.py
"""
UI for Docling + Gemini extraction (App4 version)
"""

import streamlit as st
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from Archives.app4 import extract_fields_ai_docling
import os
import tempfile


st.set_page_config(page_title="Service PDF Extractor (Docling)", layout="centered")

st.markdown("""
# 📄 Service PDF Extractor — Docling + Gemini
Parses PDF using Docling (OCR + tables) then extracts fields via Gemini.
Faster & cheaper than Vision model.
""")


uploaded_files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

def create_pdf_from_text(text):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    text_obj = pdf.beginText(40, 750)
    text_obj.setFont("Helvetica", 11)

    for line in text.split("\n"):
        if text_obj.getY() < 40:
            pdf.drawText(text_obj)
            pdf.showPage()
            text_obj = pdf.beginText(40, 750)
            text_obj.setFont("Helvetica", 11)
        text_obj.textLine(line)

    pdf.drawText(text_obj)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

def copy_button(text, key):
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`")
    copy_js = f"""
    <script>
    function copyToClipboard{key}() {{
        navigator.clipboard.writeText(`{safe_text}`).then(function() {{
            const e = document.createElement('div');
            e.innerText = "Copied!";
            e.style.position = 'fixed';
            e.style.right = '20px';
            e.style.top = '20px';
            e.style.background = '#0b7285';
            e.style.color = 'white';
            e.style.padding = '8px 12px';
            e.style.borderRadius = '6px';
            document.body.appendChild(e);
            setTimeout(()=>document.body.removeChild(e), 1200);
        }});
    }}
    </script>
    """
    st.markdown(copy_js, unsafe_allow_html=True)

def _format_summary(d):
    lines = []
    preferred_keys = [
        "service_type", "services", "title", "airport", "max_passengers_allowed",
        "travel_type", "status", "meeting_point", "fast_track",
        "transportation_inside_airport", "assistance_with_pieces_of_luggage",
        "lounge_access", "farewell", "special_announcement",
        "duration_minutes", "fee_ooh", "late_booking_fee", "usp", "refund_policy_hours"
    ]
    for k in preferred_keys:
        v = d.get(k, None)
        lines.append(f"{k}: {v}")
    pricing = d.get("pricing", {})
    lines.append("pricing:")
    if isinstance(pricing, dict):
        for pax_key in sorted(pricing.keys(), key=lambda s: int(s.split("_")[0])):
            pax = pricing.get(pax_key)
            lines.append(f"  {pax_key}: {pax}")
    sd = d.get("service_details", [])
    lines.append("service_details:")
    if isinstance(sd, list):
        for bullet in sd:
            lines.append(f"  - {bullet}")
    return "\n".join(lines)

if uploaded_files:
    for idx, pdf_file in enumerate(uploaded_files):
        st.markdown("---")
        st.write(f"**File:** {pdf_file.name}")

        with st.spinner(f"Processing {pdf_file.name} using Docling..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name

            try:
                try:
                    result = extract_fields_ai_docling(tmp_path)
                except Exception:
                    result = None
            finally:
                os.unlink(tmp_path)

        if not result or (isinstance(result, dict) and result.get("error")):
            st.error("❌ Failed to extract from PDF.")
            continue

        st.subheader("Extracted JSON")
        st.json(result)

        summary = _format_summary(result if isinstance(result, dict) else {})

        with st.expander("Preview / Copy / Download", expanded=False):
            st.code(summary, language="text")
            copy_button(summary, key=f"{idx}")
            st.download_button(
                label="📥 Download as TXT",
                data=summary,
                file_name=f"{pdf_file.name}_docling.txt",
                mime="text/plain"
            )
            pdf_buffer = create_pdf_from_text(summary)
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_buffer,
                file_name=f"{pdf_file.name}_docling.pdf",
                mime="application/pdf"
            )
else:
    st.info("Upload PDF to begin.")