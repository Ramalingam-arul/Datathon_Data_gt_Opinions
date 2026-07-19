"""Repository layer — the ONLY place the backend touches storage.
SqlAlchemyRepo (local SQLite) | CatalystRepo (Data Store via SDK/REST).
Select with env: DATA_BACKEND=local | catalyst
"""
import json
import os
import uuid
from datetime import datetime, timezone

import bcrypt

from .models import User, ChatSession, AuditLog
from .database import SessionLocal


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def hash_password(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain, hashed):
    return bcrypt.checkpw(plain.encode(), hashed.encode())


class SqlAlchemyRepo:
    def create_user(self, email, password, full_name, role="analyst", district=""):
        with SessionLocal() as db:
            user = User(email=email.lower().strip(), password_hash=hash_password(password),
                        full_name=full_name, role=role, district=district)
            db.add(user); db.commit(); db.refresh(user)
            return {"ROWID": user.ROWID, "email": user.email, "full_name": user.full_name, "role": user.role}

    def authenticate(self, email, password):
        with SessionLocal() as db:
            user = db.query(User).filter(User.email == email.lower().strip()).first()
            if user and user.is_active and verify_password(password, user.password_hash):
                user.last_login = datetime.now(timezone.utc); db.commit()
                return {"ROWID": user.ROWID, "email": user.email, "role": user.role, "full_name": user.full_name}
            return None

    def create_session(self, user_id, title="New chat"):
        with SessionLocal() as db:
            s = ChatSession(session_id=uuid.uuid4().hex, user_id=user_id, title=title)
            db.add(s); db.commit(); db.refresh(s)
            return {"session_id": s.session_id, "ROWID": s.ROWID, "title": s.title}

    def append_message(self, session_id, role, content):
        with SessionLocal() as db:
            s = db.query(ChatSession).filter(ChatSession.session_id == session_id).one()
            msgs = json.loads(s.messages_json)
            msgs.append({"role": role, "content": content, "ts": utcnow_iso()})
            s.messages_json = json.dumps(msgs)
            s.message_count = len(msgs)
            s.last_message_at = datetime.now(timezone.utc)
            db.commit()
            return s.message_count

    def get_history(self, session_id):
        with SessionLocal() as db:
            s = db.query(ChatSession).filter(ChatSession.session_id == session_id).one()
            return json.loads(s.messages_json)

    def set_title(self, session_id, title):
        with SessionLocal() as db:
            s = db.query(ChatSession).filter(ChatSession.session_id == session_id).one()
            s.title = title[:60]; db.commit()

    def list_sessions(self, user_id):
        with SessionLocal() as db:
            rows = (db.query(ChatSession)
                    .filter(ChatSession.user_id == user_id, ChatSession.status == "active")
                    .order_by(ChatSession.CREATEDTIME.desc()).all())
            return [{"session_id": r.session_id, "title": r.title, "message_count": r.message_count} for r in rows]

    def log_action(self, actor_email, actor_role, action, resource="", detail=""):
        with SessionLocal() as db:
            db.add(AuditLog(actor_email=actor_email, actor_role=actor_role,
                            action=action, resource=resource, detail=detail[:2000]))
            db.commit()

    def list_audit(self, limit=200):
        with SessionLocal() as db:
            rows = db.query(AuditLog).order_by(AuditLog.CREATEDTIME.desc()).limit(limit).all()
            return [{"time": r.CREATEDTIME.strftime("%Y-%m-%d %H:%M:%S"), "actor": r.actor_email,
                     "role": r.actor_role, "action": r.action, "resource": r.resource,
                     "detail": r.detail} for r in rows]


class CatalystRepo:
    """sdk mode (inside Catalyst) or rest mode (anywhere, needs OAuth token)."""

    def __init__(self):
        self.mode = os.getenv("CATALYST_MODE", "sdk")
        if self.mode == "sdk":
            import zcatalyst_sdk
            self.app = zcatalyst_sdk.initialize()
        else:
            import requests
            self.requests = requests
            self.base = os.getenv("CATALYST_BASE_URL", "https://api.catalyst.zoho.in")
            self.project = os.environ["CATALYST_PROJECT_ID"]
            self.headers = {"Authorization": f"Zoho-oauthtoken {os.environ['CATALYST_OAUTH_TOKEN']}",
                            "Content-Type": "application/json"}

    def _insert(self, table, row):
        if self.mode == "sdk":
            return self.app.datastore().table(table).insert_row(row)
        url = f"{self.base}/baas/v1/project/{self.project}/table/{table}/row"
        r = self.requests.post(url, headers=self.headers, json=[row], timeout=30)
        r.raise_for_status()
        return r.json()["data"][0]

    def _update(self, table, row):
        if self.mode == "sdk":
            return self.app.datastore().table(table).update_row(row)
        url = f"{self.base}/baas/v1/project/{self.project}/table/{table}/row"
        r = self.requests.put(url, headers=self.headers, json=[row], timeout=30)
        r.raise_for_status()
        return r.json()["data"][0]

    def _zcql(self, query):
        if self.mode == "sdk":
            return self.app.zcql().execute_query(query)
        url = f"{self.base}/baas/v1/project/{self.project}/query"
        r = self.requests.post(url, headers=self.headers, json={"query": query}, timeout=30)
        r.raise_for_status()
        return r.json()["data"]

    def create_user(self, email, password, full_name, role="analyst", district=""):
        return self._insert("Users", {"email": email.lower().strip(),
                                      "password_hash": hash_password(password),
                                      "full_name": full_name, "role": role,
                                      "district": district, "is_active": True})

    def authenticate(self, email, password):
        email = email.lower().strip().replace("'", "")
        rows = self._zcql(f"SELECT ROWID, email, role, full_name, password_hash, is_active FROM Users WHERE email = '{email}'")
        if not rows:
            return None
        u = rows[0].get("Users", rows[0])
        if u.get("is_active") in (True, "true", "True") and verify_password(password, u["password_hash"]):
            self._update("Users", {"ROWID": u["ROWID"], "last_login": utcnow_iso()})
            return {"ROWID": u["ROWID"], "email": u["email"], "role": u["role"],
                    "full_name": u.get("full_name", "")}
        return None

    def create_session(self, user_id, title="New chat"):
        sid = uuid.uuid4().hex
        row = self._insert("ChatSessions", {"session_id": sid, "user_id": str(user_id),
                                            "title": title, "status": "active",
                                            "messages_json": "[]", "message_count": 0})
        return {"session_id": sid, "ROWID": row.get("ROWID"), "title": title}

    def _get_session(self, session_id, cols="ROWID, messages_json"):
        rows = self._zcql(f"SELECT {cols} FROM ChatSessions WHERE session_id = '{session_id}'")
        return rows[0].get("ChatSessions", rows[0])

    def append_message(self, session_id, role, content):
        s = self._get_session(session_id)
        msgs = json.loads(s["messages_json"] or "[]")
        msgs.append({"role": role, "content": content, "ts": utcnow_iso()})
        self._update("ChatSessions", {"ROWID": s["ROWID"], "messages_json": json.dumps(msgs),
                                      "message_count": len(msgs), "last_message_at": utcnow_iso()})
        return len(msgs)

    def get_history(self, session_id):
        s = self._get_session(session_id, cols="messages_json")
        return json.loads(s["messages_json"] or "[]")

    def set_title(self, session_id, title):
        s = self._get_session(session_id, cols="ROWID")
        self._update("ChatSessions", {"ROWID": s["ROWID"], "title": title[:60]})

    def list_sessions(self, user_id):
        rows = self._zcql(f"SELECT session_id, title, message_count FROM ChatSessions "
                          f"WHERE user_id = '{user_id}' AND status = 'active' ORDER BY CREATEDTIME DESC")
        return [r.get("ChatSessions", r) for r in rows]

    def log_action(self, actor_email, actor_role, action, resource="", detail=""):
        self._insert("AuditLogs", {"actor_email": actor_email, "actor_role": actor_role,
                                   "action": action, "resource": resource, "detail": detail[:2000]})

    def list_audit(self, limit=200):
        rows = self._zcql(f"SELECT * FROM AuditLogs ORDER BY CREATEDTIME DESC LIMIT {int(limit)}")
        return [r.get("AuditLogs", r) for r in rows]


def get_repo():
    if os.getenv("DATA_BACKEND", "local") == "catalyst":
        return CatalystRepo()
    return SqlAlchemyRepo()
