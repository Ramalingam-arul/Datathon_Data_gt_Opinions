"""Dummy agent — REPLACE THIS with the real supervisor-agent pipeline.

Contract your agent must keep:
    respond(query: str, role: str, history: list[dict]) -> str
history = [{"role": "user"|"assistant", "content": str, "ts": str}, ...]
"""
import time


ROLE_SCOPES = {
    "investigator": "case-level detail for your own station/district",
    "analyst": "district and state level analytics, pattern mining",
    "supervisor": "cross-station performance, pendency and audit views",
    "policymaker": "aggregate, anonymised trends only (no personal data)",
    "admin": "full system access",
}


def respond(query: str, role: str, history: list[dict]) -> str:
    time.sleep(0.6)  # simulate model latency
    scope = ROLE_SCOPES.get(role, "standard access")
    return (
        f"**[stub agent]** I received your query: *\u201c{query[:120]}\u201d*\n\n"
        f"As a **{role}**, your data scope is: {scope}.\n\n"
        f"This is turn {len(history)//2 + 1} of the conversation. "
        "Once the real agent is wired in, this reply will come from the "
        "supervisor agent querying the FIR datastore."
    )
