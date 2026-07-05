"""Seed the LOCAL SQLite db from the CSVs.  Run:  python -m seed.seed_local"""
import csv, json, pathlib
from datetime import datetime, timezone

from app.db.database import init_db, SessionLocal
from app.db.models import User, ChatSession
from app.db.repository import SqlAlchemyRepo

HERE = pathlib.Path(__file__).parent
repo = SqlAlchemyRepo()

init_db()

email_to_id = {}
with open(HERE / "users_seed.csv", newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        u = repo.create_user(row["email"], row["password"], row["full_name"],
                             role=row["role"], district=row["district"])
        email_to_id[row["email"]] = u["ROWID"]
        print("user:", u["email"], "->", u["ROWID"])

with open(HERE / "chat_sessions_seed.csv", newline="", encoding="utf-8") as f, SessionLocal() as db:
    for row in csv.DictReader(f):
        msgs = json.loads(row["messages_json"])
        s = ChatSession(
            session_id=__import__("uuid").uuid4().hex,
            user_id=email_to_id[row["user_email"]],
            title=row["title"],
            messages_json=json.dumps(msgs),
            message_count=len(msgs),
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(s)
        db.commit()
        print("session:", row["title"], "->", s.session_id)

print("Seed complete.")
