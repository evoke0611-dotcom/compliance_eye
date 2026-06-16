import streamlit as st
import json
import os
import re
import html
import pdfplumber
import pytesseract
from PIL import Image
import openai
from openai import OpenAI
from report_builder import create_structured_docx_report
from database import init_db, register_user, login_user, get_user_by_id, save_audit_session, get_user_audit_history, update_audit_session, delete_audit_session
from auth_page import render_auth_page
from isms_questions import ISMS_STEPS, REPEAT_FIELDS, STEP_LABELS
from isms_policy_builder import build_isms_policy_docx

# set_page_config MUST be the very first Streamlit call
st.set_page_config(
    page_title="ComplianceEye — ISO 27001 AI Auditor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# PDF and image extraction functions
def extract_text_from_pdf(uploaded_file):
    """Extract text from PDF using basic fallback."""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error extracting PDF: {e}")
        return ""

def extract_text_from_image(uploaded_file):
    """Extract text from image using basic fallback."""
    try:
        image = Image.open(uploaded_file)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        st.error(f"Error extracting image: {e}")
        return ""

# Simplified text processing
def chunk_text(text, chunk_size=1000, overlap=200):
    """Simple text chunking."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def clean_text(text):
    """Simple text cleaning."""
    return text.strip()

def load_faiss_index():
    """Simple placeholder for FAISS index."""
    return None

def search_faiss(query, index=None):
    """Simple placeholder for FAISS search.""" 
    return ""

# Load configuration
try:
    from config import OPENAI_API_KEY, OPENAI_MODEL
except ImportError:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = "gpt-4o-mini"

# Initialize OpenAI client
client = OpenAI(
    api_key=OPENAI_API_KEY
)

# Load Assessment Questions
@st.cache_data
def load_assessment_questions_from_pdf(pdf_path: str):
    """Extract assessment questions and A-D options from a PDF."""
    if not os.path.exists(pdf_path):
        return []

    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                full_text += "\n" + (page.extract_text() or "")
    except Exception:
        return []

    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    questions = []
    current = None
    # Parse options like: "A. text", "B) text", or "C text" (letter + whitespace).
    # Important: do NOT match regular words that start with A-E (e.g., "challenges?").
    option_pat = re.compile(r"^([A-E])(?:[.)]\s*|\s+)(.+)$", re.IGNORECASE)
    q_pat = re.compile(r"^(\d+(?:\.\d+)*)[.)]\s*(.+)$")

    for line in lines:
        q_match = q_pat.match(line)
        opt_match = option_pat.match(line)

        if q_match:
            if current and current.get("question"):
                questions.append(current)
            current = {
                "clause": q_match.group(1),
                "question": q_match.group(2).strip(),
                "options": [],
            }
            continue

        if opt_match and current:
            letter = opt_match.group(1).upper()
            opt_text = (opt_match.group(2) or "").strip()
            current["options"].append(f"{letter}. {opt_text}")
            continue

        if current:
            # Continuation of previous question/options text
            if current.get("options"):
                current["options"][-1] = f"{current['options'][-1]} {line}".strip()
            else:
                current["question"] = f"{current['question']} {line}".strip()

    if current and current.get("question"):
        questions.append(current)

    return questions

@st.cache_data
def load_isms_policy_questions_from_pdf():
    """
    Extracts ISMS Policy questions from 'ISMS Policy Questions.pdf'.
    The PDF is a questionnaire with headings and bullet questions.
    Returns list[dict]: {section: str, question: str}
    """
    pdf_path = "ISMS Policy Questions.pdf"
    if not os.path.exists(pdf_path):
        return []

    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += "\n" + page_text
    except Exception:
        # Fallback: best-effort; return empty if we can't read
        return []

    section = ""
    questions = []
    for raw in full_text.splitlines():
        line = (raw or "").strip()
        if not line:
            continue
        # Section headers like: "1. ISMS POLICY & GOVERNANCE"
        if re.match(r"^\d+\.\s+", line):
            section = line
            continue
        # Bullet questions like: "- Is there a formal Information Security Policy ...?"
        if line.startswith("- "):
            q = line[2:].strip()
            if q:
                questions.append({"section": section or "ISMS Policy", "question": q})
    return questions

GAP_ASSESSMENT_QUESTIONS = load_assessment_questions_from_pdf("Gap Assessment question.pdf")
RISK_ASSESSMENT_QUESTIONS = load_assessment_questions_from_pdf("Risk Assessment question.pdf")
ISMS_POLICY_QUESTIONS = load_isms_policy_questions_from_pdf()

# Initialise DB schema on every startup
init_db()

# (set_page_config moved to top of file, right after imports)

# ── Auth gate: renders login if not authenticated ──────────────────────────
if not render_auth_page():
    st.stop()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, html, body { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }

/* ── BACKGROUND: animated mesh gradient ── */
.stApp {
    background: #f0f4ff;
    background-image:
        radial-gradient(at 20% 10%, #dbeafe 0px, transparent 55%),
        radial-gradient(at 80% 0%, #ede9fe 0px, transparent 50%),
        radial-gradient(at 5% 90%, #d1fae5 0px, transparent 45%),
        radial-gradient(at 90% 85%, #fce7f3 0px, transparent 45%);
    min-height: 100vh;
}

/* ── TOP NAV BAR ── */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 0 22px;
    border-bottom: 1.5px solid rgba(99,102,241,0.12);
    margin-bottom: 28px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-icon {
    width: 40px; height: 40px; border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; color: white; box-shadow: 0 4px 14px rgba(99,102,241,0.4);
}
.brand-name { font-size: 1.25rem; font-weight: 800; color: #1e1b4b; letter-spacing: -0.02em; }
.brand-sub { font-size: 0.7rem; color: #6366f1; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
.nav-pill {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white; border-radius: 100px; padding: 7px 20px;
    font-size: 0.8rem; font-weight: 600; letter-spacing: 0.04em;
    box-shadow: 0 4px 16px rgba(99,102,241,0.35);
    display: flex; align-items: center; gap: 7px;
}
.live-dot {
    width: 8px; height: 8px; background: #34d399; border-radius: 50%;
    animation: blink 1.5s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }

/* ── BENTO GRID ── */
.bento-grid {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 20px;
}

/* ── CARDS (Applied to main columns) ── */
[data-testid="column"] {
    background: rgba(255,255,255,0.75);
    backdrop-filter: blur(20px);
    border: 1.5px solid rgba(99,102,241,0.12);
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 4px 24px rgba(99,102,241,0.07);
}
/* Do not apply card style to nested columns (like button rows) */
[data-testid="column"] [data-testid="column"] {
    background: transparent;
    backdrop-filter: none;
    border: none;
    border-radius: 0;
    padding: 0;
    box-shadow: none;
}
.card-title {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #6366f1; margin-bottom: 16px;
    display: flex; align-items: center; gap: 7px;
}

/* ── CHAT MESSAGES ── */
.chat-scroll {
    display: flex; flex-direction: column-reverse;
    height: 480px; overflow-y: auto;
    padding-right: 6px; margin-bottom: 16px;
}
.chat-scroll::-webkit-scrollbar { width: 4px; }
.chat-scroll::-webkit-scrollbar-thumb { background: #c7d2fe; border-radius: 10px; }

.msg-row { display: flex; gap: 12px; margin-bottom: 16px; align-items: flex-start; }
.msg-row.user-row { flex-direction: row-reverse; }

.avatar-chip {
    width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.avatar-alex {
    background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
    border: 2px solid #a5b4fc;
}
.avatar-user {
    background: linear-gradient(135deg, #fce7f3, #fbcfe8);
    border: 2px solid #f9a8d4;
}

.bubble-wrap { display: flex; flex-direction: column; max-width: 75%; }
.bubble-wrap.user-wrap { align-items: flex-end; }

.bubble {
    padding: 13px 17px; border-radius: 18px;
    font-size: 0.875rem; line-height: 1.65; color: #1e1b4b;
}
.bubble-alex {
    background: white;
    border: 1.5px solid #e0e7ff;
    border-top-left-radius: 4px;
    box-shadow: 0 2px 12px rgba(99,102,241,0.08);
}
.bubble-user {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border-top-right-radius: 4px;
    box-shadow: 0 4px 16px rgba(99,102,241,0.25);
}
.bubble-time {
    font-size: 0.65rem; color: #94a3b8; margin-top: 4px;
}

/* ── START SCREEN ── */
.start-screen {
    text-align: center; padding: 48px 20px;
}
.start-icon {
    width: 90px; height: 90px; border-radius: 24px; margin: 0 auto 20px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-size: 42px;
    box-shadow: 0 8px 32px rgba(99,102,241,0.35);
}
.start-title {
    font-size: 1.6rem; font-weight: 800; color: #1e1b4b;
    letter-spacing: -0.03em; margin-bottom: 10px;
}
.start-sub { font-size: 0.9rem; color: #64748b; max-width: 380px; margin: 0 auto 28px; line-height: 1.6; }
.feature-grid { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-bottom: 28px; }
.feature-tag {
    background: #f0f4ff; border: 1.5px solid #c7d2fe;
    border-radius: 100px; padding: 5px 14px;
    font-size: 0.75rem; font-weight: 600; color: #4f46e5;
}

/* ── QUICK PILLS ── */
.pills-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; margin-bottom: 6px; }
.q-pill {
    background: #f0f4ff; border: 1.5px solid #c7d2fe; border-radius: 100px;
    padding: 6px 15px; font-size: 0.75rem; color: #4f46e5; font-weight: 500; cursor: pointer;
    transition: all 0.2s;
}
.q-pill:hover { background: #e0e7ff; border-color: #a5b4fc; }

/* ── INPUTS & SELECTBOX ── */
.stTextInput > div > div > input,
div[data-baseweb="select"] > div,
.stTextArea > div > div > textarea {
    background: white !important;
    border: 1.5px solid #c7d2fe !important;
    border-radius: 12px !important;
    color: #1e1b4b !important;
    font-family: 'Sora', sans-serif !important;
    font-size: 0.875rem !important;
    box-shadow: 0 2px 8px rgba(99,102,241,0.06) !important;
}
.stTextInput > div > div > input { 
    padding: 13px 16px !important; 
    height: 44px !important;
}
.stTextArea > div > div > textarea { 
    padding: 13px 16px !important; 
    height: 68px !important;
    resize: none !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
div[data-baseweb="select"] > div:focus-within {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}

/* ── FORM ALIGNMENT ── */
.form-row {
    display: flex;
    gap: 20px;
    margin-bottom: 16px;
}
.form-column {
    flex: 1;
}

/* ── BETTER FORM FIELD ALIGNMENT ── */
[data-testid="stForm"] {
    margin-bottom: 0 !important;
}
[data-testid="stForm"] > div {
    padding: 0 !important;
}
[data-testid="stForm"] .stVerticalBlock {
    gap: 0 !important;
}
[data-testid="stForm"] .stVerticalBlock > div {
    margin-bottom: 16px !important;
}
[data-testid="stForm"] .stHorizontalBlock {
    gap: 20px !important;
    margin-bottom: 16px !important;
}
[data-testid="stForm"] .element-container {
    margin-bottom: 0 !important;
}
[data-testid="stForm"] .stTextInput,
[data-testid="stForm"] .stTextArea {
    margin-bottom: 0 !important;
}

/* ── BUTTONS ── */
button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important; border-radius: 12px !important;
    color: white !important; font-family: 'Sora', sans-serif !important;
    font-weight: 600 !important; font-size: 0.875rem !important;
    padding: 11px 22px !important; letter-spacing: 0.01em !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.3) !important;
    transition: all 0.25s ease !important;
}
button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(99,102,241,0.45) !important;
}
button[kind="secondary"] {
    background: #f0f4ff !important; 
    border: 1.5px solid #c7d2fe !important; 
    border-radius: 100px !important;
    padding: 6px 8px !important; 
    font-size: 0.72rem !important; 
    color: #4f46e5 !important; 
    font-weight: 500 !important;
    box-shadow: none !important;
    min-height: 0 !important;
    transition: all 0.2s !important;
}
button[kind="secondary"] p { font-size: 0.72rem !important; }
button[kind="secondary"]:hover {
    background: #e0e7ff !important; 
    border-color: #a5b4fc !important; 
}

/* ── KB PANEL ── */
.kb-item {
    background: white;
    border: 1.5px solid rgba(99,102,241,0.1);
    border-radius: 14px; padding: 14px 16px; margin-bottom: 10px;
    transition: all 0.2s; cursor: default;
}
.kb-item:hover { border-color: #a5b4fc; transform: translateX(3px); box-shadow: 0 4px 16px rgba(99,102,241,0.1); }
.kb-cid {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem; font-weight: 500;
    background: #e0e7ff; color: #4f46e5;
    border-radius: 6px; padding: 2px 8px; display: inline-block; margin-bottom: 6px;
}
.kb-title { font-size: 0.82rem; font-weight: 700; color: #1e1b4b; margin-bottom: 4px; }
.kb-desc { font-size: 0.75rem; color: #64748b; line-height: 1.55; white-space: normal; }
.kb-scroll { max-height: 580px; overflow-y: auto; padding-right: 6px; }
.kb-scroll::-webkit-scrollbar { width: 4px; }
.kb-scroll::-webkit-scrollbar-thumb { background: #c7d2fe; border-radius: 6px; }

/* ── STATS ── */
.stat-row { display: flex; gap: 10px; margin-bottom: 18px; }
.stat-box {
    flex: 1; background: white; border: 1.5px solid rgba(99,102,241,0.12);
    border-radius: 14px; padding: 12px; text-align: center;
    box-shadow: 0 2px 10px rgba(99,102,241,0.06);
}
.stat-num { font-size: 1.5rem; font-weight: 800; color: #4f46e5; line-height: 1; }
.stat-lbl { font-size: 0.65rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }

/* ── CTRL BUTTONS ── */
.ctrl-row { display: flex; gap: 8px; margin-top: 10px; }
.ctrl-btn {
    flex: 1; background: white; border: 1.5px solid #e0e7ff;
    border-radius: 12px; padding: 9px 10px; text-align: center;
    font-size: 0.75rem; font-weight: 600; color: #4f46e5;
    cursor: pointer; transition: all 0.2s;
}
.ctrl-btn:hover { background: #e0e7ff; border-color: #a5b4fc; }

/* ── MODERN CHAT CAPSULE ── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 40px !important;
}
[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: white !important;
    border: 1px solid rgba(99, 102, 241, 0.15) !important;
    border-radius: 40px !important;
    padding: 2px 16px !important;
    box-shadow: 0 10px 30px rgba(99, 102, 241, 0.08) !important;
}
.stTextArea textarea {
    background: transparent !important;
    border: none !important;
    padding: 10px 0 !important;
    font-size: 1rem !important;
    color: #1e1b4b !important;
    resize: none !important;
}
.stTextArea textarea:focus {
    box-shadow: none !important;
}
.workflow-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-top: 18px;
}
.workflow-step {
    background: rgba(255,255,255,0.82);
    border: 1.5px solid rgba(99,102,241,0.12);
    border-radius: 18px;
    padding: 14px 14px 12px;
    min-height: 92px;
    transition: all 0.2s ease;
    box-shadow: 0 8px 24px rgba(99,102,241,0.06);
}
.workflow-step.pending:hover {
    transform: translateY(-2px);
    border-color: #c7d2fe;
}
.workflow-step.active {
    border-color: #6366f1;
    background: linear-gradient(135deg, rgba(224,231,255,0.95), rgba(243,232,255,0.92));
    box-shadow: 0 12px 28px rgba(99,102,241,0.16);
}
.workflow-step.completed {
    border-color: rgba(16,185,129,0.35);
    background: linear-gradient(135deg, rgba(236,253,245,0.96), rgba(240,253,250,0.94));
}
.workflow-kicker {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6366f1;
}
.workflow-step.completed .workflow-kicker { color: #059669; }
.workflow-title {
    margin-top: 6px;
    font-size: 0.9rem;
    font-weight: 700;
    color: #1e1b4b;
}
.workflow-status {
    margin-top: 8px;
    font-size: 0.76rem;
    color: #64748b;
    line-height: 1.5;
}
.workflow-step.active .workflow-status {
    color: #4338ca;
}
.workflow-step.completed .workflow-status {
    color: #047857;
}
[data-testid="column"] .stButton > button[kind="secondary"]:disabled,
[data-testid="column"] .stButton > button[kind="primary"]:disabled {
    opacity: 0.55;
}
.plus-btn {
    width: 44px; height: 44px; border-radius: 50%;
    background: #f1f5f9; display: flex; align-items: center; justify-content: center;
    color: #64748b; font-size: 24px; cursor: pointer; transition: all 0.2s;
}
.plus-btn:hover { background: #e2e8f0; color: #4f46e5; }

</style>
""", unsafe_allow_html=True)

# ── FIXED JS: Enter to Send ───────────────────────────────────────────────
ST_INPUT_JS = """
<script>
const doc = window.parent.document;

doc.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        const active = doc.activeElement;

        if (active.tagName === 'TEXTAREA') {
            e.preventDefault();

            const submitBtn = Array.from(doc.querySelectorAll('button[kind="primary"]'))
                .find(btn => btn.innerText.trim() === "↑");
            
            if (submitBtn) submitBtn.click();
        }
    }
});
</script>
"""
st.markdown(ST_INPUT_JS, unsafe_allow_html=True)

# ── Load KB ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_kb():
    with open("C:\EvokeAI\Compliance Eye\data\knowledge_base\iso27001_metadata.json", "r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def build_context(data):
    lines = []
    for item in data:
        cid = item.get("control_id", "")
        title = item.get("title", "")
        desc = item.get("description", "")[:150] # Truncated to save tokens
        lines.append(f"[{cid}] {title}: {desc}...")
    return "\n".join(lines)

kb_data = load_kb()
kb_context = build_context(kb_data)
total_controls = len(kb_data)

# ── System Prompt ─────────────────────────────────────────────────────────────
def get_system_prompt(kb_context, basic_info=None, assessment_mode=False):
    org_name = basic_info.get("org_name", "{org_name}") if basic_info else "{org_name}"
    industry = basic_info.get("business_nature", "{industry}") if basic_info else "{industry}"
    
    basic_info_text = ""
    if basic_info:
        basic_info_text = f"""
USER CONTEXT:
- Organization: {org_name}
- Industry: {industry}
- Employee: {basic_info.get('emp_name')} ({basic_info.get('emp_role')})
"""

    if not assessment_mode:
        # ── CONVERSATIONAL MODE (one question at a time) ──────────────────
        return f"""You are Alex, a friendly, highly experienced, and empathetic ISO 27001 Lead Auditor and consultant.
Your complete ISO 27001:2022 knowledge base:
{kb_context}

{basic_info_text}

## 🔴 CRITICAL RULES — NEVER BREAK THESE:
1. Ask ONLY ONE question per response. Never list multiple questions together.
2. Wait for the user's answer before moving to the next question.
3. NEVER present a numbered or bulleted list of questions.
4. NEVER say "Here are my questions" or similar preamble.
5. Briefly acknowledge the user's previous answer (1-2 warm sentences), then ask the NEXT single question.
6. Be conversational, warm, and human — not robotic or list-like.

## INTERVIEW PHASES — Ask these questions one at a time, in order:

### Phase 1: Organization & Introduction (already collected via form — skip these, greet and move to Phase 2)
The user has already submitted: org name, business nature, services, IS mission, IS importance, stakeholders, stakeholder expectations, ISMS responsible person, ISMS core group, management commitment.
Do NOT re-ask Phase 1 questions. Greet the user warmly using their submitted info and proceed directly to Phase 2.

### Phase 2: ISMS Scope
Q1: What is the defined ISMS scope?
Q2: Which locations are included in your ISMS scope?
Q3: Which departments are in scope?
Q4: Which systems and applications are in scope?
Q5: What is explicitly excluded from scope?
Q6: How do you control interfaces with out-of-scope entities?
Q7: Who approves scope changes?
Q8: How often is scope reviewed?

### Phase 3: Risk Management
Q9: Do you have a formal risk assessment process?
Q10: How do you identify information security risks?
Q11: What risk assessment methodology do you use?
Q12: How do you evaluate and prioritize risks?
Q13: Who owns the risk register?
Q14: How often is the risk register reviewed?

### Phase 4: Controls & Policies
Q15: Do you have a documented Information Security Policy?
Q16: How is the policy communicated to staff?
Q17: How often is the policy reviewed?
Q18: Do you have role-based access controls in place?
Q19: How do you manage third-party/supplier security?
Q20: Do you have an incident response plan?

### Phase 5: Monitoring & Improvement
Q21: How do you monitor and measure ISMS performance?
Q22: Do you conduct internal audits? How often?
Q23: Have you had a management review of the ISMS?
Q24: How do you handle nonconformities and corrective actions?
Q25: What continual improvement activities are in place?

## RESPONSE FORMAT (follow strictly):
- 1-2 sentences acknowledging the previous answer.
- Ask exactly ONE question from the current phase.
- Do not include suggestions, options arrays, or any "SUGGESTIONS:" text.

## EXAMPLE OF CORRECT RESPONSE:
"That's great — having customer data and employee records in scope is a solid foundation.

Which physical locations or office sites are included in your ISMS scope?"

## EXAMPLE OF WRONG RESPONSE (NEVER DO THIS):
"Here are some questions about your ISMS scope:
1. What is the defined ISMS scope?
2. Which locations are included?
3. Which departments are in scope?"
"""

    else:
        # GAP & RISK ASSESSMENT MODE (55 QUESTIONS)
        return f"""You are Alex, a senior ISO 27001 consultant. 
You are conducting a formal GAP & RISK ASSESSMENT for {org_name}.

🎯 YOUR MISSION:
1. Walk through 55 specific questions from the assessment bank.
2. For each question, follow this flow:
   - STEP 1 (Maturity): Use specific options A-D from the bank.
   - STEP 2 (Optional Context): Ask "Tell me a bit more about how you handle this currently?" (Ask once per gap).
   - STEP 3 (Risk): Evaluate Impact (Low-Critical) and Likelihood (Rare-Very Likely).

⚙️ SCORING (INTERNAL ONLY):
- A: Critical Gap (1/4), B: Partial Gap (2/4), C: Compliant (3/4), D: Best Practice (4/4)

🧠 RULES:
- One question at a time.
- Be professional but warm.
- Do not include suggestions, options arrays, or any "SUGGESTIONS:" text in responses.

{basic_info_text}
KNOWLEDGE BASE:
{kb_context}
"""

# ── Authentication Gate ─────────────────────────────────────────────────────
if "user" not in st.session_state:
    if render_auth_page():
        st.stop()

# ── Session State ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.display = []
    st.session_state.started = False
    st.session_state.user_msg_to_send = ""
    st.session_state.learned_data = ""
    st.session_state.current_question_index = 0
    st.session_state.assessment_complete = False
    st.session_state.gap_complete = False
    st.session_state.risk_complete = False
    st.session_state.current_assessment_phase = None
    st.session_state.isms_policy_complete = False
    st.session_state.isms_policy_question_index = 0
    st.session_state.assessment_answers = []
    st.session_state.gap_assessment_answers = []
    st.session_state.risk_assessment_answers = []
    st.session_state.isms_policy_answers = []
    st.session_state.current_assessment_question = None
    st.session_state.current_assessment_options = []
    st.session_state.alex_responding = False
    # structured ISMS flow
    st.session_state.isms_q_idx = 0
    st.session_state.isms_collected = {}
    st.session_state.isms_repeat_current = {}
    st.session_state.isms_policy_doc_ready = False

def reset_to_home():
    st.session_state.messages = []
    st.session_state.display = []
    st.session_state.started = False
    st.session_state.final_report = None
    st.session_state.basic_info = None
    st.session_state.assessment_mode = False
    st.session_state.current_session_token = ""
    st.session_state.current_question_index = 0
    st.session_state.assessment_complete = False
    st.session_state.gap_complete = False
    st.session_state.risk_complete = False
    st.session_state.current_assessment_phase = None
    st.session_state.isms_policy_complete = False
    st.session_state.assessment_results = []
    st.session_state.user_msg_to_send = ""
    st.session_state.isms_policy_question_index = 0
    st.session_state.assessment_answers = []
    st.session_state.gap_assessment_answers = []
    st.session_state.risk_assessment_answers = []
    st.session_state.isms_policy_answers = []
    st.session_state.current_assessment_question = None
    st.session_state.current_assessment_options = []
    st.session_state.alex_responding = False
    # structured ISMS flow
    st.session_state.isms_q_idx = 0
    st.session_state.isms_collected = {}
    st.session_state.isms_repeat_current = {}
    st.session_state.isms_policy_doc_ready = False
    st.rerun()

def get_session_state_snapshot():
    return {
        "started": bool(st.session_state.get("started")),
        "assessment_mode": bool(st.session_state.get("assessment_mode")),
        "assessment_complete": bool(st.session_state.get("assessment_complete")),
        "gap_complete": bool(st.session_state.get("gap_complete")),
        "risk_complete": bool(st.session_state.get("risk_complete")),
        "current_assessment_phase": st.session_state.get("current_assessment_phase"),
        "isms_policy_complete": bool(st.session_state.get("isms_policy_complete")),
        "isms_policy_question_index": int(st.session_state.get("isms_policy_question_index", 0) or 0),
        "current_question_index": int(st.session_state.get("current_question_index", 0) or 0),
        "assessment_answers": st.session_state.get("assessment_answers", []),
        "gap_assessment_answers": st.session_state.get("gap_assessment_answers", []),
        "risk_assessment_answers": st.session_state.get("risk_assessment_answers", []),
        "isms_policy_answers": st.session_state.get("isms_policy_answers", []),
        "current_assessment_question": st.session_state.get("current_assessment_question"),
        "current_assessment_options": st.session_state.get("current_assessment_options", []),
        "learned_data": st.session_state.get("learned_data", ""),
        "audit_stats": st.session_state.get("audit_stats"),
        "isms_q_idx": int(st.session_state.get("isms_q_idx", 0) or 0),
        "isms_collected": st.session_state.get("isms_collected", {}),
        "isms_repeat_current": st.session_state.get("isms_repeat_current", {}),
        "isms_policy_doc_ready": bool(st.session_state.get("isms_policy_doc_ready", False)),
    }

def restore_session_state_snapshot(state: dict | None):
    state = state or {}
    st.session_state.started = bool(state.get("started", bool(st.session_state.get("started"))))
    st.session_state.assessment_mode = bool(state.get("assessment_mode", False))
    st.session_state.assessment_complete = bool(state.get("assessment_complete", False))
    st.session_state.gap_complete = bool(state.get("gap_complete", state.get("assessment_complete", False)))
    st.session_state.risk_complete = bool(state.get("risk_complete", False))
    st.session_state.current_assessment_phase = state.get("current_assessment_phase")
    st.session_state.isms_policy_complete = bool(state.get("isms_policy_complete", False))
    st.session_state.isms_policy_question_index = int(state.get("isms_policy_question_index", 0) or 0)
    st.session_state.current_question_index = int(state.get("current_question_index", 0) or 0)
    st.session_state.assessment_answers = state.get("assessment_answers", []) or []
    st.session_state.gap_assessment_answers = state.get("gap_assessment_answers", []) or []
    st.session_state.risk_assessment_answers = state.get("risk_assessment_answers", []) or []
    st.session_state.isms_policy_answers = state.get("isms_policy_answers", []) or []
    st.session_state.current_assessment_question = state.get("current_assessment_question")
    st.session_state.current_assessment_options = state.get("current_assessment_options", []) or []
    st.session_state.learned_data = state.get("learned_data", "") or ""
    if state.get("audit_stats") is not None:
        st.session_state.audit_stats = state.get("audit_stats")
    st.session_state.isms_q_idx = int(state.get("isms_q_idx", 0) or 0)
    st.session_state.isms_collected = state.get("isms_collected", {}) or {}
    st.session_state.isms_repeat_current = state.get("isms_repeat_current", {}) or {}
    st.session_state.isms_policy_doc_ready = bool(state.get("isms_policy_doc_ready", False))


# ── Structured ISMS flow helpers ──────────────────────────────────────────────

def _isms_complete() -> str:
    st.session_state.isms_policy_complete = True
    st.session_state.isms_policy_doc_ready = True
    return (
        "✅ **All ISMS Policy questions are complete!**\n\n"
        "I have collected all the information needed for your ISMS Policy Document.\n\n"
        "👇 Click **\"Download ISMS Policy (.docx)\"** below to get your filled policy document, "
        "then proceed to the **Gap Assessment**."
    )


def _isms_record_answer(answer: str) -> bool:
    """Records the answer and advances. Returns True if complete, False if more."""
    idx = int(st.session_state.get("isms_q_idx", 0) or 0)
    if idx >= len(ISMS_STEPS):
        return True

    q = ISMS_STEPS[idx]
    qtype = q["type"]
    group = q.get("group")

    if qtype == "text":
        st.session_state.isms_collected[q["id"]] = answer
        st.session_state.isms_policy_answers.append({"question": q["text"], "answer": answer})
        st.session_state.isms_q_idx = idx + 1

    elif qtype == "repeat_field":
        st.session_state.isms_repeat_current[q["id"]] = answer
        st.session_state.isms_policy_answers.append({"question": q["text"], "answer": answer})
        st.session_state.isms_q_idx = idx + 1

    elif qtype == "repeat_ask":
        entry = dict(st.session_state.get("isms_repeat_current", {}))
        lst = st.session_state.isms_collected.setdefault(group, [])
        lst.append(entry)
        st.session_state.isms_repeat_current = {}
        if answer.strip().lower() in ("yes", "y"):
            for i, qq in enumerate(ISMS_STEPS):
                if qq.get("group") == group and qq["type"] == "repeat_field":
                    st.session_state.isms_q_idx = i
                    break
        else:
            st.session_state.isms_q_idx = idx + 1

    return int(st.session_state.get("isms_q_idx", 0) or 0) >= len(ISMS_STEPS)


def get_next_isms_policy_question():
    idx = int(st.session_state.get("isms_policy_question_index", 0) or 0)
    if idx >= len(ISMS_POLICY_QUESTIONS):
        return None
    item = ISMS_POLICY_QUESTIONS[idx]
    return item.get("question") if isinstance(item, dict) else str(item)


def build_assessment_question_prompt(question_number: int, question_text: str, options: list[str]) -> str:
    prompt_q = f"**Question {question_number}:** {question_text}"
    if options:
        prompt_q += "\n\nPlease choose one option and send it in chat (A/B/C/D/E or full option text):\n"
        prompt_q += "\n".join([f"- {opt}" for opt in options])
    return prompt_q

def normalize_assessment_choice(user_text: str, options: list[str]):
    """
    Returns the canonical option text (e.g., 'B. ...') if user_text matches an option.
    Accepts A/B/C/D style input or the full option text.
    """
    raw = (user_text or "").strip()
    if not raw or not options:
        return None

    # Match by option letter prefix: A / A. / a / a.
    letter_match = re.match(r"^\s*([A-Za-z])(?:[\.\)\-:\s].*)?$", raw)
    if letter_match:
        letter = letter_match.group(1).upper()
        for opt in options:
            if opt.upper().startswith(f"{letter}."):
                return opt

    # Match by exact full option text (case-insensitive)
    normalized_raw = re.sub(r"\s+", " ", raw).strip().lower()
    for opt in options:
        if normalized_raw == re.sub(r"\s+", " ", opt).strip().lower():
            return opt

    return None


def format_clause_description_for_ui(text: str) -> str:
    """Render clause description in a readable HTML-friendly way."""
    desc = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    desc = re.sub(r"\s+", " ", desc).strip()
    desc = re.sub(r"\s([a-z]\))\s", r"<br>\1 ", desc)
    desc = re.sub(r"\s(\d+\))\s", r"<br>\1 ", desc)
    desc = re.sub(r"\s(NOTE(?:\s+\d+)?)\s", r"<br><br>\1 ", desc)
    desc = re.sub(r"\s[—-]\s", r"<br>- ", desc)
    # Make long semicolon chains easier to read.
    desc = re.sub(r";\s+", ".<br>", desc)
    desc = re.sub(r"\.\s*<br>(?=\s*[a-z]\))", "<br>", desc)
    desc = re.sub(r"(<br>){3,}", "<br><br>", desc)
    return html.escape(desc, quote=False).replace("&lt;br&gt;", "<br>")


def reconstruct_isms_answers_from_display(display_log, question_bank):
    answers = []
    if not display_log or not question_bank:
        return answers

    user_replies = []
    for msg in display_log:
        role = msg.get("role")
        text = str(msg.get("content", ""))
        if role == "assistant" and ("Let's begin the Gap Assessment" in text or "Let's begin the Risk Assessment" in text):
            break
        if role == "user":
            user_replies.append(text.strip())

    for idx, reply in enumerate(user_replies):
        if idx >= len(question_bank):
            break
        q_item = question_bank[idx]
        q_text = q_item.get("question") if isinstance(q_item, dict) else str(q_item)
        answers.append({"question": q_text, "answer": reply})
    return answers


def reconstruct_assessment_answers_from_display(display_log, assessment_bank):
    answers = []
    if not display_log or not assessment_bank:
        return answers

    current_q_idx = None
    current_q_text = None
    waiting_for_user = False

    for msg in display_log:
        role = msg.get("role")
        content = str(msg.get("content", ""))
        if role == "assistant":
            m = re.search(r"\*\*Question\s+(\d+):\*\*\s*(.+)", content)
            if m:
                q_num = int(m.group(1))
                q_text = m.group(2).strip()
                current_q_idx = q_num - 1
                current_q_text = q_text
                waiting_for_user = True
        elif role == "user" and waiting_for_user and current_q_idx is not None:
            if 0 <= current_q_idx < len(assessment_bank):
                q_item = assessment_bank[current_q_idx]
                clause = q_item.get("clause")
                answers.append(
                    {
                        "question_index": current_q_idx,
                        "clause": clause,
                        "question": current_q_text or q_item.get("question"),
                        "selected": content.strip(),
                    }
                )
            waiting_for_user = False
    return answers


def reconstruct_assessment_answers_from_display_phase(
    display_log,
    phase_start_text: str,
    phase_end_text: str | None,
    assessment_bank,
):
    """
    Reconstruct a phase's MCQ answers from chat history safely.
    Stops when the next phase starts (prevents gap/risk mixing).
    """
    answers = []
    if not display_log or not assessment_bank:
        return answers

    in_phase = False
    current_q_idx = None
    current_q_text = None
    waiting_for_user = False

    for msg in display_log:
        role = msg.get("role")
        content = str(msg.get("content", ""))

        if role == "assistant":
            if not in_phase and phase_start_text in content:
                in_phase = True
                waiting_for_user = False
                current_q_idx = None
                current_q_text = None
                continue
            if in_phase and phase_end_text and phase_end_text in content:
                break

            if in_phase:
                m = re.search(r"\*\*Question\s+(\d+):\*\*\s*(.+)", content)
                if m:
                    q_num = int(m.group(1))
                    q_text = m.group(2).strip()
                    current_q_idx = q_num - 1
                    current_q_text = q_text
                    waiting_for_user = True
            continue

        if role == "user" and in_phase and waiting_for_user and current_q_idx is not None:
            if 0 <= current_q_idx < len(assessment_bank):
                q_item = assessment_bank[current_q_idx]
                answers.append(
                    {
                        "question_index": current_q_idx,
                        "clause": q_item.get("clause"),
                        "question": current_q_text or q_item.get("question"),
                        "selected": content.strip(),
                    }
                )
            waiting_for_user = False

    return answers


def get_active_assessment_bank():
    phase = st.session_state.get("current_assessment_phase")
    if phase == "risk":
        return RISK_ASSESSMENT_QUESTIONS
    return GAP_ASSESSMENT_QUESTIONS

def inject_next_question_system_message(next_question: str):
    """
    Adds a transient system instruction telling Alex which single topic to ask next.
    This message is added to `messages` only (not `display`) so the user never sees it.
    """
    if not next_question:
        return
    st.session_state.messages.append(
        {
            "role": "system",
            "content": (
                "INSTRUCTION: Ask ONE next question that covers this exact audit intent.\n"
                f"{next_question}\n"
                "Do not copy it verbatim. Rephrase it in a warm, human, conversational way "
                "(natural audit dialogue, not rigid or interrogative wording). "
                "Do not ask any other questions."
            ),
        }
    )

def _start_assessment_phase(phase_name: str):
    st.session_state.assessment_mode = True
    st.session_state.current_assessment_phase = phase_name
    st.session_state.messages = []
    st.session_state.display = []
    st.session_state.final_report = None
    # Keep the same session token so completion state updates the same audit record.
    st.session_state.current_question_index = 0
    st.session_state.assessment_complete = False
    if phase_name == "gap":
        st.session_state.gap_assessment_answers = []
        st.session_state.gap_complete = False
    else:
        st.session_state.risk_assessment_answers = []
        st.session_state.risk_complete = False
    bank = GAP_ASSESSMENT_QUESTIONS if phase_name == "gap" else RISK_ASSESSMENT_QUESTIONS

    if not st.session_state.get("basic_info"):
        st.session_state.started = False
    else:
        system_prompt = get_system_prompt(kb_context, st.session_state.basic_info, assessment_mode=True)
        st.session_state.messages = [{"role": "system", "content": system_prompt}]

        first_q = bank[0] if bank else {"question": "No assessment questions found."}
        st.session_state.current_assessment_question = first_q
        # JSONL format: options is a dict A-D; questions.json format: options is a list
        opts = []
        if isinstance(first_q.get("options"), dict):
            opts = [f"{k}. {v}" for k, v in first_q["options"].items()]
        elif isinstance(first_q.get("options"), list):
            # If the PDF parser already returned "A. ...", keep as-is.
            if first_q["options"] and re.match(r"^\s*[A-E]\s*[.)]", str(first_q["options"][0]), re.IGNORECASE):
                opts = [str(opt).strip() for opt in first_q["options"]]
            else:
                opts = [f"{chr(65+i)}. {opt}" for i, opt in enumerate(first_q["options"])]
        st.session_state.current_assessment_options = opts

        phase_label = "Gap Assessment" if phase_name == "gap" else "Risk Assessment"
        prompt_q = f"Let's begin the {phase_label}.\n\n" + build_assessment_question_prompt(
            1,
            first_q.get("question", ""),
            opts,
        )
        st.session_state.display.append({"role": "assistant", "content": prompt_q})
        st.session_state.started = True
    st.rerun()


def start_gap_assessment():
    _start_assessment_phase("gap")


def start_risk_assessment():
    _start_assessment_phase("risk")

def generate_final_report():
    if not st.session_state.get("isms_policy_answers"):
        st.session_state.isms_policy_answers = reconstruct_isms_answers_from_display(
            st.session_state.get("display", []),
            ISMS_POLICY_QUESTIONS,
        )
    if not st.session_state.get("gap_assessment_answers"):
        st.session_state.gap_assessment_answers = reconstruct_assessment_answers_from_display_phase(
            st.session_state.get("display", []),
            phase_start_text="Let's begin the Gap Assessment",
            phase_end_text="Let's begin the Risk Assessment",
            assessment_bank=GAP_ASSESSMENT_QUESTIONS,
        )
    if not st.session_state.get("risk_assessment_answers"):
        st.session_state.risk_assessment_answers = reconstruct_assessment_answers_from_display_phase(
            st.session_state.get("display", []),
            phase_start_text="Let's begin the Risk Assessment",
            phase_end_text=None,
            assessment_bank=RISK_ASSESSMENT_QUESTIONS,
        )
    st.session_state.assessment_answers = (
        st.session_state.get("gap_assessment_answers", [])
        + st.session_state.get("risk_assessment_answers", [])
    )

    # Stats based on Gap & Risk Logic.pdf
    gap_counts = {
        "Critical Gap": 0,
        "Major Gap": 0,
        "Partial Gap": 0,
        "Minor Gap": 0,
        "No Gap": 0,
    }
    risk_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}

    def _gap_map(letter: str):
        m = {"A": ("Critical Gap", 1), "B": ("Major Gap", 2), "C": ("Partial Gap", 3), "D": ("Minor Gap", 4), "E": ("No Gap", 5)}
        return m.get(letter, ("Partial Gap", 3))

    def _risk_map(letter: str):
        n = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}.get(letter, 3)
        l = n
        i = n
        score = l * i
        if score >= 17:
            level = "Critical"
        elif score >= 13:
            level = "High"
        elif score >= 6:
            level = "Medium"
        else:
            level = "Low"
        return l, i, score, level

    for ans in st.session_state.get("gap_assessment_answers", []):
        selected = str(ans.get("selected", "")).strip().upper()
        letter = selected[:1] if selected else ""
        gap_status, _score = _gap_map(letter)
        gap_counts[gap_status] = gap_counts.get(gap_status, 0) + 1

    for ans in st.session_state.get("risk_assessment_answers", []):
        selected = str(ans.get("selected", "")).strip().upper()
        letter = selected[:1] if selected else ""
        _l, _i, _score, level = _risk_map(letter)
        risk_counts[level] = risk_counts.get(level, 0) + 1

    st.session_state.audit_stats = {
        "gap_counts": gap_counts,
        "risk_counts": risk_counts,
    }
    st.session_state.final_report = "Final report data prepared."
    st.session_state.display.append({"role": "assistant", "content": "✅ Final report is ready for DOCX download."})

    uid = st.session_state.get("user", {}).get("id")
    token = st.session_state.get("current_session_token", "")
    if uid and token:
        update_audit_session(
            session_token=token,
            chat_log=st.session_state.display,
            messages=st.session_state.messages,
            final_report=st.session_state.final_report,
            is_complete=True,
            state=get_session_state_snapshot(),
        )
    st.toast("Audit submitted successfully!", icon="🎉")
    st.rerun()

def get_workflow_step():
    if st.session_state.get("final_report"):
        return 5
    if st.session_state.get("assessment_mode"):
        return 3 if st.session_state.get("current_assessment_phase") == "gap" else 4
    if st.session_state.get("basic_info"):
        if not st.session_state.get("isms_policy_complete"):
            return 2
        if not st.session_state.get("gap_complete"):
            return 3
        if not st.session_state.get("risk_complete"):
            return 4
        return 5
    return 1

def workflow_card_html(step_number, title, completed, active, description):
    state_class = "completed" if completed else "active" if active else "pending"
    status_text = "Completed" if completed else "Current step" if active else "Pending"
    icon = "✓" if completed else str(step_number)
    return (
        f'<div class="workflow-step {state_class}">'
        f'<div class="workflow-kicker">Step {icon}</div>'
        f'<div class="workflow-title">{title}</div>'
        f'<div class="workflow-status"><strong>{status_text}</strong><br>{description}</div>'
        f'</div>'
    )

def render_audit_history():
    user_id = st.session_state.get("user", {}).get("id")
    if not user_id:
        return

    history = get_user_audit_history(user_id)
    if not history:
        return

    st.markdown("<div class='card-title'>🕒 Your Audit History</div>", unsafe_allow_html=True)
    for idx, h in enumerate(history):
        label = f"{'✅' if h.get('is_complete') else '⏳'} {h.get('organization', 'Unknown')}  —  {h.get('date', '')}"
        with st.expander(label):
            st.write(f"**Employee:** {h.get('employee_name', 'Unknown')}")
            if h.get("is_complete"):
                st.success("Audit completed — final report generated.")
            else:
                st.warning("Audit in progress or incomplete.")

            hc1, hc2 = st.columns(2)
            with hc1:
                if st.button("Resume / View", key=f"resume_btn_{idx}", use_container_width=True):
                    st.session_state.basic_info = h.get('basic_info', {})
                    st.session_state.display = h.get('chat_log', [])
                    st.session_state.messages = h.get('messages', [])
                    st.session_state.started = True
                    st.session_state.final_report = h.get("final_report", "")
                    st.session_state.current_session_token = h.get("session_token", "")
                    restore_session_state_snapshot(h.get("state", {}))
                    if not st.session_state.get("isms_policy_answers"):
                        st.session_state.isms_policy_answers = reconstruct_isms_answers_from_display(
                            st.session_state.get("display", []),
                            ISMS_POLICY_QUESTIONS,
                        )
                    if not st.session_state.get("gap_assessment_answers"):
                        st.session_state.gap_assessment_answers = reconstruct_assessment_answers_from_display_phase(
                            st.session_state.get("display", []),
                            phase_start_text="Let's begin the Gap Assessment",
                            phase_end_text="Let's begin the Risk Assessment",
                            assessment_bank=GAP_ASSESSMENT_QUESTIONS,
                        )
                    if not st.session_state.get("risk_assessment_answers"):
                        st.session_state.risk_assessment_answers = reconstruct_assessment_answers_from_display_phase(
                            st.session_state.get("display", []),
                            phase_start_text="Let's begin the Risk Assessment",
                            phase_end_text=None,
                            assessment_bank=RISK_ASSESSMENT_QUESTIONS,
                        )
                    st.rerun()
            with hc2:
                if st.button("🗑️ Delete", key=f"del_btn_{idx}", use_container_width=True):
                    delete_audit_session(h["session_token"], user_id)
                    st.rerun()

def render_workflow_section():
    current_step = get_workflow_step()
    st.markdown(
        '<div class="workflow-row">'
        + workflow_card_html(
            1,
            "Basic Information",
            bool(st.session_state.get("basic_info")),
            current_step == 1,
            "Fill the initial company and employee details to begin the audit.",
        )
        + workflow_card_html(
            2,
            "ISMS Policy",
            bool(st.session_state.get("isms_policy_complete")),
            current_step == 2,
            "Complete the Alex chat for the ISMS policy discussion.",
        )
        + workflow_card_html(
            3,
            "Gap Assessment",
            bool(st.session_state.get("gap_complete")),
            current_step == 3,
            "Run the gap assessment questionnaire.",
        )
        + workflow_card_html(
            4,
            "Risk Assessment",
            bool(st.session_state.get("risk_complete")),
            current_step == 4,
            "Run the risk assessment questionnaire.",
        )
        + workflow_card_html(
            5,
            "Generate Report",
            bool(st.session_state.get("final_report")),
            current_step == 5,
            "Generate and download the final ISO 27001 report in DOCX format.",
        )
        + '</div>',
        unsafe_allow_html=True,
    )

    step_col1, step_col2, step_col3, step_col4, step_col5 = st.columns(5)
    with step_col1:
        st.button(
            "✓ Basic Information Saved" if st.session_state.get("basic_info") else "Complete Basic Information",
            key=f"workflow_basic_info_btn_{current_step}",
            use_container_width=True,
            disabled=True,
            help="This step is completed after the initial details form is submitted.",
        )
    with step_col2:
        st.button(
            "✓ ISMS Policy Completed" if st.session_state.get("isms_policy_complete") else "ISMS Policy In Progress",
            key=f"workflow_isms_btn_{current_step}",
            use_container_width=True,
            disabled=True,
            help="This step is completed after Alex finishes the ISMS policy conversation.",
        )
    with step_col3:
        gap_enabled = (
            st.session_state.get("basic_info")
            and st.session_state.get("isms_policy_complete")
            and not st.session_state.get("gap_complete")
            and not st.session_state.get("assessment_mode")
        )
        step3_label = "✓ Gap Assessment Completed" if st.session_state.get("gap_complete") else "Start Gap Assessment"
        if st.button(
            step3_label,
            key=f"workflow_gap_btn_{current_step}",
            type="secondary",
            use_container_width=True,
            disabled=not gap_enabled,
            help="Available after the ISMS Policy step is complete.",
        ):
            start_gap_assessment()
    with step_col4:
        risk_enabled = (
            st.session_state.get("basic_info")
            and st.session_state.get("isms_policy_complete")
            and st.session_state.get("gap_complete")
            and not st.session_state.get("risk_complete")
            and not st.session_state.get("assessment_mode")
        )
        step4_label = "✓ Risk Assessment Completed" if st.session_state.get("risk_complete") else "Start Risk Assessment"
        if st.button(
            step4_label,
            key=f"workflow_risk_btn_{current_step}",
            type="secondary",
            use_container_width=True,
            disabled=not risk_enabled,
            help="Available after gap assessment is complete.",
        ):
            start_risk_assessment()
    with step_col5:
        final_enabled = (
            st.session_state.get("started")
            and st.session_state.get("gap_complete")
            and st.session_state.get("risk_complete")
            and not st.session_state.get("final_report")
        )
        if st.session_state.get("final_report"):
            combined_assessment_answers = (
                st.session_state.get("gap_assessment_answers", [])
                + st.session_state.get("risk_assessment_answers", [])
            )
            if not combined_assessment_answers:
                combined_assessment_answers = st.session_state.get("assessment_answers", [])
            docx_buffer = create_structured_docx_report(
                basic_info=st.session_state.get("basic_info", {}),
                isms_answers=st.session_state.get("isms_policy_answers", []),
                gap_assessment_answers=st.session_state.get("gap_assessment_answers", []),
                risk_assessment_answers=st.session_state.get("risk_assessment_answers", []),
                clause_metadata=kb_data,
            )
            st.download_button(
                label="✓ Download Report (.docx)",
                key=f"workflow_docx_download_{current_step}",
                data=docx_buffer,
                file_name="ISO27001_Official_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary",
            )
        else:
            if st.button(
                "Generate Report",
                key=f"workflow_generate_btn_{current_step}",
                type="primary",
                use_container_width=True,
                disabled=not final_enabled,
                help="Available after the gap and risk analysis is complete.",
            ):
                generate_final_report()

# ── Top Nav ───────────────────────────────────────────────────────────────────
user_info = st.session_state.get("user", {})
user_full_name = user_info.get("full_name", "User")
user_initials = "".join(p[0].upper() for p in user_full_name.split()[:2])

col_nav_left, col_nav_right = st.columns([8, 1])
with col_nav_left:
    shield_emoji = "🛡️"
    topbar_html = f"""
<div class="topbar">
  <div class="brand">
    <div class="brand-icon">{shield_emoji}</div>
    <div>
      <div class="brand-name">ComplianceEye</div>
      <div class="brand-sub">ISO 27001 AI Auditor</div>
    </div>
  </div>
  <div style="display:flex; align-items:center; gap:12px;">
    <div class="nav-pill"><span class="live-dot"></span> Alex is Online</div>
    <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;box-shadow:0 4px 14px rgba(99,102,241,0.4);" title="{user_full_name}">{user_initials}</div>
    <div style="font-size:0.78rem;font-weight:600;color:#4f46e5;">Hi, {user_full_name.split()[0]}!</div>
  </div>
</div>
"""
    st.markdown(topbar_html, unsafe_allow_html=True)
with col_nav_right:
    if st.button("Logout", key="logout_btn", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ── Sidebar Navigation ──
with st.sidebar:
    st.markdown("### 🛠️ Audit Controls")
    if st.button("🔄 Start New Audit", use_container_width=True, type="primary"):
        reset_to_home()
    
    st.divider()
    st.markdown("### 📚 Resources")
    st.info("Alex is ready to help you with your ISO 27001 compliance journey.")

# ── Stats Row ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="stat-row">
  <div class="stat-box"><div class="stat-num">{total_controls}</div><div class="stat-lbl">Controls</div></div>
  <div class="stat-box"><div class="stat-num">10</div><div class="stat-lbl">Clauses</div></div>
  <div class="stat-box"><div class="stat-num">93</div><div class="stat-lbl">Annex A</div></div>
  <div class="stat-box"><div class="stat-num">AI</div><div class="stat-lbl">Powered</div></div>
</div>
""", unsafe_allow_html=True)

# ── Main Layout ───────────────────────────────────────────────────────────────
left, right = st.columns([3, 1.2], gap="large")

# ── RIGHT: Knowledge Panel ────────────────────────────────────────────────────
with right:
    render_audit_history()
    st.markdown('<br>', unsafe_allow_html=True)

    # ── Upload Section (Learning) ──
    st.markdown('<div class="card-title">🧠 Alex\'s Knowledge Base</div>', unsafe_allow_html=True)
    if st.session_state.get('learned_data'):
        st.info("Alex is currently using additional context from your uploaded documents.")
    else:
        st.write("Upload documents in the chat area to feed Alex more data.")

    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📚 ISO 27001 Clauses</div>', unsafe_allow_html=True)

    # Group controls
    categories = {}
    is_annex = False
    for item in kb_data:
        cid = item.get("control_id", "").strip()
        title = item.get("title", "")
        # Detect transition to Annex A controls (which start at 5.1 again)
        if cid == "5.1" and "Policies for information security" in title:
            is_annex = True
        
        main_cat_num = cid.split(".")[0]
        if not is_annex:
            cat_name = f"Clause {main_cat_num}"
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(item)
        else:
            cat_name = f"Annex A.{main_cat_num}"
            if cat_name not in categories:
                categories[cat_name] = []
            categories[cat_name].append(item)

    # ── Dropdown for category selection ──
    cat_list = list(categories.keys())
    selected_cat = st.selectbox("Select Clause / Category", cat_list, label_visibility="collapsed")

    # ── Display sub-clauses for selected category ──
    sub_clauses = categories[selected_cat]
    st.markdown('<div class="kb-scroll">', unsafe_allow_html=True)
    for item in sub_clauses:
        cid = item.get("control_id", "")
        title = item.get("title", "")
        desc = format_clause_description_for_ui(item.get("description", ""))
        st.markdown(f"""
        <div class="kb-item">
          <div class="kb-cid">{cid if not is_annex or cid.startswith('A.') else f"A.{cid}"}</div>
          <div class="kb-title">{title}</div>
          <div class="kb-desc">{desc}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── LEFT: Chat Panel ──────────────────────────────────────────────────────────
with left:
    chat_title_col, chat_action_col = st.columns([4.5, 1.2])
    with chat_title_col:
        st.markdown('<div class="card-title">💬 Audit Session</div>', unsafe_allow_html=True)
    with chat_action_col:
        if st.session_state.started:
            if st.button("← Back to Home", key="back_to_home_btn", use_container_width=True):
                reset_to_home()

    if not st.session_state.started:
        start_screen_html = "<div class=\"start-screen\" style=\"padding-bottom: 20px;\"><div class=\"start-icon\">&#128737;</div><div class=\"start-title\">Meet Alex, Your AI Auditor</div><div class=\"start-sub\">Alex is a certified ISO 27001 Lead Auditor trained on the full ISO/IEC 27001:2022 standard. He'll conduct a real audit conversation - one question at a time.</div><div class=\"feature-grid\"><span class=\"feature-tag\">✓ All 10 Clauses</span><span class=\"feature-tag\">✓ 93 Annex A Controls</span><span class=\"feature-tag\">✓ Human-Like</span><span class=\"feature-tag\">✓ GPT Powered</span></div></div>"
        st.markdown(start_screen_html, unsafe_allow_html=True)

        st.markdown("<h4 style='text-align:center; color:#1e1b4b; margin-top:0px;'>Setup Employee & Organization Details</h4>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#64748b; font-size:0.85rem; margin-bottom:30px;'>Provide your details below to save time during the audit.</p>", unsafe_allow_html=True)
        
        with st.form("organization_intro_form"):
            st.markdown("##### 👤 Employee Details")
            st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
            ec1, ec2 = st.columns([1, 1], gap="large")
            with ec1:
                emp_name = st.text_input("Full Name", placeholder="e.g. John Doe")
                emp_email = st.text_input("Email Address", placeholder="e.g. john@example.com")
            with ec2:
                emp_contact = st.text_input("Contact Number", placeholder="e.g. +1 234 567 890")
                emp_role = st.text_input("Role in Organization", placeholder="e.g. Compliance Officer")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("##### 🏢 Organization & Introduction (10 Questions)")
            st.markdown("<div style='margin-bottom: 20px;'>", unsafe_allow_html=True)
            
            r1c1, r1c2 = st.columns([1, 1], gap="large")
            with r1c1: org_name = st.text_input("1. Legal name of your organization?", placeholder="e.g. Acme Corp")
            with r1c2: business_nature = st.text_input("2. What is the nature of your business?", placeholder="e.g. Software Development")

            r2c1, r2c2 = st.columns([1, 1], gap="large")
            with r2c1: services = st.text_area("3. What services/products do you provide?", height=68)
            with r2c2: is_mission = st.text_area("4. Organization's mission regarding info security?", height=68)

            r3c1, r3c2 = st.columns([1, 1], gap="large")
            with r3c1: is_importance = st.text_area("5. Why is info security important for your business?", height=68)
            with r3c2: stakeholders = st.text_area("6. Who are your key stakeholders (clients, regulators)?", height=68)

            r4c1, r4c2 = st.columns([1, 1], gap="large")
            with r4c1: stakeholder_exp = st.text_area("7. What are stakeholder security expectations?", height=68)
            with r4c2: isms_responsible = st.text_input("8. Who is responsible for ISMS at top level?", placeholder="e.g. Chief Information Security Officer (CISO)")

            r5c1, r5c2 = st.columns([1, 1], gap="large")
            with r5c1: isms_core_group = st.text_area("9. Do you have an ISMS core group? List members and roles", height=68)
            with r5c2: mgmt_commitment = st.text_area("10. How does management demonstrate commitment?", height=68)
            st.markdown("</div>", unsafe_allow_html=True)
            
            submit_form = st.form_submit_button("🚀 Submit & Begin Audit with Alex", use_container_width=True)

        if submit_form:
            basic_info = {
                "emp_name": emp_name,
                "emp_email": emp_email,
                "emp_contact": emp_contact,
                "emp_role": emp_role,
                "org_name": org_name,
                "business_nature": business_nature,
                "services": services,
                "is_mission": is_mission,
                "is_importance": is_importance,
                "stakeholders": stakeholders,
                "stakeholder_exp": stakeholder_exp,
                "isms_responsible": isms_responsible,
                "isms_core_group": isms_core_group,
                "mgmt_commitment": mgmt_commitment
            }
            
            # Validation: ensure all fields are filled
            missing = False
            for val in basic_info.values():
                if not val.strip():
                    missing = True
                    break
                    
            if missing:
                st.error("⚠️ Please fill in all the details (both Employee and Organization) before beginning the audit.")
            else:
                st.session_state.basic_info = basic_info
                st.session_state.isms_policy_answers = []
                # ── seed isms_collected from form data ──
                st.session_state.isms_collected = {
                    "org_name":     basic_info.get("org_name", ""),
                    "org_email":    basic_info.get("emp_email", ""),
                    "org_business": basic_info.get("business_nature", ""),
                    "auditor_name": basic_info.get("emp_name", ""),
                    "org_location": "", "org_employees": "", "org_it_infra": "",
                }
                st.session_state.isms_q_idx = 0
                st.session_state.isms_repeat_current = {}
                st.session_state.isms_policy_doc_ready = False
                first_q = ISMS_STEPS[0]
                step_label = STEP_LABELS.get(first_q["step"], "")
                intro = (
                    f"Thanks, {basic_info.get('emp_name')}! Basic info captured for **{basic_info.get('org_name')}**.\n\n"
                    f"I will now guide you through {len(ISMS_STEPS)} questions across 12 sections.\n\n"
                    f"📋 **{step_label}**\n\n{first_q['text']}"
                )
                st.session_state.messages = [{"role": "assistant", "content": intro}]
                st.session_state.display = [{"role": "assistant", "content": intro}]
                st.session_state.started = True
                uid = st.session_state.get("user", {}).get("id")
                if uid:
                    token = save_audit_session(
                        user_id=uid, basic_info=basic_info,
                        chat_log=st.session_state.display,
                        messages=st.session_state.messages,
                        state=get_session_state_snapshot(),
                    )
                    st.session_state.current_session_token = token
                st.rerun()
                
        render_workflow_section()

    else:
        # Chat history
        chat_html = '<div class="chat-scroll">'
        # We iterate in reverse so the newest message is at the bottom in a column-reverse flex container
        for msg in reversed(st.session_state.display):
            if msg["role"] == "assistant":
                chat_html += f"""
                <div class="msg-row">
                  <div class="avatar-chip avatar-alex">&#128737;</div>
                  <div class="bubble-wrap">
                    <div class="bubble bubble-alex">{msg["content"]}</div>
                    <div class="bubble-time">Alex - Lead Auditor</div>
                  </div>
                </div>"""
            else:
                chat_html += f"""
                <div class="msg-row user-row">
                  <div class="avatar-chip avatar-user">&#128100;</div>
                  <div class="bubble-wrap user-wrap">
                    <div class="bubble bubble-user">{msg["content"]}</div>
                    <div class="bubble-time" style="text-align:right;">You</div>
                  </div>
                </div>"""
        if st.session_state.get("alex_responding"):
            chat_html += """
            <div class="msg-row">
              <div class="avatar-chip avatar-alex">&#128737;</div>
              <div class="bubble-wrap">
                <div class="bubble bubble-alex">Alex is responding...</div>
                <div class="bubble-time">Alex - Lead Auditor</div>
              </div>
            </div>"""
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        # ── ISMS Policy document download (appears once all questions answered) ──
        if st.session_state.get("isms_policy_doc_ready") and not st.session_state.get("assessment_mode"):
            st.info("📄 Your ISMS Policy document is ready! Download it below, then proceed to Gap Assessment.")
            try:
                policy_buf = build_isms_policy_docx(st.session_state.get("isms_collected", {}))
                st.download_button(
                    label="⬇️ Download ISMS Policy (.docx)",
                    data=policy_buf,
                    file_name="ISMS_Policy_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="isms_policy_download_btn",
                )
            except Exception as _e:
                st.error(f"Could not generate policy document: {_e}")


        # Input + Send
        def submit_chat():
            text = st.session_state.chat_in.strip()
            if text:
                st.session_state.user_msg_to_send = text
            st.session_state.chat_in = ""

        # ── Modern Chat Capsule UI ──
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.8, 6, 0.8], gap="small")
            
            with c1:
                with st.popover("➕", use_container_width=True):
                    st.markdown("### Attach Documents")
                    uploaded_files = st.file_uploader("Upload", type=["pdf", "png", "jpg", "jpeg"], 
                                                     accept_multiple_files=True, label_visibility="collapsed", key="chat_upload")
                    if uploaded_files:
                        new_learned = ""
                        for uploaded_file in uploaded_files:
                            with st.spinner(f"Alex reading {uploaded_file.name}..."):
                                if uploaded_file.type == "application/pdf":
                                    text = extract_text_from_pdf(uploaded_file)
                                else:
                                    text = extract_text_from_image(uploaded_file)
                                new_learned += f"\n--- Data from {uploaded_file.name} ---\n{text}\n"
                        
                        if new_learned:
                            st.session_state.learned_data = f"\n### ADDITIONAL LEARNED CONTEXT FROM USER DOCUMENTS:\n{new_learned}\n"
                            st.toast("Alex has updated his knowledge base!", icon="🧠")

            with c2:
                st.text_input(
                    "reply",
                    placeholder="Ask anything...",
                    label_visibility="collapsed",
                    key="chat_in",
                    on_change=submit_chat,
                )
                
            with c3:
                st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                st.button("↑", use_container_width=True, type="primary", on_click=submit_chat, help="Send Message")

        render_workflow_section()

        if st.session_state.get("user_msg_to_send"):
            user_text = st.session_state.user_msg_to_send
            st.session_state.user_msg_to_send = ""
            
            # Assessment mode: local option submission flow (no extra AI "thank you" response)
            if st.session_state.get("assessment_mode"):
                opts = st.session_state.get("current_assessment_options") or []
                selected_opt = normalize_assessment_choice(user_text, opts)
                if not opts:
                    selected_opt = user_text.strip()
                active_bank = get_active_assessment_bank()
                active_phase = st.session_state.get("current_assessment_phase") or "gap"

                # Always show what the user submitted in chat
                st.session_state.messages.append({"role": "user", "content": user_text})
                st.session_state.display.append({"role": "user", "content": user_text})

                if not selected_opt:
                    opts = st.session_state.get("current_assessment_options") or []
                    opts_str = "\n".join([f"- {opt}" for opt in opts]) if opts else ""
                    assist_msg = (
                        "Please submit one valid option for this question (A/B/C/D/E or paste the full option text).\n"
                        + (("\n" + opts_str) if opts_str else "")
                    )
                    st.session_state.messages.append({"role": "assistant", "content": assist_msg})
                    st.session_state.display.append({"role": "assistant", "content": assist_msg})
                else:
                    q = st.session_state.get("current_assessment_question") or {}
                    record = {
                        "question_index": st.session_state.get("current_question_index", 0),
                        "clause": q.get("clause"),
                        "question": q.get("question"),
                        "selected": selected_opt,
                    }
                    st.session_state.assessment_answers.append(record)
                    if active_phase == "gap":
                        st.session_state.gap_assessment_answers.append(record)
                    else:
                        st.session_state.risk_assessment_answers.append(record)

                    st.session_state.current_question_index += 1
                    if st.session_state.current_question_index >= len(active_bank):
                        if active_phase == "gap":
                            st.session_state.gap_complete = True
                            completion_msg = f"✅ **Gap Assessment Complete!**\n\nAll {len(active_bank)} gap questions are answered. You can now proceed to Risk Assessment."
                        else:
                            st.session_state.risk_complete = True
                            completion_msg = f"✅ **Risk Assessment Complete!**\n\nAll {len(active_bank)} risk questions are answered. You can now generate the final report."
                        st.session_state.assessment_complete = bool(st.session_state.get("gap_complete")) and bool(st.session_state.get("risk_complete"))
                        st.session_state.assessment_mode = False
                        st.session_state.current_assessment_phase = None
                        st.session_state.display.append({"role": "assistant", "content": completion_msg})
                    else:
                        next_q = active_bank[st.session_state.current_question_index]
                        st.session_state.current_assessment_question = next_q
                        next_opts = []
                        if isinstance(next_q.get("options"), dict):
                            next_opts = [f"{k}. {v}" for k, v in next_q["options"].items()]
                        elif isinstance(next_q.get("options"), list):
                            if next_q["options"] and re.match(r"^\s*[A-E]\s*[.)]", str(next_q["options"][0]), re.IGNORECASE):
                                next_opts = [str(opt).strip() for opt in next_q["options"]]
                            else:
                                next_opts = [f"{chr(65+i)}. {opt}" for i, opt in enumerate(next_q["options"])]
                        st.session_state.current_assessment_options = next_opts

                        prompt_q = build_assessment_question_prompt(
                            st.session_state.current_question_index + 1,
                            next_q.get("question", ""),
                            next_opts,
                        )
                        st.session_state.messages.append({"role": "assistant", "content": prompt_q})
                        st.session_state.display.append({"role": "assistant", "content": prompt_q})

                # Persist every MCQ answer to history.
                uid = st.session_state.get("user", {}).get("id")
                token = st.session_state.get("current_session_token", "")
                if uid and token:
                    update_audit_session(
                        session_token=token,
                        chat_log=st.session_state.display,
                        messages=st.session_state.messages,
                        state=get_session_state_snapshot(),
                    )
            else:
                # ── STRUCTURED ISMS POLICY FLOW (AI-assisted) ─────
                st.session_state.messages.append({"role": "user", "content": user_text})
                st.session_state.display.append({"role": "user", "content": user_text})

                if st.session_state.get("started") and not st.session_state.get("isms_policy_complete"):
                    is_done = _isms_record_answer(user_text)
                    
                    if is_done:
                        reply = _isms_complete()
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        st.session_state.display.append({"role": "assistant", "content": reply})
                    else:
                        new_idx = int(st.session_state.get("isms_q_idx", 0) or 0)
                        next_q = ISMS_STEPS[new_idx]
                        prev_step = ISMS_STEPS[new_idx - 1]["step"] if new_idx > 0 else None
                        header = ""
                        if next_q["step"] != prev_step:
                            header = f"\n\n📋 **{STEP_LABELS.get(next_q['step'], '')}**\n\n"

                        st.session_state.alex_responding = True
                        try:
                            # Prompt the AI to ask the next question humanistically
                            system_prompt = (
                                "You are Alex, a friendly and experienced ISO 27001 Lead Auditor. "
                                "The user just answered a question about their ISMS policy. "
                                "Acknowledge their answer briefly, warmly, and humanistically. "
                                "Then, you MUST ask the following exact next question to progress the audit:\n\n"
                                f"QUESTION TO ASK:\n{next_q['text']}\n\n"
                                "If relevant, weave in a tiny bit of ISO 27001 context or best practices. "
                                "Do NOT ask any other questions. Just ask the target question provided."
                            )
                            # Temporarily inject this system prompt just for this turn
                            msgs = list(st.session_state.messages)
                            msgs.append({"role": "system", "content": system_prompt})
                            
                            r = client.chat.completions.create(
                                model=OPENAI_MODEL, messages=msgs,
                                temperature=0.75, max_tokens=350)
                            ai_reply = r.choices[0].message.content
                            
                            # Append the step header to the AI's reply if we changed steps
                            display_reply = header + ai_reply
                        finally:
                            st.session_state.alex_responding = False

                        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                        st.session_state.display.append({"role": "assistant", "content": display_reply})
            
            # Auto-save progress to SQLite after each AI response
            uid = st.session_state.get("user", {}).get("id")
            token = st.session_state.get("current_session_token", "")
            if uid and token:
                update_audit_session(
                    session_token=token,
                    chat_log=st.session_state.display,
                    messages=st.session_state.messages,
                    state=get_session_state_snapshot(),
                )
            st.rerun()

        if st.session_state.get("final_report"):
            # ── Dashboard Section ──
            stats = st.session_state.get("audit_stats")
            if stats:
                st.markdown('<div class="card-title">📊 Assessment Insights</div>', unsafe_allow_html=True)
                c_gap, c_risk = st.columns(2)
                with c_gap:
                    import plotly.graph_objects as go
                    gap_data = stats.get(
                        "gap_counts",
                        {"Critical Gap": 0, "Major Gap": 0, "Partial Gap": 0, "Minor Gap": 0, "No Gap": 0},
                    )
                    fig_gap = go.Figure(
                        data=[
                            go.Pie(
                                labels=list(gap_data.keys()),
                                values=list(gap_data.values()),
                                hole=0.4,
                                marker_colors=['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#10b981'],
                            )
                        ]
                    )
                    fig_gap.update_layout(title_text="Gap Analysis", height=300, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig_gap, use_container_width=True)
                with c_risk:
                    risk_data = stats.get("risk_counts", {"Critical": 0, "High": 0, "Medium": 0, "Low": 0})
                    fig_risk = go.Figure(data=[go.Bar(x=list(risk_data.keys()), y=list(risk_data.values()), marker_color=['#b91c1c', '#dc2626', '#f59e0b', '#3b82f6'])])
                    fig_risk.update_layout(title_text="Risk Severity", height=300, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig_risk, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.success("The final report is ready. Use the Step 5 box above to download the DOCX file.")