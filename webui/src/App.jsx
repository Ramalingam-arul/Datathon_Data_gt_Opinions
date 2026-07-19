import { useEffect, useRef, useState } from 'react'
import { api, setUser as bindApiUser } from './api.js'

const ROLES = ['investigator', 'analyst', 'supervisor', 'policymaker']
const AUDIT_ROLES = ['supervisor', 'admin']

/* ---------- tiny markdown-ish renderer (bold + line breaks only) ---------- */
function Rich({ text }) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g)
  return (
    <span>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**')
          ? <strong key={i}>{p.slice(2, -2)}</strong>
          : p.split('\n').map((line, j, arr) => (
              <span key={`${i}-${j}`}>{line}{j < arr.length - 1 && <br />}</span>
            ))
      )}
    </span>
  )
}

/* ------------------------------- Auth ------------------------------------ */
function AuthScreen({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', confirm: '', full_name: '', role: 'analyst', district: '' })
  const [err, setErr] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async () => {
    setErr(''); setOk(''); setBusy(true)
    try {
      if (mode === 'login') {
        const user = await api.login({ email: form.email, password: form.password })
        onLogin(user)
      } else {
        if (form.password !== form.confirm) throw new Error('Passwords do not match')
        await api.signup({ email: form.email, password: form.password, full_name: form.full_name, role: form.role, district: form.district })
        setOk('Account created. You can log in now.')
        setMode('login')
      }
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="crest">KSP</div>
        <h1>Crime Analytics Platform</h1>
        <p className="sub">Conversational AI over FIR data · Datathon 2026</p>

        <div className="tabs">
          <button className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr('') }}>Log in</button>
          <button className={mode === 'signup' ? 'on' : ''} onClick={() => { setMode('signup'); setErr('') }}>Create account</button>
        </div>

        {mode === 'signup' && (
          <>
            <label>Full name<input value={form.full_name} onChange={set('full_name')} placeholder="e.g. Priya Deshpande" /></label>
            <label>Role
              <select value={form.role} onChange={set('role')}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <label>District (optional)<input value={form.district} onChange={set('district')} placeholder="e.g. Ballari" /></label>
          </>
        )}

        <label>Official email<input type="email" value={form.email} onChange={set('email')} placeholder="name@ksp.gov.in" /></label>
        <label>Password<input type="password" value={form.password} onChange={set('password')}
          onKeyDown={e => e.key === 'Enter' && mode === 'login' && submit()} placeholder="min 8 characters" /></label>
        {mode === 'signup' && (
          <label>Confirm password<input type="password" value={form.confirm} onChange={set('confirm')} /></label>
        )}

        {err && <div className="msg err">{err}</div>}
        {ok && <div className="msg ok">{ok}</div>}

        <button className="primary" onClick={submit} disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
        </button>

        {mode === 'signup' && (
          <p className="note">Demo note: in production, role assignment requires supervisor approval instead of self-service signup.</p>
        )}
      </div>
    </div>
  )
}

/* ------------------------------- Chat ------------------------------------ */
function ChatPane({ user, sessionId, onFirstMessage }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const bottom = useRef(null)

  useEffect(() => {
    if (!sessionId) return
    setHistory([]); setErr('')
    api.history(sessionId).then(setHistory).catch(e => setErr(e.message))
  }, [sessionId])

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [history, busy])

  const send = async () => {
    const q = input.trim()
    if (!q || busy) return
    setInput(''); setErr('')
    const wasEmpty = history.length === 0
    setHistory(h => [...h, { role: 'user', content: q }])
    setBusy(true)
    try {
      const { reply } = await api.chat(sessionId, q)
      setHistory(h => [...h, { role: 'assistant', content: reply }])
      if (wasEmpty) onFirstMessage(q)
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  if (!sessionId) return (
    <div className="empty">
      <h2>Namaskara, {user.full_name || user.email} 👋</h2>
      <p>Start a <b>new conversation</b> from the left, or reopen a past one.</p>
      <p className="hint">Try: “Show chain snatching trends in Ballari over the last 3 months”</p>
    </div>
  )

  return (
    <div className="chat">
      <div className="msgs">
        {history.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <div className="who">{m.role === 'user' ? 'You' : 'Analyst AI'}</div>
            <Rich text={m.content} />
          </div>
        ))}
        {busy && <div className="bubble assistant thinking">Analysing…</div>}
        {err && <div className="msg err">{err}</div>}
        <div ref={bottom} />
      </div>
      <div className="composer">
        <input value={input} onChange={e => setInput(e.target.value)}
               onKeyDown={e => e.key === 'Enter' && send()}
               placeholder="Ask about crime patterns, cases, trends…" />
        <button className="primary" onClick={send} disabled={busy || !input.trim()}>Send</button>
      </div>
    </div>
  )
}

/* ------------------------------- Audit ----------------------------------- */
function AuditPane() {
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.audit().then(setRows).catch(e => setErr(e.message)) }, [])
  if (err) return <div className="msg err" style={{ margin: 24 }}>{err}</div>
  if (!rows) return <div className="empty"><p>Loading audit trail…</p></div>
  return (
    <div className="audit">
      <h2>Audit trail</h2>
      <p className="sub">Every login, session and query is recorded for traceability.</p>
      <table>
        <thead><tr><th>Time</th><th>Actor</th><th>Role</th><th>Action</th><th>Resource</th><th>Detail</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="mono">{r.time || r.CREATEDTIME}</td>
              <td>{r.actor || r.actor_email}</td>
              <td><span className="chip">{r.role || r.actor_role}</span></td>
              <td className="mono">{r.action}</td>
              <td className="mono dim">{(r.resource || '').slice(0, 10)}</td>
              <td className="dim">{(r.detail || '').slice(0, 60)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* -------------------------------- App ------------------------------------ */
export default function App() {
  const [user, setUser] = useState(null)
  const [sessions, setSessions] = useState([])
  const [current, setCurrent] = useState(null)
  const [view, setView] = useState('chat')

  const login = (u) => { bindApiUser(u); setUser(u) }

  const refreshSessions = () => user && api.listSessions(user.ROWID).then(setSessions).catch(() => {})
  useEffect(() => { refreshSessions() }, [user])

  const newChat = async () => {
    const s = await api.newSession(user.ROWID)
    setCurrent(s.session_id); setView('chat'); refreshSessions()
  }

  const logout = async () => {
    try { await api.logout() } catch {}
    bindApiUser(null); setUser(null); setSessions([]); setCurrent(null); setView('chat')
  }

  if (!user) return <AuthScreen onLogin={login} />

  return (
    <div className="shell">
      <aside>
        <div className="brand"><span className="crest sm">KSP</span> Crime Analytics</div>
        <div className="me">
          <div className="name">{user.full_name || user.email}</div>
          <span className="chip">{user.role}</span>
        </div>

        <button className="primary block" onClick={newChat}>＋ New conversation</button>

        <div className="label">Past conversations</div>
        <div className="sessions">
          {sessions.length === 0 && <div className="dim pad">No conversations yet.</div>}
          {sessions.map(s => (
            <button key={s.session_id}
                    className={`sess ${current === s.session_id && view === 'chat' ? 'on' : ''}`}
                    onClick={() => { setCurrent(s.session_id); setView('chat') }}>
              {s.title}
            </button>
          ))}
        </div>

        <div className="foot">
          {AUDIT_ROLES.includes(user.role) && (
            <button className={`ghost block ${view === 'audit' ? 'on' : ''}`}
                    onClick={() => setView(view === 'audit' ? 'chat' : 'audit')}>
              {view === 'audit' ? '← Back to chat' : '🔍 Audit log'}
            </button>
          )}
          <button className="ghost block" onClick={logout}>Log out</button>
        </div>
      </aside>

      <main>
        {view === 'audit'
          ? <AuditPane />
          : <ChatPane user={user} sessionId={current} onFirstMessage={refreshSessions} />}
      </main>
    </div>
  )
}
