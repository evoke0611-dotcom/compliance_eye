from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
QUESTIONS_DIR = DATA_DIR / "questions"
RUNTIME_DIR = DATA_DIR / "runtime"

ASSETS_DIR = PROJECT_ROOT / "assets"
GENERATED_ASSETS_DIR = ASSETS_DIR / "generated"

DOCS_DIR = PROJECT_ROOT / "docs"
PROJECT_DOCS_DIR = DOCS_DIR / "project"

ISO_PDF_PATH = KNOWLEDGE_BASE_DIR / "ISO_IEC-270012022-ed.3.pdf"
KB_JSONL_PATH = KNOWLEDGE_BASE_DIR / "output.jsonl"
FAISS_INDEX_PATH = KNOWLEDGE_BASE_DIR / "iso27001.index"
KB_METADATA_PATH = KNOWLEDGE_BASE_DIR / "iso27001_metadata.json"

GAP_ASSESSMENT_PDF_PATH = QUESTIONS_DIR / "Gap Assessment question.pdf"
RISK_ASSESSMENT_PDF_PATH = QUESTIONS_DIR / "Risk Assessment question.pdf"
ISMS_POLICY_PDF_PATH = QUESTIONS_DIR / "ISMS Policy Questions.pdf"

DB_PATH = RUNTIME_DIR / "complianceeye.db"
GENERATED_LOGO_PATH = GENERATED_ASSETS_DIR / "temp_logo.png"
