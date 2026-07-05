"""KSP Crime Analytics — Chat UI (Streamlit)
Run:  streamlit run ui/streamlit_app.py

ChatGPT/Claude-style layout:
  * left sidebar: user info, New chat, past conversations, logout
  * main pane: chat window (st.chat_message / st.chat_input)
  * login / signup screen before anything else
  * supervisors & admins get an Audit Log tab (RBAC demo)
Every sensitive action is written to AuditLogs via repo.log_action().
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))  # import app.*

import streamlit as st

from app.db.database import init_db
from app.db.repository import get_repo
from app.db.models import ROLES, AUDIT_VIEW_ROLES
from app import agent

st.set_page_config(page_title="KSP Crime Analytics", page_icon="🛡️", layout="wide")
init_db()
repo = get_repo()

# ----------------------------------------------------------------------
# session_state keys: user (dict|None), current_session (str|None)
# ----------------------------------------------------------------------
ss = st.session_state
ss.setdefault("user", None)
ss.setdefault("current_session", None)


# ----------------------------------------------------------------------
# Auth screen
# ----------------------------------------------------------------------
def auth_screen():
    st.title("🛡️ KSP Crime Analytics Platform")
    st.caption("Conversational AI over FIR data — Datathon 2026")
    tab_login, tab_signup = st.tabs(["Log in", "Create account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", use_container_width=True):
                user = repo.authenticate(email, password)
                if user:
                    repo.log_action(email, user["role"], "LOGIN_SUCCESS")
                    ss.user = user
                    st.rerun()
                else:
                    repo.log_action(email or "unknown", "", "LOGIN_FAILED")
                    st.error("Invalid credentials or inactive account.")

    with tab_signup:
        with st.form("signup_form"):
            full_name = st.text_input("Full name")
            email2 = st.text_input("Official email")
            role = st.selectbox("Role", ROLES[:-1])  # admin not self-assignable
            district = st.text_input("District (optional)")
            pw1 = st.text_input("Password (min 8 chars)", type="password")
            pw2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create account", use_container_width=True):
                if not full_name or not email2 or "@" not in email2:
                    st.error("Enter a valid name and email.")
                elif len(pw1) < 8:
                    st.error("Password must be at least 8 characters.")
                elif pw1 != pw2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        repo.create_user(email2, pw1, full_name, role=role, district=district)
                        repo.log_action(email2, role, "SIGNUP", detail=f"district={district}")
                        st.success("Account created — switch to the Log in tab.")
                    except Exception:
                        st.error("An account with this email already exists.")
        st.info("Demo note: in production, role assignment would require "
                "supervisor approval instead of self-service signup.")


# ----------------------------------------------------------------------
# Sidebar: identity, new chat, history, audit access, logout
# ----------------------------------------------------------------------
def sidebar():
    u = ss.user
    with st.sidebar:
        st.markdown(f"**{u['email']}**")
        st.markdown(f"Role: `{u['role']}`")
        st.divider()

        if st.button("➕ New chat", use_container_width=True):
            s = repo.create_session(u["ROWID"], title="New chat")
            repo.log_action(u["email"], u["role"], "SESSION_CREATED", resource=s["session_id"])
            ss.current_session = s["session_id"]
            st.rerun()

        st.markdown("##### Past conversations")
        sessions = repo.list_sessions(u["ROWID"])
        if not sessions:
            st.caption("No conversations yet.")
        for s in sessions:
            label = s["title"][:34] + ("…" if len(s["title"]) > 34 else "")
            is_current = s["session_id"] == ss.current_session
            if st.button(("🟢 " if is_current else "") + label,
                         key=f"sess_{s['session_id']}", use_container_width=True):
                ss.current_session = s["session_id"]
                repo.log_action(u["email"], u["role"], "SESSION_OPENED", resource=s["session_id"])
                st.rerun()

        st.divider()
        if st.button("Log out", use_container_width=True):
            repo.log_action(u["email"], u["role"], "LOGOUT")
            ss.user = None
            ss.current_session = None
            st.rerun()


# ----------------------------------------------------------------------
# Chat pane
# ----------------------------------------------------------------------
def chat_pane():
    u = ss.user
    if ss.current_session is None:
        st.markdown("### 👋 Welcome")
        st.markdown("Start a **New chat** from the sidebar, or open a past conversation.")
        return

    history = repo.get_history(ss.current_session)
    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    query = st.chat_input("Ask about crime patterns, cases, trends…")
    if query:
        with st.chat_message("user"):
            st.markdown(query)
        repo.append_message(ss.current_session, "user", query)
        repo.log_action(u["email"], u["role"], "QUERY_SUBMITTED",
                        resource=ss.current_session, detail=query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                reply = agent.respond(query, u["role"], history)
            st.markdown(reply)
        repo.append_message(ss.current_session, "assistant", reply)
        repo.log_action(u["email"], u["role"], "RESPONSE_RETURNED",
                        resource=ss.current_session, detail=reply[:300])

        # First user message becomes the conversation title
        if len(history) == 0:
            _retitle_current(query)
        st.rerun()


def _retitle_current(first_query: str):
    """Set session title from the first message (like ChatGPT/Claude do)."""
    from app.db.database import SessionLocal
    from app.db.models import ChatSession
    import os
    if os.getenv("DATA_BACKEND", "local") == "local":
        with SessionLocal() as db:
            s = db.query(ChatSession).filter(
                ChatSession.session_id == ss.current_session).one()
            s.title = first_query[:60]
            db.commit()
    # Catalyst backend: title update happens via repo._update in CatalystRepo
    else:
        rows = repo._zcql(
            f"SELECT ROWID FROM ChatSessions WHERE session_id = '{ss.current_session}'")
        r = rows[0].get("ChatSessions", rows[0])
        repo._update("ChatSessions", {"ROWID": r["ROWID"], "title": first_query[:60]})


# ----------------------------------------------------------------------
# Audit log view (supervisor / admin only) — RBAC in action
# ----------------------------------------------------------------------
def audit_pane():
    st.markdown("### 🔍 Audit trail")
    st.caption("Every login, session, and query is recorded for traceability.")
    rows = repo.list_audit(limit=300)
    if rows:
        st.dataframe(rows, use_container_width=True, height=480)
    else:
        st.caption("No audit entries yet.")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if ss.user is None:
    auth_screen()
else:
    sidebar()
    if ss.user["role"] in AUDIT_VIEW_ROLES:
        tab_chat, tab_audit = st.tabs(["💬 Chat", "🔍 Audit log"])
        with tab_chat:
            chat_pane()
        with tab_audit:
            audit_pane()
    else:
        chat_pane()
