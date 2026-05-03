import pdfplumber
import docx
import re

def extract_text(file, filename):
    text = ""

    if filename.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""

    elif filename.endswith(".docx"):
        doc = docx.Document(file)
        for para in doc.paragraphs:
            text += para.text + "\n"

    return clean_text(text)


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)      # remove extra spaces
    text = re.sub(r'[^\w\s@.+-]', '', text)  # remove weird characters
    return text.strip()
