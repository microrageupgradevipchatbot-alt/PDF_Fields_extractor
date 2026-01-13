# app3_streamlit.py
"""
Streamlit UI for app3: multi-file upload, send each PDF to app3.extract_fields_ai,
display JSON results, allow copy/download.
"""

import json
import streamlit as st
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from app_v2 import extract_fields_ai

st.set_page_config(page_title="Service PDF Extractor (Vision)", layout="centered")

st.markdown("""
# 📄 Service PDF Extractor — Gemini Vision V2.5
""")

# small old-style UI wrapper (like your screenshot)

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=False)

# helper to create a simple downloadable PDF from text
def create_pdf_from_text(text):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    text_obj = pdf.beginText(40, 750)
    text_obj.setFont("Helvetica", 11)
    for line in text.split("\n"):
        # guard: if text runs off page we simply keep adding pages (simple approach)
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

# JS copy button helper
def copy_button(text, key):
    # Escape backticks and backslashes in text for safe inline JS
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

if uploaded_file:
    st.markdown("---")
    st.write(f"**File:** {uploaded_file.name}")

    # Use session_state to cache result for this file
    # NEW CODE:
    file_key = f"result_{uploaded_file.name}_{uploaded_file.size}"
    if file_key not in st.session_state:
        # Create a larger, persistent processing indicator
        processing_container = st.empty()
        # NEW CODE - Dots Right After PDF (No Space):
        with processing_container:
            st.markdown("""
            <style>
            @keyframes dots {
                0%, 20% { content: ''; }
                40% { content: '.'; }
                60% { content: '..'; }
                80%, 100% { content: '...'; }
            }
            .loading-title::after {
                content: '';
                animation: dots 1.5s infinite;
            }
            </style>
            <div style='padding: 40px; text-align: center; background: #f8f9fa; 
                        border: 2px solid #e9ecef; border-radius: 10px; margin: 20px 0;'>
                <h2 style='color: #2c3e50; margin: 0; font-weight: 600;'>
                    <span class='loading-title'>🔄 Processing Your PDF</span>
                </h2>
                <p style='color: #6c757d; margin: 15px 0 0 0; font-size: 20px;font-weight:bold;'>
                    Extracting service details with AI. Please wait...
                </p>
            </div>
            """, unsafe_allow_html=True)
        try:
            result = extract_fields_ai(uploaded_file)
            processing_container.empty()  # Clear only after success
        except Exception as e:
            processing_container.empty()
            st.error(f"Processing error: {e}")
            result = None
        
        st.session_state[file_key] = result
    else:
        result = st.session_state[file_key]

    if isinstance(result, dict) and result.get("error"):
        if result.get("error") == "quota_exceeded":
            st.error("⚠️ " + result.get("detail"))
        else:
            st.error("❌ Extraction error — see details below.")
            st.write(result.get("detail") or result.get("raw"))
    elif result:
        st.subheader("Extracted JSON")
        st.json(result)

    # --- Download buttons at the bottom ---
    st.markdown("---")
    st.download_button(
        label="📥 Download as TXT",
        data=json.dumps(result, indent=2),
        file_name=f"{uploaded_file.name}_extracted.txt",
        mime="text/plain"
    )
    pdf_buffer = create_pdf_from_text(json.dumps(result, indent=2))
    st.download_button(
        label="📄 Download as PDF",
        data=pdf_buffer,
        file_name=f"{uploaded_file.name}_extracted.pdf",
        mime="application/pdf"
    )    
else:
    st.info("Please upload a PDF file to extract.")