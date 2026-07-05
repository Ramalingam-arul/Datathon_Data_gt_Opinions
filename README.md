# KSP Chatbot Backend — Storage Layer (Users + ChatSessions)

## 1. Git branching (do this first, from your cloned repo)

```bash
cd your-repo

# make sure main is current
git checkout main
git pull origin main

# create dev branch off main and push it
git checkout -b dev
git push -u origin dev

# create your feature branch off dev
git checkout -b feature/chatbot-backend
git push -u origin feature/chatbot-backend
```

Daily flow: work on `feature/chatbot-backend` → PR into `dev` → `dev` merges to `main` only for releases/demo. Teammates create their own `feature/*` branches off `dev`, never off each other's branches.

```bash
# keeping your feature branch fresh while others merge into dev
git checkout dev && git pull origin dev
git checkout feature/chatbot-backend
git merge dev            # (or: git rebase dev)
```

## 2. Catalyst Data Store — table schemas

Catalyst auto-creates `ROWID` (bigint primary key), `CREATORID`, `CREATEDTIME`, `MODIFIEDTIME` on every table. Do NOT add your own id/created columns.

### Table 1: `Users`
| Column | Catalyst type | Constraints / notes |
|---|---|---|
| email | Varchar (255) | Mandatory, Unique ✔ |
| password_hash | Varchar (255) | Mandatory. Store bcrypt hash only, never plaintext |
| full_name | Varchar (120) | Mandatory |
| role | Varchar (30) | default `analyst` (analyst / admin / sho) |
| district | Varchar (60) | optional |
| is_active | Boolean | default true |
| last_login | Date time | optional |

### Table 2: `ChatSessions`
| Column | Catalyst type | Constraints / notes |
|---|---|---|
| session_id | Varchar (64) | Mandatory, Unique ✔ (uuid4 hex, used in URLs/APIs) |
| user_id | Bigint | Mandatory — stores Users.ROWID (Catalyst has no FK enforcement; app enforces it) |
| title | Varchar (200) | default "New chat" |
| status | Varchar (20) | default `active` (active / archived) |
| messages_json | Text | JSON array of {role, content, ts} |
| message_count | Int | default 0 |
| last_message_at | Date time | optional |

Console steps: Catalyst Console → your project → **Data Store → Create Table** → name it `Users` → add columns above (pick type, tick Mandatory/Unique where noted) → repeat for `ChatSessions`.

> Why messages inside the session row? For a hackathon it removes a third table and one join. If chats get long (>1000 messages) or you need per-message analytics, split into a `ChatMessages` table later — the repo layer means only `append_message`/`get_history` change.

## 3. Why not SQLAlchemy → Catalyst directly

Catalyst Data Store has **no SQL endpoint/connection string** — it is only reachable via the Catalyst SDK (ZCQL) or REST API. So:

- **Locally**: SQLAlchemy + SQLite (`chatbot_dev.db`), same column names as Catalyst.
- **Deployed / integration test**: `CatalystRepo` talks to the real Data Store (SDK inside Catalyst functions, REST from outside).
- The rest of the backend only ever calls `get_repo()` — identical interface both ways.

Switch with one env var in `.env`: `DATA_BACKEND=local` or `catalyst`.

## 4. Run it locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

python -m seed.seed_local        # creates chatbot_dev.db + 5 users + 4 sample chats
uvicorn app.main:app --reload    # http://127.0.0.1:8000/docs
```

Test in the Swagger UI (`/docs`): `POST /auth/login` with `analyst1@kspdemo.in / Analyst@2026`, then `POST /sessions/3`, then `POST /chat`.

## 5. Point it at real Catalyst

1. Create the two tables in the console (step 2).
2. Get an OAuth token: Zoho API Console → Self Client → generate token with scope `ZohoCatalyst.tables.rows.ALL,ZohoCatalyst.zcql.READ` (or run inside a Catalyst function with `CATALYST_MODE=sdk` and skip tokens entirely).
3. In `.env`: `DATA_BACKEND=catalyst`, `CATALYST_MODE=rest`, project id + token, base URL `https://api.catalyst.zoho.in` (India DC).
4. Restart uvicorn — same endpoints now read/write Catalyst.

## 6. Files

```
app/main.py               FastAPI endpoints (signup/login/sessions/chat)
app/db/models.py          SQLAlchemy models (mirror Catalyst columns 1:1)
app/db/database.py        engine + init_db + get_db dependency
app/db/repository.py      SqlAlchemyRepo + CatalystRepo + get_repo() factory
seed/users_seed.csv       5 demo users (plaintext pw in CSV only; hashed on insert)
seed/chat_sessions_seed.csv  4 sample chat sessions with message history
seed/seed_local.py        loads both CSVs into local SQLite
```

Commit all of this to `feature/chatbot-backend`, add `chatbot_dev.db` and `.env` to `.gitignore`.
