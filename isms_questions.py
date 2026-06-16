"""
ISMS Policy question flow matching ISMS Doc MP.docx master prompt.
Each question has: id, text, field (dot-path into collected_data), step, type.
Types: text | choice | repeat_start | repeat_end | repeat_add
"""

ISMS_STEPS = [
    # ── STEP 1: Organisation Details ──────────────────────────────────────
    {"id": "org_name",       "step": 1, "type": "text",
     "text": "What is your Organization Name?"},
    {"id": "org_email",      "step": 1, "type": "text",
     "text": "What is your Organization Email?"},
    {"id": "org_business",   "step": 1, "type": "text",
     "text": "What is the Nature of your Business?"},
    {"id": "org_location",   "step": 1, "type": "text",
     "text": "What are your Office Location(s)?"},
    {"id": "org_employees",  "step": 1, "type": "text",
     "text": "How many Employees does your organization have?"},
    {"id": "org_it_infra",   "step": 1, "type": "text",
     "text": "What is your IT Infrastructure type? (On-Premise / Cloud / Hybrid)"},

    # ── STEP 2: Audit Details ──────────────────────────────────────────────
    {"id": "audit_type",     "step": 2, "type": "text",
     "text": "What type of audit is this? (Internal / External)"},
    {"id": "audit_date",     "step": 2, "type": "text",
     "text": "What is the Audit Date?"},
    {"id": "auditor_name",   "step": 2, "type": "text",
     "text": "What is the Auditor's Name?"},
    {"id": "dept_audited",   "step": 2, "type": "text",
     "text": "Which Department is being audited?"},

    # ── STEP 3: Management & ISMS Team (5 roles) ──────────────────────────
    {"id": "ceo_name",       "step": 3, "type": "text",
     "text": "What is the Name of your CEO / Director?"},
    {"id": "ceo_dept",       "step": 3, "type": "text",
     "text": "Which Department is the CEO / Director in?"},
    {"id": "ceo_contact",    "step": 3, "type": "text",
     "text": "What is the CEO / Director's Contact (email/phone)?"},

    {"id": "isms_mgr_name",  "step": 3, "type": "text",
     "text": "What is the Name of your ISMS Manager?"},
    {"id": "isms_mgr_dept",  "step": 3, "type": "text",
     "text": "Which Department is the ISMS Manager in?"},
    {"id": "isms_mgr_contact","step": 3,"type": "text",
     "text": "What is the ISMS Manager's Contact (email/phone)?"},

    {"id": "hr_name",        "step": 3, "type": "text",
     "text": "What is the Name of your HR Head?"},
    {"id": "hr_dept",        "step": 3, "type": "text",
     "text": "Which Department is the HR Head in?"},
    {"id": "hr_contact",     "step": 3, "type": "text",
     "text": "What is the HR Head's Contact (email/phone)?"},

    {"id": "sysadmin_name",  "step": 3, "type": "text",
     "text": "What is the Name of your System Administrator?"},
    {"id": "sysadmin_dept",  "step": 3, "type": "text",
     "text": "Which Department is the System Administrator in?"},
    {"id": "sysadmin_contact","step": 3,"type": "text",
     "text": "What is the System Administrator's Contact (email/phone)?"},

    {"id": "tech_name",      "step": 3, "type": "text",
     "text": "What is the Name of your Technical Head?"},
    {"id": "tech_dept",      "step": 3, "type": "text",
     "text": "Which Department is the Technical Head in?"},
    {"id": "tech_contact",   "step": 3, "type": "text",
     "text": "What is the Technical Head's Contact (email/phone)?"},

    # ── STEP 4: ISMS Core Group (5 roles) ─────────────────────────────────
    {"id": "cg_hr_name",     "step": 4, "type": "text",
     "text": "For the ISMS Core Group — what is the Name of the person in the HR role?"},
    {"id": "cg_hr_resp",     "step": 4, "type": "text",
     "text": "What is their Responsibility in the ISMS?"},
    {"id": "cg_hr_exp",      "step": 4, "type": "text",
     "text": "How many years of Experience do they have in this role?"},

    {"id": "cg_sa_name",     "step": 4, "type": "text",
     "text": "For the ISMS Core Group — what is the Name of the System Admin?"},
    {"id": "cg_sa_resp",     "step": 4, "type": "text",
     "text": "What is their Responsibility in the ISMS?"},
    {"id": "cg_sa_exp",      "step": 4, "type": "text",
     "text": "How many years of Experience do they have?"},

    {"id": "cg_th_name",     "step": 4, "type": "text",
     "text": "For the ISMS Core Group — what is the Name of the Technical Head?"},
    {"id": "cg_th_resp",     "step": 4, "type": "text",
     "text": "What is their Responsibility in the ISMS?"},
    {"id": "cg_th_exp",      "step": 4, "type": "text",
     "text": "How many years of Experience do they have?"},

    {"id": "cg_ceo_name",    "step": 4, "type": "text",
     "text": "For the ISMS Core Group — what is the Name of the CEO?"},
    {"id": "cg_ceo_resp",    "step": 4, "type": "text",
     "text": "What is the CEO's Responsibility in the ISMS?"},
    {"id": "cg_ceo_exp",     "step": 4, "type": "text",
     "text": "How many years of Experience does the CEO have in this role?"},

    {"id": "cg_aud_name",    "step": 4, "type": "text",
     "text": "For the ISMS Core Group — what is the Name of the Auditor?"},
    {"id": "cg_aud_resp",    "step": 4, "type": "text",
     "text": "What is the Auditor's Responsibility in the ISMS?"},
    {"id": "cg_aud_exp",     "step": 4, "type": "text",
     "text": "How many years of Experience does the Auditor have?"},

    # ── STEP 5: Scope Details ──────────────────────────────────────────────
    {"id": "scope_location", "step": 5, "type": "text",
     "text": "What is the Physical Location covered under the ISMS scope?"},
    {"id": "scope_depts",    "step": 5, "type": "text",
     "text": "Which Departments are covered under the scope?"},
    {"id": "scope_systems",  "step": 5, "type": "text",
     "text": "Which Systems are included in the scope?"},
    {"id": "scope_data",     "step": 5, "type": "text",
     "text": "What types of Data are handled? (Client / Internal / Both)"},
    {"id": "scope_third_party","step": 5,"type": "text",
     "text": "Who are your Third-Party Dependencies? (cloud providers, vendors, etc.)"},
    {"id": "scope_exclusions","step": 5,"type": "text",
     "text": "What is explicitly excluded from the ISMS scope?"},

    # ── STEP 6: Contact & Escalation ──────────────────────────────────────
    {"id": "contact_isms_name",  "step": 6, "type": "text",
     "text": "Contact Details — what is the Name of your ISMS Manager?"},
    {"id": "contact_isms_email", "step": 6, "type": "text",
     "text": "What is the ISMS Manager's Email?"},
    {"id": "contact_isms_phone", "step": 6, "type": "text",
     "text": "What is the ISMS Manager's Phone number?"},

    {"id": "contact_sa_name",    "step": 6, "type": "text",
     "text": "Contact Details — what is the Name of your System Administrator?"},
    {"id": "contact_sa_email",   "step": 6, "type": "text",
     "text": "What is the System Administrator's Email?"},
    {"id": "contact_sa_phone",   "step": 6, "type": "text",
     "text": "What is the System Administrator's Phone number?"},

    {"id": "contact_hr_name",    "step": 6, "type": "text",
     "text": "Contact Details — what is the Name of your HR?"},
    {"id": "contact_hr_email",   "step": 6, "type": "text",
     "text": "What is the HR's Email?"},
    {"id": "contact_hr_phone",   "step": 6, "type": "text",
     "text": "What is the HR's Phone number?"},

    {"id": "esc_l1_time",    "step": 6, "type": "text",
     "text": "Escalation Matrix — what is the Expected Response Time for Level 1 (System Admin - Initial Response)?"},
    {"id": "esc_l2_time",    "step": 6, "type": "text",
     "text": "What is the Expected Response Time for Level 2 (ISMS Manager - Investigation)?"},
    {"id": "esc_l3_time",    "step": 6, "type": "text",
     "text": "What is the Expected Response Time for Level 3 (Management - Final Decision)?"},

    # ── STEP 7: Risk Register (repeating) ─────────────────────────────────
    {"id": "risk_desc",      "step": 7, "type": "repeat_field",  "group": "risks",
     "text": "Risk Register — describe this Risk (threat or vulnerability):"},
    {"id": "risk_impact",    "step": 7, "type": "repeat_field",  "group": "risks",
     "text": "What is the Impact level? (1=Very Low, 2=Low, 3=Medium, 4=High, 5=Critical)"},
    {"id": "risk_likelihood","step": 7, "type": "repeat_field",  "group": "risks",
     "text": "What is the Likelihood? (1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High)"},
    {"id": "risk_treatment", "step": 7, "type": "repeat_field",  "group": "risks",
     "text": "What is the Treatment Plan for this risk?"},
    {"id": "risk_owner",     "step": 7, "type": "repeat_field",  "group": "risks",
     "text": "Who is the Risk Owner?"},
    {"id": "risk_more",      "step": 7, "type": "repeat_ask",    "group": "risks",
     "text": "Would you like to add another risk? (yes / no)"},

    # ── STEP 8: Asset Register (repeating) ────────────────────────────────
    {"id": "asset_name",     "step": 8, "type": "repeat_field",  "group": "assets",
     "text": "Asset Register — what is the Asset Name?"},
    {"id": "asset_type",     "step": 8, "type": "repeat_field",  "group": "assets",
     "text": "What Type of asset is it? (Hardware / Software / Data / People / Service)"},
    {"id": "asset_owner",    "step": 8, "type": "repeat_field",  "group": "assets",
     "text": "Who is the Asset Owner?"},
    {"id": "asset_location", "step": 8, "type": "repeat_field",  "group": "assets",
     "text": "Where is it Located?"},
    {"id": "asset_class",    "step": 8, "type": "repeat_field",  "group": "assets",
     "text": "What is its Classification? (Public / Internal / Confidential / Restricted)"},
    {"id": "asset_more",     "step": 8, "type": "repeat_ask",    "group": "assets",
     "text": "Would you like to add another asset? (yes / no)"},

    # ── STEP 9: Policy Register ────────────────────────────────────────────
    {"id": "pol_isms_owner",  "step": 9, "type": "text",
     "text": "Policy Register — who is the Owner of the ISMS Policy?"},
    {"id": "pol_isms_updated","step": 9, "type": "text",
     "text": "When was the ISMS Policy Last Updated?"},
    {"id": "pol_isms_status", "step": 9, "type": "text",
     "text": "What is the ISMS Policy current Status? (Active / Under Review / Outdated)"},

    {"id": "pol_acc_owner",   "step": 9, "type": "text",
     "text": "Who is the Owner of the Access Policy?"},
    {"id": "pol_acc_updated", "step": 9, "type": "text",
     "text": "When was the Access Policy Last Updated?"},
    {"id": "pol_acc_status",  "step": 9, "type": "text",
     "text": "What is the Access Policy current Status? (Active / Under Review / Outdated)"},

    {"id": "pol_bak_owner",   "step": 9, "type": "text",
     "text": "Who is the Owner of the Backup Policy?"},
    {"id": "pol_bak_updated", "step": 9, "type": "text",
     "text": "When was the Backup Policy Last Updated?"},
    {"id": "pol_bak_status",  "step": 9, "type": "text",
     "text": "What is the Backup Policy current Status? (Active / Under Review / Outdated)"},

    # ── STEP 10: Backup Register (repeating) ──────────────────────────────
    {"id": "bak_system",     "step": 10, "type": "repeat_field", "group": "backups",
     "text": "Backup Register — which System is being backed up?"},
    {"id": "bak_freq",       "step": 10, "type": "repeat_field", "group": "backups",
     "text": "What is the Backup Frequency? (Daily / Weekly / Monthly)"},
    {"id": "bak_storage",    "step": 10, "type": "repeat_field", "group": "backups",
     "text": "Where is the Backup stored?"},
    {"id": "bak_responsible","step": 10, "type": "repeat_field", "group": "backups",
     "text": "Who is the Responsible Person for this backup?"},
    {"id": "bak_tested",     "step": 10, "type": "repeat_field", "group": "backups",
     "text": "Has the backup been Tested? (Yes / No)"},
    {"id": "bak_more",       "step": 10, "type": "repeat_ask",   "group": "backups",
     "text": "Would you like to add another backup entry? (yes / no)"},

    # ── STEP 11: Technical Controls ───────────────────────────────────────
    {"id": "ctrl_fw_impl",   "step": 11, "type": "text",
     "text": "Technical Controls — is Firewall implemented? (Yes / No)"},
    {"id": "ctrl_fw_resp",   "step": 11, "type": "text",
     "text": "Who is Responsible for the Firewall?"},
    {"id": "ctrl_fw_remark", "step": 11, "type": "text",
     "text": "Any Remarks about the Firewall?"},

    {"id": "ctrl_av_impl",   "step": 11, "type": "text",
     "text": "Is Antivirus implemented? (Yes / No)"},
    {"id": "ctrl_av_resp",   "step": 11, "type": "text",
     "text": "Who is Responsible for Antivirus?"},
    {"id": "ctrl_av_remark", "step": 11, "type": "text",
     "text": "Any Remarks about Antivirus?"},

    {"id": "ctrl_enc_impl",  "step": 11, "type": "text",
     "text": "Is Encryption implemented? (Yes / No)"},
    {"id": "ctrl_enc_resp",  "step": 11, "type": "text",
     "text": "Who is Responsible for Encryption?"},
    {"id": "ctrl_enc_remark","step": 11, "type": "text",
     "text": "Any Remarks about Encryption?"},

    {"id": "ctrl_pm_impl",   "step": 11, "type": "text",
     "text": "Is Patch Management implemented? (Yes / No)"},
    {"id": "ctrl_pm_resp",   "step": 11, "type": "text",
     "text": "Who is Responsible for Patch Management?"},
    {"id": "ctrl_pm_remark", "step": 11, "type": "text",
     "text": "Any Remarks about Patch Management?"},

    # ── STEP 12: Approval & Sign-Off ──────────────────────────────────────
    {"id": "appr_auditor",   "step": 12, "type": "text",
     "text": "Approval & Sign-Off — who is the Auditor signing off this report?"},
    {"id": "appr_isms_mgr",  "step": 12, "type": "text",
     "text": "Who is the ISMS Manager approving this report?"},
    {"id": "appr_ceo",       "step": 12, "type": "text",
     "text": "Who is the CEO / Director approving this report?"},
]

# Group labels for section headers shown in chat
STEP_LABELS = {
    1:  "Step 1 of 12 — Organisation Details",
    2:  "Step 2 of 12 — Audit Details",
    3:  "Step 3 of 12 — Management & ISMS Team",
    4:  "Step 4 of 12 — ISMS Core Group",
    5:  "Step 5 of 12 — Scope Details",
    6:  "Step 6 of 12 — Contact & Escalation",
    7:  "Step 7 of 12 — Risk Register",
    8:  "Step 8 of 12 — Asset Register",
    9:  "Step 9 of 12 — Policy Register",
    10: "Step 10 of 12 — Backup Register",
    11: "Step 11 of 12 — Technical Controls",
    12: "Step 12 of 12 — Approval & Sign-Off",
}

# Sub-field keys for repeating groups (in order)
REPEAT_FIELDS = {
    "risks":   ["risk_desc", "risk_impact", "risk_likelihood", "risk_treatment", "risk_owner"],
    "assets":  ["asset_name", "asset_type", "asset_owner", "asset_location", "asset_class"],
    "backups": ["bak_system", "bak_freq", "bak_storage", "bak_responsible", "bak_tested"],
}
