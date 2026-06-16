import fitz


def extract_text(pdf_path):
    print(f"Extracting text from {pdf_path}...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        print(f"Error opening PDF: {exc}")
        return ""

    raw_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        raw_text += page.get_text("text") + "\n"
    return raw_text
