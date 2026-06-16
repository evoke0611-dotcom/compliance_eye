import streamlit as st

from database import login_user, register_user


AUTH_CSS = """
<style>
#MainMenu, footer, header { visibility: hidden; }
.stApp {
    background: #eef6ff;
    background-image:
        radial-gradient(at 12% 12%, rgba(191, 219, 254, 0.75) 0px, transparent 46%),
        radial-gradient(at 88% 20%, rgba(221, 214, 254, 0.62) 0px, transparent 42%),
        radial-gradient(at 52% 94%, rgba(187, 247, 208, 0.52) 0px, transparent 46%);
}
.block-container {
    max-width: 1120px;
    padding-top: 24px;
    padding-bottom: 32px;
}
.auth-brand-panel,
.auth-form-panel {
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(79, 70, 229, 0.14);
    box-shadow: 0 22px 70px rgba(15, 23, 42, 0.10);
    backdrop-filter: blur(18px);
    border-radius: 22px;
}
.auth-brand-panel {
    min-height: 590px;
    padding: 40px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
}
.auth-form-panel {
    padding: 32px;
    margin-bottom: 16px;
}
div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stTabs"]) {
    background: rgba(255, 255, 255, 0.76);
    border: 1px solid rgba(79, 70, 229, 0.14);
    box-shadow: 0 22px 70px rgba(15, 23, 42, 0.10);
    border-radius: 22px;
    padding: 22px;
}
.brand-lockup {
    display: flex;
    align-items: center;
    gap: 12px;
}
.brand-mark {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    font-weight: 800;
    letter-spacing: 0.03em;
}
.brand-name {
    color: #172554;
    font-weight: 800;
    font-size: 1.35rem;
}
.brand-sub {
    color: #4f46e5;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}
.auth-headline {
    color: #0f172a;
    font-size: clamp(2.1rem, 4vw, 3.4rem);
    line-height: 1.04;
    font-weight: 800;
    max-width: 560px;
    margin-top: 46px;
}
.auth-copy {
    color: #475569;
    font-size: 1rem;
    line-height: 1.7;
    max-width: 540px;
    margin-top: 18px;
}
.assurance-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-top: 42px;
}
.assurance-item {
    border: 1px solid rgba(79, 70, 229, 0.14);
    background: rgba(248, 250, 252, 0.72);
    border-radius: 12px;
    padding: 14px;
}
.assurance-kicker {
    color: #4f46e5;
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.13em;
    text-transform: uppercase;
}
.assurance-text {
    color: #1e293b;
    font-weight: 700;
    margin-top: 6px;
}
.form-eyebrow {
    color: #4f46e5;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.form-title {
    color: #0f172a;
    font-size: 1.65rem;
    font-weight: 800;
    margin-bottom: 6px;
}
.form-subtitle {
    color: #64748b;
    line-height: 1.55;
    margin-bottom: 22px;
}
div[data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(79, 70, 229, 0.06);
    padding: 6px;
    border-radius: 12px;
    margin-bottom: 20px;
}
button[data-baseweb="tab"] {
    border-radius: 9px;
    color: #475569;
    font-weight: 800;
    padding: 8px 14px;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: white;
    color: #4f46e5;
    box-shadow: 0 8px 20px rgba(79, 70, 229, 0.10);
}
div[data-testid="stTextInput"] label {
    color: #334155;
    font-weight: 700;
}
div[data-testid="stTextInput"] input {
    border-radius: 10px;
    border-color: rgba(79, 70, 229, 0.20);
    min-height: 44px;
}
div[data-testid="stFormSubmitButton"] button {
    min-height: 46px;
    border-radius: 10px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border: 0;
    font-weight: 800;
}
.stAlert {
    border-radius: 10px;
}
.auth-note {
    color: #64748b;
    font-size: 0.82rem;
    line-height: 1.55;
    margin-top: 18px;
    padding-top: 18px;
    border-top: 1px solid rgba(79, 70, 229, 0.12);
}
@media (max-width: 900px) {
    .auth-brand-panel,
    .auth-form-panel {
        padding: 26px;
    }
    .auth-headline {
        margin-top: 30px;
    }
}
</style>
"""


def _set_user(user: dict):
    st.session_state.user = user
    st.session_state.authenticated = True


def render_auth_page() -> bool:
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return True

    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    brand_col, form_col = st.columns([1.05, 0.95], gap="large")

    with brand_col:
        st.markdown(
            """
            <section class="auth-brand-panel">
              <div>
                <div class="brand-lockup">
                  <div class="brand-mark">CE</div>
                  <div>
                    <div class="brand-name">ComplianceEye</div>
                    <div class="brand-sub">ISO 27001 AI Auditor</div>
                  </div>
                </div>
                <div class="auth-headline">Secure access for audit work that needs focus.</div>
                <div class="auth-copy">
                  Sign in to continue your ISO 27001 audit session, review saved history,
                  and generate structured compliance reports.
                </div>
                <div class="assurance-grid">
                  <div class="assurance-item">
                    <div class="assurance-kicker">Workspace</div>
                    <div class="assurance-text">Session history stays organized by user.</div>
                  </div>
                  <div class="assurance-item">
                    <div class="assurance-kicker">Reports</div>
                    <div class="assurance-text">DOCX outputs remain ready for review.</div>
                  </div>
                  <div class="assurance-item">
                    <div class="assurance-kicker">Guided Flow</div>
                    <div class="assurance-text">ISMS, gap, and risk steps are tracked.</div>
                  </div>
                  <div class="assurance-item">
                    <div class="assurance-kicker">ISO 27001</div>
                    <div class="assurance-text">Built around the active audit workflow.</div>
                  </div>
                </div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with form_col:
        st.markdown(
            """
            <section class="auth-form-panel">
              <div class="form-eyebrow">Account Access</div>
              <div class="form-title">Welcome </div>
              <div class="form-subtitle">Use your ComplianceEye account to open the audit workspace.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(["Login", "Create Account"])

        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                result = login_user(username, password)
                if result["success"]:
                    _set_user(result["user"])
                    st.rerun()
                st.error(result["message"])

        with register_tab:
            with st.form("register_form"):
                full_name = st.text_input("Full Name", placeholder="Enter your full name")
                email = st.text_input("Email", placeholder="name@company.com")
                username = st.text_input("Choose Username", placeholder="Create a username")
                password = st.text_input("Choose Password", type="password", placeholder="Create a password")
                submitted = st.form_submit_button("Create Account", use_container_width=True)
            if submitted:
                if not all([full_name.strip(), email.strip(), username.strip(), password.strip()]):
                    st.error("Please fill in all fields.")
                else:
                    result = register_user(username, email, full_name, password)
                    if result["success"]:
                        st.success("Account created. Please login.")
                    else:
                        st.error(result["message"])

        st.markdown(
            """
            <div class="auth-note">
              Use a unique username and password for each auditor or team member.
            </div>
            """,
            unsafe_allow_html=True,
        )

    return False
