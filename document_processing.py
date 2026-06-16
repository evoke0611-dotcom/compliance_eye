import pdfplumber
import pytesseract
import streamlit as st
from PIL import Image


def extract_text_from_pdf(uploaded_file):
    """Extract text from an uploaded PDF."""
    try:
        text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text.strip()
    except Exception as exc:
        st.error(f"Error extracting PDF: {exc}")
        return ""


def extract_text_from_image(uploaded_file):
    """Extract text from an uploaded image with OCR."""
    try:
        return pytesseract.image_to_string(Image.open(uploaded_file)).strip()
    except Exception as exc:
        st.error(f"Error extracting image: {exc}")
        return ""


def chunk_text(text, chunk_size=1000, overlap=200):
    words = text.split()
    step = max(1, chunk_size - overlap)
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), step)]


def clean_text(text):
    return str(text or "").strip()


def load_faiss_index():
    return None


def search_faiss(query, index=None):
    return ""
