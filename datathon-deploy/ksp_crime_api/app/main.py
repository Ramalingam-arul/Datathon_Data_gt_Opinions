"""Minimal chatbot backend demonstrating the storage layer.
Run locally:  uvicorn app.main:app --reload
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.db.database import init_db
from app.db.repository import get_repo

app = FastAPI(title="KSP Crime Analytics — Chatbot Backend")
repo = get_repo()
init_db()  # no-op for Catalyst backend, creates SQLite tables locally


class SignupIn(BaseModel):
    email: str
    password: str
    full_name: str
    district: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class MessageIn(BaseModel):
    session_id: str
    content: str


@app.post("/auth/signup")
def signup(body: SignupIn):
    return repo.create_user(body.email, body.password, body.full_name, district=body.district)


@app.post("/auth/login")
def login(body: LoginIn):
    user = repo.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    return user


@app.post("/sessions/{user_id}")
def new_session(user_id: int, title: str = "New chat"):
    return repo.create_session(user_id, title)


@app.get("/sessions/{user_id}")
def sessions(user_id: int):
    return repo.list_sessions(user_id)


@app.post("/chat")
def chat(body: MessageIn):
    repo.append_message(body.session_id, "user", body.content)
    # TODO: replace with your actual LLM / multi-agent call
    reply = f"(stub) You asked: {body.content[:80]}"
    repo.append_message(body.session_id, "assistant", reply)
    return {"reply": reply, "history": repo.get_history(body.session_id)}
