# Compliance Eye

Compliance Eye is a Streamlit-based ISO 27001 audit assistant. It helps users run gap assessments, risk assessments, and ISMS policy workflows, then generate structured report documents from uploaded evidence and questionnaire responses.

## Features

- Streamlit web interface for ISO 27001 audit workflows
- User registration, login, and local audit history storage
- Gap assessment, risk assessment, and ISMS policy question flows
- PDF and image text extraction with `pdfplumber`, `Pillow`, and `pytesseract`
- OpenAI-assisted compliance analysis and report generation
- DOCX report output using `python-docx`
- Local ISO 27001 knowledge-base assets with FAISS indexing support

## Project Structure

```text
.
|-- auditor.py                  # Main Streamlit app entry point
|-- compliance_eye_app.py        # Alternate/legacy app flow
|-- auth_page.py                 # Login and registration UI
|-- database.py                  # SQLite user and audit session storage
|-- report_builder.py            # DOCX audit report generation
|-- isms_policy_builder.py       # ISMS policy document generation
|-- isms_questions.py            # ISMS policy workflow questions
|-- question_bank.py             # Assessment question loading
|-- document_processing.py       # Uploaded document helpers
|-- extractor.py                 # ISO source extraction
|-- cleaner.py                   # Text cleanup helpers
|-- chunker.py                   # Text chunking helpers
|-- exporter.py                  # JSONL export helpers
|-- faiss_indexer.py             # FAISS index builder
|-- main.py                      # Knowledge-base extraction pipeline
|-- pipeline.py                  # Question generation and validation utilities
|-- project_paths.py             # Shared repo-relative paths
|-- assets/                      # Static and generated assets
|-- data/
|   |-- knowledge_base/          # ISO source, JSONL chunks, metadata, FAISS index
|   |-- questions/               # Question banks and assessment source files
|   `-- runtime/                 # Local database and runtime-generated data
|-- docs/project/                # Project briefs and reference documents
`-- requirements.txt             # Python dependencies
```

## Requirements

- Python 3.10 or newer
- Tesseract OCR installed locally if you want image OCR to work through `pytesseract`
- An OpenAI API key for AI-assisted analysis

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Configure your OpenAI key:

```powershell
$env:OPENAI_API_KEY="your-api-key"
```

The app also supports `config.py`, but that file should be kept local because it can contain secrets.

## Running the App

Start the Streamlit app:

```powershell
streamlit run auditor.py
```

Streamlit will print a local URL in the terminal, usually:

```text
http://localhost:8501
```

## Knowledge-Base Pipeline

The ISO source extraction pipeline can be run with:

```powershell
python main.py
```

This reads the ISO PDF path from `project_paths.py`, cleans and chunks extracted text, and writes JSONL output to `data/knowledge_base/output.jsonl`.

To rebuild or work with the vector index, use `faiss_indexer.py` and the files in `data/knowledge_base/`.

## Runtime Data

Local runtime files are stored in:

```text
data/runtime/
```

This directory may contain the SQLite database and audit history generated while using the app. These files are ignored by Git because they are machine-specific and may contain user data.

## Security Notes

- Do not commit real API keys.
- Prefer `OPENAI_API_KEY` as an environment variable.
- Rotate any key that has already been shared or committed.
- Keep local databases and generated audit reports out of public repositories unless they have been reviewed and sanitized.

## Common Commands

```powershell
# Run the web app
streamlit run auditor.py

# Run the extraction pipeline
python main.py

# Install dependencies
pip install -r requirements.txt
```
