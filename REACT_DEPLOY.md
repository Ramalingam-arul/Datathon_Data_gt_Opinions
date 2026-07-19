# React + FastAPI on Catalyst — Deploy Guide

Architecture (all Catalyst, no WebSockets anywhere):
  React SPA  -> Catalyst Web Client Hosting  (static files)
  FastAPI    -> AppSail                      (plain HTTP)
  Data       -> Catalyst Data Store          (via CatalystRepo)

---------------------------------------------------------------
## A. Run everything locally first (2 terminals)
---------------------------------------------------------------
Terminal 1 — backend:
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload            # http://127.0.0.1:8000

Terminal 2 — frontend (needs Node from nodejs.org):
    cd webui
    npm install
    npm run dev                              # http://localhost:5173

Sign up a user in the UI, chat, check the audit tab as a supervisor.
(Local backend uses SQLite via DATA_BACKEND=local in .env — no seeding
needed; create users through the signup screen.)

---------------------------------------------------------------
## B. Deploy the FastAPI backend to AppSail
---------------------------------------------------------------
Same runbook as before (DEPLOY_RUNBOOK.md §2-4) with TWO changes:

1. app-config.json command becomes:
   "command": "sh -c 'python3 -m uvicorn app.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT'"
   (no streamlit, no seeding — data lives in the Data Store)

2. env_variables for real Catalyst data:
   "DATA_BACKEND": "catalyst",
   "CATALYST_MODE": "sdk"
   (sdk mode works because the app runs INSIDE Catalyst — no OAuth token needed;
    add zcatalyst-sdk to requirements.txt before the pip -t install)

   For a quick smoke test you can instead keep DATA_BACKEND=local +
   DATABASE_URL=sqlite:////tmp/chatbot_dev.db (ephemeral).

Prerequisite for catalyst mode: create tables Users, ChatSessions,
AuditLogs in Console -> Data Store (columns: README.md §2 + AuditLogs:
actor_email/actor_role/action/resource Varchar, detail Text).

Verify: open  https://<appsail-url>/health  -> {"status":"ok"}
Also try /docs — FastAPI's Swagger UI works over plain HTTP just fine.

---------------------------------------------------------------
## C. Build & deploy the React app to Web Client Hosting
---------------------------------------------------------------
1. Build with the API URL baked in:
       cd webui
       VITE_API_BASE=https://<your-appsail-url> npm run build
   -> creates webui/dist (index.html + assets)

2. Deploy dist/ to Catalyst web client hosting. Either:
   CLI:  catalyst init (tick "Client" feature) — when asked for the client
         directory give webui/dist — then: catalyst deploy
   or Console: CLOUD SCALE -> Web Client Hosting -> upload zip of the
         CONTENTS of webui/dist.

3. Open the web client URL Catalyst gives you (yourproject.catalystserverless.in
   style). Log in, chat — everything is HTTP calls to AppSail; check the
   Network tab: no websockets, no failures.

---------------------------------------------------------------
## D. Gotchas
---------------------------------------------------------------
* Changed the AppSail URL? Rebuild the frontend (the URL is baked at build
  time) and redeploy dist.
* CORS errors in browser console -> backend allow_origins is "*" already;
  if you restricted it, add the web client URL.
* 403 on /audit is CORRECT for non-supervisor roles — that's the RBAC demo.
* Auth is demo-grade (role header after login). Tell judges: "production
  would swap the header for signed JWTs — one function in api.js".
