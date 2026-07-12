# KSP Chat UI — Catalyst AppSail Deploy Runbook

Repo folder: `Datathon_Data_gt_Opinions` (a.k.a. "the repo")
Deploy folder: `../ksp_deploy` (sits NEXT TO the repo, never inside it, never committed)

Golden rules:
- All `catalyst` commands run FROM THE REPO ROOT (where `catalyst.json` lives).
- The deploy folder is disposable — rebuilt from scratch every deploy.
- `app-config.json` lives INSIDE the deploy folder → it is destroyed on every
  rebuild → the rebuild block below always recreates it. Never edit it and
  forget to mirror the change here / in the repo copy.

-------------------------------------------------------------------------------
## 0. One-time machine setup (already done — only for new laptops/teammates)
-------------------------------------------------------------------------------
    # Node.js required (nodejs.org), then:
    npm install -g zcatalyst-cli
    catalyst login

-------------------------------------------------------------------------------
## 1. One-time project wiring (already done — only after a fresh clone)
-------------------------------------------------------------------------------
    cd <repo>
    catalyst init
      → associate with EXISTING project: Datathon-data-gt-opinions
      → at "Which features to setup" press SPACEBAR to tick AppSail, then Enter
        (pressing Enter without ticking = "Could not understand the targets" later)

    # If AppSail wasn't ticked during init, add it after the fact:
    catalyst appsail:add
      → Runtime type:            Catalyst-Managed Runtime
      → Sample project?          N
      → Is this the source dir?  N  → paste ABSOLUTE path of ../ksp_deploy
                                      (get it: cd ../ksp_deploy && pwd)
      → Stack:                   Python 3.9   (must match app-config.json)
      → App name:                ksp-chat-ui  (link existing, don't create new)
      → Overwrite app-config.json?  N   (keep ours!)

    # Commit the wiring so teammates inherit it:
    #   catalyst.json, .catalystrc → commit & push

-------------------------------------------------------------------------------
## 2. EVERY-DEPLOY RECIPE (the part you'll actually reuse)
-------------------------------------------------------------------------------
Run from the REPO ROOT. Copy-paste the whole block.

    # (a) fresh deploy folder with current code
    rm -rf ../ksp_deploy && mkdir ../ksp_deploy
    cp -R app ui seed requirements.txt ../ksp_deploy/

    # (b) recreate the AppSail config
    cat > ../ksp_deploy/app-config.json <<'EOF'
    {
      "command": "sh -c 'python3 -m seed.seed_local && python3 -m streamlit run ui/streamlit_app.py --server.port $X_ZOHO_CATALYST_LISTEN_PORT --server.address 0.0.0.0 --server.headless true'",
      "env_variables": {
        "DATA_BACKEND": "local",
        "DATABASE_URL": "sqlite:////tmp/chatbot_dev.db",
        "HOME": "/tmp",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"
      },
      "build_path": ".",
      "stack": "python_3_9",
      "memory": 512,
      "scripts": {}
    }
    EOF

    # (c) install LINUX wheels (AppSail runs Linux x86-64, not macOS!)
    pip3 install -r requirements.txt -t ../ksp_deploy \
      --platform manylinux2014_x86_64 --only-binary=:all: \
      --python-version 3.9 --implementation cp

    # (d) prune junk → smaller zip, fewer open files (prevents ENFILE crash)
    find ../ksp_deploy -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find ../ksp_deploy -type d -name "tests"       -exec rm -rf {} + 2>/dev/null
    rm -rf ../ksp_deploy/pip ../ksp_deploy/setuptools ../ksp_deploy/wheel 2>/dev/null

-------------------------------------------------------------------------------
## 3. Pre-deploy verification (10 seconds, saves an hour)
-------------------------------------------------------------------------------
    # No Mac binaries snuck in (must print NOTHING):
    find ../ksp_deploy -name "*darwin*" -o -name "*macosx*" | head

    # Python-3.9-safe models.py made it in (must print 2):
    grep -c "Optional\[datetime\]" ../ksp_deploy/app/db/models.py

    # Config survived the rebuild (must show our sh -c command, not a placeholder):
    cat ../ksp_deploy/app-config.json

-------------------------------------------------------------------------------
## 4. Deploy
-------------------------------------------------------------------------------
    ulimit -n 10240      # raise open-file limit for THIS terminal window
    catalyst deploy      # from the repo root

    Success looks like: AppSail [ksp-chat-ui] deployed, endpoint URL printed.

-------------------------------------------------------------------------------
## 5. Verify it's alive
-------------------------------------------------------------------------------
    Console → project → Serverless → AppSail → ksp-chat-ui → Logs
      WANT: seed output ("user: admin@kspdemo.in -> 1" ...) then
            Streamlit banner ("You can now view your Streamlit app ...")
    Open the app URL → log in:  analyst1@kspdemo.in / Analyst@2026
    Supervisor demo (audit tab): supervisor@kspdemo.in / Super@2026

    NOTE: /tmp database is EPHEMERAL — signups/chats vanish when the instance
    restarts. Fine for testing. Persistence = switch to DATA_BACKEND=catalyst
    (see §7).

-------------------------------------------------------------------------------
## 6. Troubleshooting — every error we've hit, and its fix
-------------------------------------------------------------------------------
| Log / CLI message                                   | Cause                              | Fix |
|-----------------------------------------------------|------------------------------------|-----|
| sh: python: command not found                       | runtime only has `python3`         | use python3 in command (§2b already does) |
| TypeError: unsupported operand ... \| ... NoneType  | `X \| None` hints on Python 3.9    | Optional[...] in models.py (committed) |
| ImportError ... invalid ELF header                  | Mac wheels on Linux                | rebuild with §2c pip flags |
| Error: Could not understand the targets             | AppSail not in catalyst.json       | catalyst appsail:add (§1) |
| ENFILE: file table overflow (+ other apps crash)    | macOS system file table full       | RESTART the Mac, close heavy apps, §2d prune, ulimit, retry |
| cp: app-config.json: No such file                   | rebuild deleted it                 | §2b recreates it every time |
| "Execution failed. Check startup command or port"   | generic — real error is in Logs    | always read Logs first |
| Crashes under load / random restarts                | 256 MB memory                      | memory: 512 in app-config.json |
| Login works locally, data gone after restart        | /tmp SQLite is ephemeral           | expected; see §7 |

-------------------------------------------------------------------------------
## 7. Later: switch to persistent Catalyst Data Store
-------------------------------------------------------------------------------
    1. Console → Data Store → create tables: Users, ChatSessions, AuditLogs
       (column specs in repo README.md §2; AuditLogs: actor_email, actor_role,
        action, resource — Varchar; detail — Text)
    2. Add zcatalyst-sdk to requirements.txt (uncomment) and rebuild (§2)
    3. In app-config.json env_variables:
         "DATA_BACKEND": "catalyst",
         "CATALYST_MODE": "sdk"
       and REMOVE `python3 -m seed.seed_local &&` from the command
       (no SQLite to seed; create demo users once via the signup screen)
    4. Deploy (§4)

-------------------------------------------------------------------------------
Maintained by: Manasa • Last updated: 12 Jul 2026 • Datathon 2026
