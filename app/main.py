"""KSP Crime Analytics — FastAPI backend for the React frontend.
Local run:   uvicorn app.main:app --reload
AppSail run: sh -c 'python3 -m uvicorn app.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT'
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from app.db.database import init_db
from app.db.repository import get_repo
from app.db.models import ROLES, AUDIT_VIEW_ROLES
from app import agent

app = FastAPI(title="KSP Crime Analytics — API")

# CORS: the React app is served from a different origin (Catalyst web hosting
# or localhost:5173 in dev), so the browser needs the API's permission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # hackathon-wide open; restrict to your web client URL for production
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = get_repo()
init_db()  # creates SQLite tables locally; no-op effect for Catalyst backend


class SignupIn(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "analyst"
    district: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class MessageIn(BaseModel):
    session_id: str
    content: str


def _actor(email: Optional[str], role: Optional[str]):
    return email or "unknown", role or ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/signup")
def signup(body: SignupIn):
    if body.role not in ROLES or body.role == "admin":
        raise HTTPException(400, "Invalid role")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    try:
        user = repo.create_user(body.email, body.password, body.full_name,
                                role=body.role, district=body.district)
    except Exception:
        raise HTTPException(409, "An account with this email already exists")
    repo.log_action(body.email, body.role, "SIGNUP", detail=f"district={body.district}")
    return user


@app.post("/auth/login")
def login(body: LoginIn):
    user = repo.authenticate(body.email, body.password)
    if not user:
        repo.log_action(body.email or "unknown", "", "LOGIN_FAILED")
        raise HTTPException(401, "Invalid credentials or inactive account")
    repo.log_action(user["email"], user["role"], "LOGIN_SUCCESS")
    return user


@app.post("/logout")
def logout(x_user_email: Optional[str] = Header(None), x_user_role: Optional[str] = Header(None)):
    email, role = _actor(x_user_email, x_user_role)
    repo.log_action(email, role, "LOGOUT")
    return {"ok": True}


@app.post("/sessions/{user_id}")
def new_session(user_id: int, x_user_email: Optional[str] = Header(None),
                x_user_role: Optional[str] = Header(None)):
    s = repo.create_session(user_id)
    email, role = _actor(x_user_email, x_user_role)
    repo.log_action(email, role, "SESSION_CREATED", resource=s["session_id"])
    return s


@app.get("/sessions/{user_id}")
def sessions(user_id: int):
    return repo.list_sessions(user_id)


@app.get("/history/{session_id}")
def history(session_id: str):
    return repo.get_history(session_id)


@app.post("/chat")
def chat(body: MessageIn, x_user_email: Optional[str] = Header(None),
         x_user_role: Optional[str] = Header(None)):
    email, role = _actor(x_user_email, x_user_role)
    history = repo.get_history(body.session_id)

    repo.append_message(body.session_id, "user", body.content)
    repo.log_action(email, role, "QUERY_SUBMITTED", resource=body.session_id, detail=body.content)

    reply = agent.respond(body.content, role or "analyst", history)

    repo.append_message(body.session_id, "assistant", reply)
    repo.log_action(email, role, "RESPONSE_RETURNED", resource=body.session_id, detail=reply[:300])

    if len(history) == 0:  # first exchange names the conversation
        repo.set_title(body.session_id, body.content)

    return {"reply": reply}


@app.get("/audit")
def audit(x_user_role: Optional[str] = Header(None)):
    # Demo-grade RBAC: role comes from a header the client sets after login.
    # Production would use signed tokens (JWT) instead — say this to judges.
    if x_user_role not in AUDIT_VIEW_ROLES:
        raise HTTPException(403, "Audit trail is restricted to supervisors and admins")
    return repo.list_audit(limit=300)
