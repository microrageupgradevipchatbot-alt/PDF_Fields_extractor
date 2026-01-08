import streamlit as st
from Archives.app2 import extract_fields_ai
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

st.set_page_config(page_title="AI PDF Field Extractor", layout="centered")

st.markdown("""
# 📄 AI PDF Field Extractor
Upload one or more PDF files and the AI will extract:
**name, roll_no, date, class**. Missing fields will return **null**.
""")

# -------------------------------------------------------
# Copy to clipboard (JS)
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
# Generate PDF from text
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
# MULTI PDF UPLOAD
# -------------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    for idx, uploaded_file in enumerate(uploaded_files):
        st.success(f"📄 Uploaded: {uploaded_file.name}")

        with st.spinner(f" 🤖 Agent processing {uploaded_file.name}..."):
            try:
                result = extract_fields_ai(uploaded_file)
            except Exception as e:
                st.error(f"❌ Error processing {uploaded_file.name}: {e}")
                continue

        # Display extracted data
        st.subheader(f"📌 Extracted Data from {uploaded_file.name}")
        st.json(result)

        # Prepare info text
        info = (
            f"Name: {result.get('name')}\n"
            f"Roll no: {result.get('roll_no')}\n"
            f"Class: {result.get('class')}\n"
            f"Date: {result.get('date')}"
        )

        with st.expander(f"📄 Show / Copy / Download for {uploaded_file.name}", expanded=False):
            st.code(info, language="text")

            # Copy Button
            copy_button(info, key=idx)

            # Download TXT
            st.download_button(
                label="📥 Download as TXT",
                data=info,
                file_name=f"{uploaded_file.name}_extracted.txt",
                mime="text/plain"
            )

            # Download PDF
            pdf_file = create_pdf(info)
            st.download_button(
                label="📄 Download as PDF",
                data=pdf_file,
                file_name=f"{uploaded_file.name}_extracted.pdf",
                mime="application/pdf"
            )
else:
    st.info("Please upload one or more PDF files to begin.")
