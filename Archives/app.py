import re
import pdfplumber

# -----------------------------
# Extract full text from PDF
# -----------------------------
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        # Log or handle the error as needed
        print(f"Error reading PDF: {e}")
        return None
    return text


# -----------------------------
# Extract structured fields using Regex
# -----------------------------
def extract_fields(text):
    # Customize these regex patterns based on your PDF format
    patterns = {
        "name": r"Name[:\- ]+([A-Za-z ]+)",
        "roll_no": r"Roll\s*No[:\- ]+(\w+)",
        "date": r"Date[:\- ]+([\d\-\/]+)",
        "class": r"Class[:\- ]+([A-Za-z0-9 ]+)"
    }

    result = {}

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        result[field] = match.group(1).strip() if match else None  # return null if not found

    return result
