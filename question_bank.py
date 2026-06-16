import os
import re

import pdfplumber
import streamlit as st

from project_paths import (
    GAP_ASSESSMENT_PDF_PATH,
    ISMS_POLICY_PDF_PATH,
    RISK_ASSESSMENT_PDF_PATH,
)


@st.cache_data
def load_assessment_questions_from_pdf(pdf_path: str):
    if not os.path.exists(pdf_path):
        return []

    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
    except Exception:
        return []

    questions = []
    current = None
    option_pat = re.compile(r"^([A-E])(?:[.)]\s*|\s+)(.+)$", re.IGNORECASE)
    q_pat = re.compile(r"^(\d+(?:\.\d+)*)[.)]\s*(.+)$")

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        q_match = q_pat.match(line)
        opt_match = option_pat.match(line)

        if q_match:
            if current and current.get("question"):
                questions.append(current)
            current = {"clause": q_match.group(1), "question": q_match.group(2).strip(), "options": []}
            continue

        if opt_match and current:
            current["options"].append(f"{opt_match.group(1).upper()}. {opt_match.group(2).strip()}")
            continue

        if current:
            if current["options"]:
                current["options"][-1] = f"{current['options'][-1]} {line}".strip()
            else:
                current["question"] = f"{current['question']} {line}".strip()

    if current and current.get("question"):
        questions.append(current)
    return questions


@st.cache_data
def load_isms_policy_questions_from_pdf():
    if not os.path.exists(ISMS_POLICY_PDF_PATH):
        return []

    text = ""
    try:
        with pdfplumber.open(ISMS_POLICY_PDF_PATH) as pdf:
            for page in pdf.pages:
                text += "\n" + (page.extract_text() or "")
    except Exception:
        return []

    section = ""
    questions = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\d+\.\s+", line):
            section = line
            continue
        if line.startswith("- "):
            questions.append({"section": section or "ISMS Policy", "question": line[2:].strip()})
    return questions


def load_question_banks():
    return {
        "gap": load_assessment_questions_from_pdf(GAP_ASSESSMENT_PDF_PATH),
        "risk": load_assessment_questions_from_pdf(RISK_ASSESSMENT_PDF_PATH),
        "isms_policy": load_isms_policy_questions_from_pdf(),
    }
