import streamlit as st
import json
from Archives.app import extract_text_from_pdf, extract_fields
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

st.set_page_config(page_title="PDF Field Extractor", layout="centered")

st.title("📄 PDF Field Extractor - Multi File Support")
st.write("Upload one or more PDF files to extract Name, Roll No, Date, Class automatically.")

# -------------------------------------------------------
# Copy-to-Clipboard Button (Custom JS)
# -------------------------------------------------------
def copy_button(text, key):
    copy_js = f"""
    <script>
        function copyText{key}() {{
            navigator.clipboard.writeText(`{text}`);
            alert("Copied to Clipboard!");
        }}
    </script>
    
    """
    st.markdown(copy_js, unsafe_allow_html=True)

# -------------------------------------------------------
# Generate PDF File from Text
# -------------------------------------------------------
def create_pdf(text):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    text_object = pdf.beginText(40, 750)
    text_object.setFont("Helvetica", 12)

    for line in text.split("\n"):
        text_object.textLine(line)

    pdf.drawText(text_object)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

# -------------------------------------------------------
# MULTIPLE FILE UPLOAD
# -------------------------------------------------------
uploaded_pdfs = st.file_uploader(
    "Upload PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_pdfs:
    for idx, uploaded_pdf in enumerate(uploaded_pdfs):
        st.success(f"📄 Uploaded: {uploaded_pdf.name}")

        # Extract text from PDF
        try:
            text = extract_text_from_pdf(uploaded_pdf)
        except:
            st.error(f"❌ Could not read {uploaded_pdf.name}")
            continue

        # Extract structured fields
        fields = extract_fields(text)

        # Display extracted data
        st.subheader(f"📌 Extracted Data from {uploaded_pdf.name}")
        st.json(fields)

        # Expand raw text + copy + downloads
        with st.expander(f"📄 Show Extracted Info for {uploaded_pdf.name}"):

            # Prepare clean output text
            info = (
                f"Name: {fields.get('name')}\n"
                f"Roll no: {fields.get('roll_no')}\n"
                f"Class: {fields.get('class')}\n"
                f"Date: {fields.get('date')}"
            )

            st.code(info, language="text")

            # ----------------------
            # COPY BUTTON
            # ----------------------
            
            copy_button(info, key=idx)

            # ----------------------
            # DOWNLOAD TXT
            # ----------------------
            st.download_button(
                label="📥 Download as TXT",
                data=info,
                file_name=f"{uploaded_pdf.name}_extracted.txt",
                mime="text/plain"
            )

            # ----------------------
            # DOWNLOAD PDF
            # ----------------------
            pdf_file = create_pdf(info)
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_file,
                file_name=f"{uploaded_pdf.name}_extracted.pdf",
                mime="application/pdf"
            )

else:
    st.info("Please upload one or more PDF files to begin.")
