import html
import os
import re

import streamlit as st
from openai import OpenAI

from auth_page import render_auth_page
from database import (
    delete_audit_session,
    get_user_audit_history,
    init_db,
    save_audit_session,
    update_audit_session,
)
from document_processing import extract_text_from_image, extract_text_from_pdf
from isms_policy_builder import build_isms_policy_docx
from isms_questions import ISMS_STEPS, REPEAT_FIELDS, STEP_LABELS
from knowledge_base import build_context, load_kb
from question_bank import load_question_banks
from report_builder import create_structured_docx_report


def clean_ui_text(value):
    text = str(value or "")
    text = "".join(ch if ord(ch) < 128 else " " for ch in text)
    text = text.replace("?", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_openai_settings():
    try:
        from config import OPENAI_API_KEY, OPENAI_MODEL
    except ImportError:
        OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
        OPENAI_MODEL = "gpt-4o-mini"
    return OPENAI_API_KEY, OPENAI_MODEL


def init_session_state():
    defaults = {
        "started": False,
        "messages": [],
        "display": [],
        "basic_info": {},
        "learned_data": "",
        "current_session_token": "",
        "isms_policy_answers": [],
        "isms_policy_question_index": 0,
        "isms_policy_complete": False,
        # ── structured ISMS flow ──
        "isms_q_idx": 0,                 # index into ISMS_STEPS
        "isms_collected": {},            # flat dict of all scalar answers
        "isms_repeat_group": None,       # active repeating group name
        "isms_repeat_current": {},       # partial entry being built
        "isms_repeat_field_idx": 0,      # which field within the group
        "isms_policy_doc_ready": False,  # True once policy DOCX is generated
        # ── assessment ──
        "assessment_mode": False,
        "current_assessment_phase": None,
        "current_question_index": 0,
        "current_assessment_question": None,
        "current_assessment_options": [],
        "assessment_answers": [],
        "gap_assessment_answers": [],
        "risk_assessment_answers": [],
        "gap_complete": False,
        "risk_complete": False,
        "final_report": "",
        "audit_stats": {},
        "user_msg_to_send": "",
        "chat_in": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def get_session_state_snapshot():
    keys = [
        "started",
        "basic_info",
        "display",
        "messages",
        "isms_policy_answers",
        "isms_policy_question_index",
        "isms_policy_complete",
        "isms_q_idx",
        "isms_collected",
        "isms_repeat_group",
        "isms_repeat_current",
        "isms_repeat_field_idx",
        "isms_policy_doc_ready",
        "assessment_mode",
        "current_assessment_phase",
        "current_question_index",
        "current_assessment_question",
        "current_assessment_options",
        "assessment_answers",
        "gap_assessment_answers",
        "risk_assessment_answers",
        "gap_complete",
        "risk_complete",
        "final_report",
        "audit_stats",
        "learned_data",
    ]
    return {key: st.session_state.get(key) for key in keys}


def restore_session_state_snapshot(state):
    for key, value in (state or {}).items():
        st.session_state[key] = value


def persist_session(is_complete=False):
    user_id = st.session_state.get("user", {}).get("id")
    token = st.session_state.get("current_session_token")
    if user_id and token:
        update_audit_session(
            session_token=token,
            chat_log=st.session_state.display,
            messages=st.session_state.messages,
            final_report=st.session_state.get("final_report", ""),
            is_complete=is_complete,
            state=get_session_state_snapshot(),
        )


def reset_to_home():
    keep_user = st.session_state.get("user")
    keep_auth = st.session_state.get("authenticated")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    if keep_user:
        st.session_state.user = keep_user
        st.session_state.authenticated = keep_auth
    init_session_state()
    st.rerun()


def get_workflow_step():
    if st.session_state.get("final_report"):
        return 5
    if st.session_state.get("assessment_mode"):
        return 3 if st.session_state.get("current_assessment_phase") == "gap" else 4
    if not st.session_state.get("basic_info"):
        return 1
    if not st.session_state.get("isms_policy_complete"):
        return 2
    if not st.session_state.get("gap_complete"):
        return 3
    if not st.session_state.get("risk_complete"):
        return 4
    return 5


def workflow_card_html(step_number, title, completed, active, description):
    state_class = "completed" if completed else "active" if active else "pending"
    status = "Completed" if completed else "Current step" if active else "Pending"
    return (
        f'<div class="workflow-step {state_class}">'
        f'<div class="workflow-kicker">Step {step_number}</div>'
        f'<div class="workflow-title">{html.escape(title)}</div>'
        f'<div class="workflow-status"><strong>{status}</strong><br>{html.escape(description)}</div>'
        "</div>"
    )


def build_assessment_question_prompt(number, question_text, options):
    option_lines = "\n".join(options)
    return f"Question {number}\n\n{question_text}\n\nOptions:\n{option_lines}\n\nReply with A, B, C, D, or E."


def normalize_assessment_choice(user_text, options):
    text = str(user_text or "").strip()
    if not text:
        return ""
    first = text[0].upper()
    for option in options:
        if option.upper().startswith(f"{first}.") or option.upper().startswith(f"{first})"):
            return option
    for option in options:
        if text.lower() == option.lower() or text.lower() in option.lower():
            return option
    return ""


def options_from_question(question):
    options = question.get("options", [])
    if isinstance(options, dict):
        return [f"{key}. {value}" for key, value in options.items()]
    if isinstance(options, list):
        normalized = []
        for idx, option in enumerate(options):
            option_text = str(option).strip()
            if re.match(r"^[A-E][.)]\s+", option_text, re.IGNORECASE):
                normalized.append(option_text)
            else:
                normalized.append(f"{chr(65 + idx)}. {option_text}")
        return normalized
    return []


def format_clause_description_for_ui(text):
    desc = clean_ui_text(text)
    desc = re.sub(r"\s+-\s+", "<br>- ", desc)
    return html.escape(desc)


def get_next_isms_policy_question(isms_questions):
    idx = int(st.session_state.get("isms_policy_question_index", 0) or 0)
    if idx >= len(isms_questions):
        return None
    item = isms_questions[idx]
    return item.get("question", "") if isinstance(item, dict) else str(item)


def start_assessment_phase(phase_name, bank):
    if not bank:
        st.warning(f"No {phase_name} questions were loaded.")
        return
    st.session_state.assessment_mode = True
    st.session_state.current_assessment_phase = phase_name
    st.session_state.current_question_index = 0
    st.session_state.current_assessment_question = bank[0]
    st.session_state.current_assessment_options = options_from_question(bank[0])
    prompt = build_assessment_question_prompt(
        1,
        bank[0].get("question", ""),
        st.session_state.current_assessment_options,
    )
    title = "Gap Assessment" if phase_name == "gap" else "Risk Assessment"
    st.session_state.display.append({"role": "assistant", "content": f"Let's begin the {title}.\n\n{prompt}"})
    st.session_state.messages.append({"role": "assistant", "content": prompt})
    persist_session()
    st.rerun()


def calculate_stats():
    gap_counts = {"Critical Gap": 0, "Major Gap": 0, "Partial Gap": 0, "Minor Gap": 0, "No Gap": 0}
    risk_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}

    for item in st.session_state.get("gap_assessment_answers", []):
        selected = str(item.get("selected", "")).upper()
        if selected.startswith("A"):
            gap_counts["Critical Gap"] += 1
        elif selected.startswith("B"):
            gap_counts["Major Gap"] += 1
        elif selected.startswith("C"):
            gap_counts["Partial Gap"] += 1
        elif selected.startswith("D"):
            gap_counts["Minor Gap"] += 1
        else:
            gap_counts["No Gap"] += 1

    for item in st.session_state.get("risk_assessment_answers", []):
        selected = str(item.get("selected", "")).upper()
        if selected.startswith("A"):
            risk_counts["Critical"] += 1
        elif selected.startswith("B"):
            risk_counts["High"] += 1
        elif selected.startswith("C"):
            risk_counts["Medium"] += 1
        else:
            risk_counts["Low"] += 1

    return {"gap_counts": gap_counts, "risk_counts": risk_counts}


def generate_final_report():
    st.session_state.audit_stats = calculate_stats()
    st.session_state.final_report = "Final report is ready for DOCX download."
    st.session_state.display.append({"role": "assistant", "content": st.session_state.final_report})
    persist_session(is_complete=True)
    st.rerun()


def render_css():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Sora', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.stApp {
    background: #f0f4ff;
    background-image:
        radial-gradient(at 20% 10%, #dbeafe 0px, transparent 55%),
        radial-gradient(at 80% 0%, #ede9fe 0px, transparent 50%),
        radial-gradient(at 5% 90%, #d1fae5 0px, transparent 45%),
        radial-gradient(at 90% 85%, #fce7f3 0px, transparent 45%);
}
.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 0 22px;
    border-bottom: 1px solid rgba(99,102,241,0.15);
    margin-bottom: 24px;
}
.brand { display:flex; align-items:center; gap:10px; }
.brand-icon {
    width: 40px; height: 40px; border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #fff; display:flex; align-items:center; justify-content:center;
    font-weight:800;
}
.brand-name { font-size:1.25rem; font-weight:800; color:#1e1b4b; }
.brand-sub { font-size:.7rem; color:#6366f1; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }
.nav-pill {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color:white; border-radius:999px; padding:7px 16px; font-size:.78rem; font-weight:700;
}
.stat-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }
.stat-box {
    background:rgba(255,255,255,.72); border:1px solid rgba(99,102,241,.14);
    border-radius:14px; padding:16px; text-align:center;
}
.stat-num { font-size:1.4rem; color:#4f46e5; font-weight:800; }
.stat-lbl { color:#64748b; font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; }
.card-title {
    color:#4f46e5; font-size:.78rem; font-weight:800; letter-spacing:.14em;
    text-transform:uppercase; margin:14px 0 14px;
}
.workflow-row { display:grid; grid-template-columns:repeat(5,minmax(150px,1fr)); gap:16px; margin:6px 0 16px; }
.workflow-step {
    min-height:140px; padding:20px; background:rgba(255,255,255,.75);
    border:1px solid rgba(99,102,241,.12); border-radius:22px;
}
.workflow-step.active { border-color:#6366f1; background:rgba(238,242,255,.82); }
.workflow-step.completed { border-color:#22c55e; background:rgba(240,253,244,.82); }
.workflow-kicker { color:#6366f1; font-weight:800; font-size:.76rem; letter-spacing:.12em; text-transform:uppercase; }
.workflow-title { color:#0f172a; font-weight:800; margin:12px 0; }
.workflow-status { color:#52677f; font-size:.88rem; line-height:1.45; }
.chat-scroll {
    min-height:360px; max-height:560px; overflow-y:auto; padding:18px;
    background:rgba(255,255,255,.55); border:1px solid rgba(99,102,241,.12); border-radius:18px;
}
.msg-row { display:flex; margin-bottom:14px; }
.msg-row.user-row { justify-content:flex-end; }
.bubble {
    max-width:760px; padding:13px 16px; border-radius:14px;
    line-height:1.55; white-space:pre-wrap;
}
.bubble-alex { background:white; color:#172554; border:1px solid rgba(99,102,241,.14); }
.bubble-user { background:#4f46e5; color:white; }
.bubble-time { color:#64748b; font-size:.72rem; margin-top:4px; }
.kb-scroll { max-height:420px; overflow-y:auto; }
.kb-item {
    background:rgba(255,255,255,.7); border:1px solid rgba(99,102,241,.12);
    border-radius:12px; padding:12px; margin-bottom:10px;
}
.kb-cid { color:#4f46e5; font-weight:800; font-size:.76rem; }
.kb-title { color:#0f172a; font-weight:700; margin:4px 0; }
.kb-desc { color:#52677f; font-size:.82rem; line-height:1.45; }
@media (max-width: 1000px) {
    .workflow-row, .stat-row { grid-template-columns:1fr; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_audit_history(isms_questions, gap_questions, risk_questions):
    user_id = st.session_state.get("user", {}).get("id")
    if not user_id:
        return
    history = get_user_audit_history(user_id)
    if not history:
        return

    st.markdown('<div class="card-title">Your Audit History</div>', unsafe_allow_html=True)
    for idx, item in enumerate(history):
        status = "Completed" if item.get("is_complete") else "In progress"
        organization = clean_ui_text(item.get("organization", "Unknown"))
        date = clean_ui_text(item.get("date", ""))
        with st.expander(f"{status} - {organization} - {date}"):
            st.write(f"Employee: {clean_ui_text(item.get('employee_name', 'Unknown'))}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Resume / View", key=f"resume_{idx}", use_container_width=True):
                    st.session_state.basic_info = item.get("basic_info", {})
                    st.session_state.display = [
                        {"role": msg.get("role", ""), "content": clean_ui_text(msg.get("content", ""))}
                        for msg in item.get("chat_log", [])
                    ]
                    st.session_state.messages = item.get("messages", [])
                    st.session_state.current_session_token = item.get("session_token", "")
                    restore_session_state_snapshot(item.get("state", {}))
                    st.session_state.started = True
                    st.rerun()
            with col2:
                if st.button("Delete", key=f"delete_{idx}", use_container_width=True):
                    delete_audit_session(item["session_token"], user_id)
                    st.rerun()


def render_workflow_section(gap_questions, risk_questions, kb_data):
    current_step = get_workflow_step()
    st.markdown(
        '<div class="workflow-row">'
        + workflow_card_html(
            1,
            "Basic Information",
            bool(st.session_state.get("basic_info")),
            current_step == 1,
            "Fill the company and employee details.",
        )
        + workflow_card_html(
            2,
            "ISMS Policy",
            bool(st.session_state.get("isms_policy_complete")),
            current_step == 2,
            "Complete the ISMS policy discussion.",
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
            "Generate and download the DOCX report.",
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.button("Basic Information Saved" if st.session_state.get("basic_info") else "Complete Basic Information", disabled=True, use_container_width=True)
    with col2:
        st.button("ISMS Policy Completed" if st.session_state.get("isms_policy_complete") else "ISMS Policy In Progress", disabled=True, use_container_width=True)
    with col3:
        enabled = st.session_state.get("isms_policy_complete") and not st.session_state.get("gap_complete") and not st.session_state.get("assessment_mode")
        label = "Gap Assessment Completed" if st.session_state.get("gap_complete") else "Start Gap Assessment"
        if st.button(label, disabled=not enabled, use_container_width=True):
            start_assessment_phase("gap", gap_questions)
    with col4:
        enabled = st.session_state.get("gap_complete") and not st.session_state.get("risk_complete") and not st.session_state.get("assessment_mode")
        label = "Risk Assessment Completed" if st.session_state.get("risk_complete") else "Start Risk Assessment"
        if st.button(label, disabled=not enabled, use_container_width=True):
            start_assessment_phase("risk", risk_questions)
    with col5:
        if st.session_state.get("final_report"):
            buffer = create_structured_docx_report(
                basic_info=st.session_state.get("basic_info", {}),
                isms_answers=st.session_state.get("isms_policy_answers", []),
                gap_assessment_answers=st.session_state.get("gap_assessment_answers", []),
                risk_assessment_answers=st.session_state.get("risk_assessment_answers", []),
                clause_metadata=kb_data,
            )
            st.download_button(
                "Download Report (.docx)",
                data=buffer,
                file_name="ISO27001_Official_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        else:
            enabled = st.session_state.get("gap_complete") and st.session_state.get("risk_complete")
            if st.button("Generate Report", disabled=not enabled, use_container_width=True):
                generate_final_report()


def render_topbar():
    user = st.session_state.get("user", {})
    name = clean_ui_text(user.get("full_name", "User")) or "User"
    initials = "".join(part[0].upper() for part in name.split()[:2]) or "U"
    left, right = st.columns([8, 1])
    with left:
        st.markdown(
            f"""
<div class="topbar">
  <div class="brand">
    <div class="brand-icon">CE</div>
    <div>
      <div class="brand-name">ComplianceEye</div>
      <div class="brand-sub">ISO 27001 AI Auditor</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:12px;">
    <div class="nav-pill">Alex is Online</div>
    <div style="background:#4f46e5;color:white;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:.8rem;font-weight:700;">{initials}</div>
    <div style="font-size:.78rem;font-weight:700;color:#4f46e5;">Hi, {html.escape(name.split()[0])}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def render_sidebar():
    with st.sidebar:
        st.markdown("### Audit Controls")
        if st.button("Start New Audit", use_container_width=True, type="primary"):
            reset_to_home()
        st.divider()
        st.markdown("### Resources")
        st.info("Alex is ready to help with your ISO 27001 compliance journey.")


def render_start_form(isms_questions, kb_context):
    st.markdown('<div class="card-title">Audit Session</div>', unsafe_allow_html=True)
    st.markdown(
        """
<div style="text-align:center;padding:18px 8px 24px;">
  <div style="font-size:1.6rem;font-weight:800;color:#1e1b4b;">Meet Alex, Your AI Auditor</div>
  <div style="color:#64748b;margin-top:8px;">Complete the setup form to begin the guided ISO 27001 audit.</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("organization_intro_form"):
        st.markdown("##### Employee Details")
        ec1, ec2 = st.columns(2)
        with ec1:
            emp_name = st.text_input("Full Name")
            emp_email = st.text_input("Email Address")
        with ec2:
            emp_contact = st.text_input("Contact Number")
            emp_role = st.text_input("Role in Organization")

        st.markdown("##### Organization and Introduction")
        c1, c2 = st.columns(2)
        with c1:
            org_name = st.text_input("1. Legal name of your organization?")
            services = st.text_area("3. What services/products do you provide?", height=68)
            is_importance = st.text_area("5. Why is information security important?", height=68)
            stakeholder_exp = st.text_area("7. What are stakeholder security expectations?", height=68)
            isms_core_group = st.text_area("9. Do you have an ISMS core group?", height=68)
        with c2:
            business_nature = st.text_input("2. What is the nature of your business?")
            is_mission = st.text_area("4. Organization mission regarding information security?", height=68)
            stakeholders = st.text_area("6. Who are your key stakeholders?", height=68)
            isms_responsible = st.text_input("8. Who is responsible for ISMS at top level?")
            mgmt_commitment = st.text_area("10. How does management demonstrate commitment?", height=68)

        submitted = st.form_submit_button("Submit and Begin Audit", use_container_width=True)

    if not submitted:
        return

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
        "mgmt_commitment": mgmt_commitment,
    }
    if any(not str(value).strip() for value in basic_info.values()):
        st.error("Please fill in all details before beginning the audit.")
        return

    st.session_state.basic_info = basic_info
    st.session_state.started = True

    # ── Seed collected with basic_info values so template has them too ────
    st.session_state.isms_collected = {
        "org_name":     org_name,
        "org_email":    emp_email,
        "org_business": business_nature,
        "org_location": "",
        "org_employees": "",
        "org_it_infra": "",
        "auditor_name": emp_name,
    }
    st.session_state.isms_q_idx = 0

    # Skip org-name question since we already have it; jump to question index 1 (org_email)
    # Actually start from 0 so Alex asks every structured question fresh
    first_q = ISMS_STEPS[0]
    step_label = STEP_LABELS.get(first_q["step"], "")
    intro = (
        f"Thanks, {emp_name}! I have captured your basic information for **{org_name}**.\n\n"
        f"Now I will guide you through the complete ISMS Policy documentation — "
        f"{len(ISMS_STEPS)} questions across 12 sections.\n\n"
        f"📋 **{step_label}**\n\n"
        f"{first_q['text']}"
    )
    st.session_state.display = [{"role": "assistant", "content": intro}]
    st.session_state.messages = [{"role": "assistant", "content": intro}]

    user_id = st.session_state.get("user", {}).get("id")
    if user_id:
        st.session_state.current_session_token = save_audit_session(
            user_id=user_id,
            basic_info=basic_info,
            chat_log=st.session_state.display,
            messages=st.session_state.messages,
            state=get_session_state_snapshot(),
        )
    st.rerun()


def render_chat(isms_questions):
    st.markdown('<div class="card-title">Audit Session</div>', unsafe_allow_html=True)
    if st.button("Back to Home", use_container_width=False):
        reset_to_home()

    chat_html = '<div class="chat-scroll">'
    for msg in st.session_state.display:
        role = msg.get("role", "")
        content = html.escape(clean_ui_text(msg.get("content", ""))).replace("\n", "<br>")
        if role == "assistant":
            chat_html += f'<div class="msg-row"><div><div class="bubble bubble-alex">{content}</div><div class="bubble-time">Alex - Lead Auditor</div></div></div>'
        else:
            chat_html += f'<div class="msg-row user-row"><div><div class="bubble bubble-user">{content}</div><div class="bubble-time" style="text-align:right;">You</div></div></div>'
    chat_html += "</div>"
    st.markdown(chat_html, unsafe_allow_html=True)

    # ── ISMS Policy document download (shown as soon as all Qs answered) ──
    if st.session_state.get("isms_policy_doc_ready") and not st.session_state.get("assessment_mode"):
        st.info("📄 Your ISMS Policy document is ready. Download it below, then start the Gap Assessment.")
        try:
            policy_buf = build_isms_policy_docx(st.session_state.get("isms_collected", {}))
            st.download_button(
                label="⬇️ Download ISMS Policy (.docx)",
                data=policy_buf,
                file_name="ISMS_Policy_Document.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Could not generate policy document: {e}")

    def submit_chat():
        text = st.session_state.chat_in.strip()
        if text:
            st.session_state.user_msg_to_send = text
        st.session_state.chat_in = ""

    # hide chat input once ISMS is complete and we are not in assessment mode
    isms_done = st.session_state.get("isms_policy_complete", False)
    in_assessment = st.session_state.get("assessment_mode", False)
    show_input = (not isms_done) or in_assessment

    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 6, 1])
        with c1:
            with st.popover("Attach", use_container_width=True):
                files = st.file_uploader(
                    "Upload documents",
                    type=["pdf", "png", "jpg", "jpeg"],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                )
                if files:
                    learned = []
                    for uploaded in files:
                        text = extract_text_from_pdf(uploaded) if uploaded.type == "application/pdf" else extract_text_from_image(uploaded)
                        learned.append(f"Data from {uploaded.name}\n{text}")
                    st.session_state.learned_data = "\n\n".join(learned)
                    st.toast("Alex has updated his knowledge base.")
        with c2:
            if show_input:
                st.text_input("reply", placeholder="Type your response...", label_visibility="collapsed", key="chat_in", on_change=submit_chat)
            else:
                st.info("ISMS Policy complete. Use the workflow buttons above to proceed.")
        with c3:
            if show_input:
                st.button("Send", type="primary", use_container_width=True, on_click=submit_chat)

    if st.session_state.get("user_msg_to_send"):
        handle_user_message(st.session_state.user_msg_to_send, isms_questions)
        st.session_state.user_msg_to_send = ""
        st.rerun()


# ── ISMS structured-flow helpers ──────────────────────────────────────────

def _isms_next_question_text():
    """Return (question_text, step_label_or_none) for the current ISMS_STEPS index."""
    idx = st.session_state.isms_q_idx
    if idx >= len(ISMS_STEPS):
        return None, None
    q = ISMS_STEPS[idx]
    # Step label prefix if first question of this step
    prev_step = ISMS_STEPS[idx - 1]["step"] if idx > 0 else None
    label = STEP_LABELS.get(q["step"]) if q["step"] != prev_step else None
    return q["text"], label


def _isms_advance(answer: str):
    """
    Process one answer for the structured ISMS flow.
    Returns the reply text to show the user.
    """
    idx = st.session_state.isms_q_idx
    if idx >= len(ISMS_STEPS):
        return _isms_complete()

    q = ISMS_STEPS[idx]
    qtype = q["type"]
    group = q.get("group")

    if qtype == "text":
        st.session_state.isms_collected[q["id"]] = answer
        # record for legacy isms_policy_answers too
        st.session_state.isms_policy_answers.append({"question": q["text"], "answer": answer})
        st.session_state.isms_q_idx += 1

    elif qtype == "repeat_field":
        # accumulate fields in isms_repeat_current
        st.session_state.isms_repeat_current[q["id"]] = answer
        st.session_state.isms_policy_answers.append({"question": q["text"], "answer": answer})
        st.session_state.isms_q_idx += 1

    elif qtype == "repeat_ask":
        # this is the "add another?" prompt
        # Save current entry into the list
        entry = dict(st.session_state.isms_repeat_current)
        lst = st.session_state.isms_collected.setdefault(group, [])
        lst.append(entry)
        st.session_state.isms_repeat_current = {}
        ans_lower = answer.strip().lower()
        if ans_lower in ("yes", "y"):
            # Go back to first field of this group
            fields = REPEAT_FIELDS.get(group, [])
            # find index of first field of this group
            for i, qq in enumerate(ISMS_STEPS):
                if qq.get("group") == group and qq["type"] == "repeat_field":
                    st.session_state.isms_q_idx = i
                    break
        else:
            # move past the repeat_ask question
            st.session_state.isms_q_idx += 1

    # Check if all done
    if st.session_state.isms_q_idx >= len(ISMS_STEPS):
        return _isms_complete()

    # Build next question text
    next_q = ISMS_STEPS[st.session_state.isms_q_idx]
    prev_step = ISMS_STEPS[st.session_state.isms_q_idx - 1]["step"] if st.session_state.isms_q_idx > 0 else None
    header = ""
    if next_q["step"] != prev_step:
        header = f"\n\n📋 **{STEP_LABELS.get(next_q['step'], '')}**\n\n"

    count_done = st.session_state.isms_q_idx
    total = len(ISMS_STEPS)
    progress = f"[{count_done}/{total}]"
    return f"Got it! {progress}{header}{next_q['text']}"


def _isms_complete() -> str:
    st.session_state.isms_policy_complete = True
    st.session_state.isms_policy_doc_ready = True
    return (
        "✅ **All ISMS Policy questions are complete!**\n\n"
        "I have collected all the information needed for your ISMS Policy Document.\n\n"
        "👇 Click **\"Download ISMS Policy (.docx)\"** below to get your filled policy document, "
        "then proceed to the **Gap Assessment**."
    )


def handle_user_message(user_text, isms_questions):
    user_text = clean_ui_text(user_text)
    st.session_state.display.append({"role": "user", "content": user_text})
    st.session_state.messages.append({"role": "user", "content": user_text})

    if st.session_state.get("assessment_mode"):
        handle_assessment_answer(user_text)
        persist_session()
        return

    # ── Use structured ISMS flow ──────────────────────────────────────────
    if not st.session_state.get("isms_policy_complete"):
        reply = _isms_advance(user_text)
        st.session_state.display.append({"role": "assistant", "content": reply})
        st.session_state.messages.append({"role": "assistant", "content": reply})
        persist_session()
        return

    # Fallback if somehow reached here post-completion
    persist_session()


def handle_assessment_answer(user_text):
    options = st.session_state.get("current_assessment_options") or []
    selected = normalize_assessment_choice(user_text, options) if options else user_text
    if not selected:
        st.session_state.display.append({"role": "assistant", "content": "Please submit a valid option: A, B, C, D, or E."})
        return

    phase = st.session_state.get("current_assessment_phase")
    bank_key = "gap_bank" if phase == "gap" else "risk_bank"
    bank = st.session_state.get(bank_key, [])
    question = st.session_state.get("current_assessment_question") or {}
    record = {
        "question_index": st.session_state.get("current_question_index", 0),
        "clause": question.get("clause"),
        "question": question.get("question"),
        "selected": selected,
    }
    st.session_state.assessment_answers.append(record)
    if phase == "gap":
        st.session_state.gap_assessment_answers.append(record)
    else:
        st.session_state.risk_assessment_answers.append(record)

    st.session_state.current_question_index += 1
    if st.session_state.current_question_index >= len(bank):
        if phase == "gap":
            st.session_state.gap_complete = True
            message = "Gap Assessment Complete. You can now proceed to Risk Assessment."
        else:
            st.session_state.risk_complete = True
            message = "Risk Assessment Complete. You can now generate the final report."
        st.session_state.assessment_mode = False
        st.session_state.current_assessment_phase = None
        st.session_state.display.append({"role": "assistant", "content": message})
        return

    next_question = bank[st.session_state.current_question_index]
    st.session_state.current_assessment_question = next_question
    st.session_state.current_assessment_options = options_from_question(next_question)
    prompt = build_assessment_question_prompt(
        st.session_state.current_question_index + 1,
        next_question.get("question", ""),
        st.session_state.current_assessment_options,
    )
    st.session_state.display.append({"role": "assistant", "content": prompt})
    st.session_state.messages.append({"role": "assistant", "content": prompt})


def render_right_panel(kb_data, isms_questions, gap_questions, risk_questions):
    render_audit_history(isms_questions, gap_questions, risk_questions)
    st.markdown('<div class="card-title">Alex Knowledge Base</div>', unsafe_allow_html=True)
    if st.session_state.get("learned_data"):
        st.info("Alex is using additional context from your uploaded documents.")
    else:
        st.write("Upload documents in the chat area to feed Alex more data.")

    st.markdown('<div class="card-title">ISO 27001 Clauses</div>', unsafe_allow_html=True)
    categories = {}
    for item in kb_data:
        cid = str(item.get("control_id", "")).strip()
        group = f"Clause {cid.split('.')[0]}" if cid else "Other"
        categories.setdefault(group, []).append(item)
    if not categories:
        st.info("No ISO metadata loaded.")
        return
    selected = st.selectbox("Select Clause / Category", list(categories.keys()), label_visibility="collapsed")
    st.markdown('<div class="kb-scroll">', unsafe_allow_html=True)
    for item in categories[selected]:
        cid = html.escape(clean_ui_text(item.get("control_id", "")))
        title = html.escape(clean_ui_text(item.get("title", "")))
        desc = format_clause_description_for_ui(item.get("description", ""))
        st.markdown(
            f'<div class="kb-item"><div class="kb-cid">{cid}</div><div class="kb-title">{title}</div><div class="kb-desc">{desc}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def run_app():
    st.set_page_config(
        page_title="ComplianceEye - ISO 27001 AI Auditor",
        page_icon="CE",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_db()
    if not render_auth_page():
        st.stop()

    init_session_state()
    render_css()

    question_banks = load_question_banks()
    gap_questions = question_banks["gap"]
    risk_questions = question_banks["risk"]
    isms_questions = question_banks["isms_policy"]
    st.session_state.gap_bank = gap_questions
    st.session_state.risk_bank = risk_questions

    kb_data = load_kb()
    kb_context = build_context(kb_data)
    total_controls = len(kb_data)

    render_topbar()
    render_sidebar()

    st.markdown(
        f"""
<div class="stat-row">
  <div class="stat-box"><div class="stat-num">{total_controls}</div><div class="stat-lbl">Controls</div></div>
  <div class="stat-box"><div class="stat-num">10</div><div class="stat-lbl">Clauses</div></div>
  <div class="stat-box"><div class="stat-num">93</div><div class="stat-lbl">Annex A</div></div>
  <div class="stat-box"><div class="stat-num">AI</div><div class="stat-lbl">Powered</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 1.2], gap="large")
    with right:
        render_right_panel(kb_data, isms_questions, gap_questions, risk_questions)

    with left:
        if not st.session_state.started:
            render_start_form(isms_questions, kb_context)
            render_workflow_section(gap_questions, risk_questions, kb_data)
        else:
            render_chat(isms_questions)
            render_workflow_section(gap_questions, risk_questions, kb_data)
            if st.session_state.get("final_report"):
                st.success("The final report is ready. Use the Step 5 download button.")
