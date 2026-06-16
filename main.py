from chunker import chunk_text
from cleaner import clean_text
from exporter import export_to_jsonl
from extractor import extract_text
from project_paths import ISO_PDF_PATH, KB_JSONL_PATH


def main():
    raw_text = extract_text(ISO_PDF_PATH)
    if not raw_text:
        print("No text extracted. Exiting.")
        return

    cleaned_text = clean_text(raw_text)
    chunks = chunk_text(cleaned_text)
    export_to_jsonl(chunks, KB_JSONL_PATH)
    print(f"Successfully processed {len(chunks)} chunks.")


if __name__ == "__main__":
    main()
