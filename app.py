"""
app.py
------
LearnMate Flask server — chat UI with sidebar, progress tracking,
roadmap tab, profile tab, and downloadable roadmap.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000
"""

import os
import uuid
from flask import Flask, request, jsonify, session, render_template_string
from learnmate_agent import (
    Session, UserState, chat, get_iam_token,
    GREETING, API_KEY,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ── In-process session store ──────────────────────────────────────────────────
_sessions: dict[str, dict] = {}


def _get_or_create(sid: str) -> dict:
    if sid not in _sessions:
        if not API_KEY:
            raise RuntimeError("WATSONX_API_KEY is not set in .env")
        token = get_iam_token(API_KEY)
        _sessions[sid] = {
            "session": Session(),
            "state":   UserState(),
            "token":   token,
            "turns":   0,
        }
    return _sessions[sid]


# ─────────────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LearnMate — AI Career Coach</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:        #0d1117;
    --surface:   #161b27;
    --surface2:  #1e2535;
    --border:    #252d3d;
    --text:      #dde4f0;
    --muted:     #6b7a99;
    --accent:    #3b82f6;
    --accent2:   #7c3aed;
    --green:     #22c55e;
    --yellow:    #fbbf24;
  }

  body {
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100dvh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* ══ Header ══════════════════════════════════════════════════════════════ */
  header {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    background: var(--bg);
    z-index: 10;
  }
  .logo {
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }
  header h1 { font-size: 16px; font-weight: 700; letter-spacing: .01em; }
  header p  { font-size: 11px; color: var(--muted); margin-top: 1px; }

  /* ══ Main layout ═══════════════════════════════════════════════════════ */
  .layout {
    flex: 1;
    display: flex;
    overflow: hidden;
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
  }

  /* ══ Sidebar ════════════════════════════════════════════════════════════ */
  .sidebar {
    width: 280px;
    flex-shrink: 0;
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* tab bar */
  .tab-bar {
    display: flex;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .tab-btn {
    flex: 1; padding: 10px 4px; font-size: 12px; font-weight: 600;
    background: none; border: none; color: var(--muted); cursor: pointer;
    border-bottom: 2px solid transparent; transition: color .15s, border-color .15s;
    letter-spacing: .02em;
  }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

  /* tab panels */
  .tab-panel { display: none; flex: 1; overflow-y: auto; padding: 16px; flex-direction: column; gap: 16px; }
  .tab-panel.active { display: flex; }

  /* ── Progress tab ── */
  .prog-header { font-size: 13px; font-weight: 700; color: var(--text); }
  .prog-sub    { font-size: 11px; color: var(--muted); margin-top: 2px; }

  .prog-ring-wrap {
    display: flex; flex-direction: column; align-items: center; gap: 6px;
    padding: 8px 0;
  }
  .prog-ring { position: relative; width: 110px; height: 110px; }
  .prog-ring svg { width: 110px; height: 110px; transform: rotate(-90deg); }
  .prog-ring .track { fill: none; stroke: var(--surface2); stroke-width: 10; }
  .prog-ring .fill  {
    fill: none; stroke: var(--accent); stroke-width: 10;
    stroke-linecap: round;
    stroke-dasharray: 283;
    stroke-dashoffset: 283;
    transition: stroke-dashoffset .6s cubic-bezier(.4,0,.2,1);
  }
  .prog-ring .fill.complete { stroke: var(--green); }
  .prog-pct {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800; color: var(--text);
  }
  .prog-label { font-size: 12px; color: var(--muted); }

  .stage-list { display: flex; flex-direction: column; gap: 6px; }
  .stage-item {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 10px; border-radius: 8px;
    background: var(--surface); border: 1px solid var(--border);
    font-size: 12.5px; transition: background .2s;
  }
  .stage-item.done    { background: #0d2918; border-color: #1a4028; }
  .stage-item.current { background: #0d1f3c; border-color: #1a3560; }
  .stage-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    background: var(--muted);
  }
  .stage-item.done    .stage-dot { background: var(--green); }
  .stage-item.current .stage-dot { background: var(--accent); }
  .stage-name { flex: 1; color: var(--text); }
  .stage-check { color: var(--green); font-size: 13px; }

  /* congrats toast */
  #congrats-toast {
    position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%) translateY(20px);
    background: #0d2918; border: 1px solid var(--green);
    color: #86efac; padding: 10px 18px; border-radius: 10px;
    font-size: 13px; font-weight: 600; text-align: center;
    opacity: 0; pointer-events: none;
    transition: opacity .3s, transform .3s;
    z-index: 100; max-width: 340px; line-height: 1.5;
  }
  #congrats-toast.show {
    opacity: 1; transform: translateX(-50%) translateY(0);
  }

  /* ── Roadmap tab ── */
  .roadmap-empty {
    color: var(--muted); font-size: 13px; line-height: 1.6; text-align: center;
    padding: 20px 8px;
  }
  #roadmap-content {
    font-size: 13px; line-height: 1.7; color: var(--text);
  }
  #roadmap-content p     { margin: 0 0 .5em; }
  #roadmap-content p:last-child { margin-bottom: 0; }
  #roadmap-content strong { color: #93c5fd; font-weight: 700; }
  #roadmap-content ol    { padding-left: 1.3em; display: flex; flex-direction: column; gap: .4em; margin: .3em 0 .5em; }
  #roadmap-content a     { color: #60a5fa; text-decoration: underline; text-underline-offset: 2px; }
  #roadmap-content a:hover { color: #93c5fd; }

  #download-btn {
    margin-top: 4px; padding: 9px 14px; border-radius: 9px;
    background: var(--accent); border: none; color: #fff;
    font-size: 12.5px; font-weight: 600; cursor: pointer;
    display: flex; align-items: center; gap: 6px; justify-content: center;
    transition: background .15s; flex-shrink: 0;
  }
  #download-btn:hover { background: #1d4ed8; }
  #download-btn svg { width: 14px; height: 14px; fill: white; }
  #download-btn:disabled { opacity: .4; cursor: default; }

  /* ── Profile tab ── */
  .profile-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 10px;
  }
  .profile-row { display: flex; flex-direction: column; gap: 3px; }
  .profile-label { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
  .profile-val   { font-size: 13px; color: var(--text); font-weight: 600; min-height: 18px; }
  .profile-val.empty { color: var(--muted); font-weight: 400; font-style: italic; }

  /* ══ Chat area ══════════════════════════════════════════════════════════ */
  .chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-width: 0;
  }

  #chat-output {
    flex: 1; overflow-y: auto;
    padding: 20px 20px 8px;
    display: flex; flex-direction: column; gap: 16px;
    scroll-behavior: smooth;
  }

  .msg { display: flex; gap: 10px; align-items: flex-start; }
  .msg.user { flex-direction: row-reverse; }

  .avatar {
    width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 800; letter-spacing: -.5px;
    margin-top: 2px;
  }
  .msg.bot  .avatar { background: #1a3560; color: #7db8f7; border: 1.5px solid #2a4a80; }
  .msg.user .avatar { background: #2d1b52; color: #b89dfa; border: 1.5px solid #4a2d8a; }

  .bubble-wrap { display: flex; flex-direction: column; max-width: min(80%, 560px); gap: 4px; }
  .msg.user .bubble-wrap { align-items: flex-end; }

  .bubble {
    padding: 11px 15px; border-radius: 18px;
    font-size: 14px; line-height: 1.7;
    word-break: break-word; overflow-wrap: anywhere; width: 100%;
  }
  .msg.bot  .bubble { background: var(--surface); border: 1px solid var(--border); border-top-left-radius: 4px; }
  .msg.user .bubble { background: #1a3560; border: 1px solid #2a4a7f; border-top-right-radius: 4px; color: #e8f0ff; }
  .msg.user .bubble { white-space: pre-wrap; }

  /* markdown inside bot bubbles */
  .bubble p      { margin: 0 0 .5em; }
  .bubble p:last-child { margin-bottom: 0; }
  .bubble strong { color: #93c5fd; font-weight: 700; }
  .bubble em     { color: #c4b5fd; }
  .bubble ol     { padding-left: 1.4em; margin: .35em 0 .5em; display: flex; flex-direction: column; gap: .3em; }
  .bubble a      { color: #60a5fa; text-decoration: underline; text-underline-offset: 2px; }
  .bubble a:hover { color: #93c5fd; }
  .bubble code   { background: #1e293b; border-radius: 4px; padding: 1px 5px; font-size: 13px; color: #7dd3fc; }

  .copy-btn {
    align-self: flex-end; background: none; border: none; cursor: pointer;
    color: #444; font-size: 11px; padding: 2px 4px;
    display: flex; align-items: center; gap: 4px; transition: color .15s;
    user-select: none;
  }
  .copy-btn:hover { color: #7db8f7; }
  .copy-btn svg   { width: 13px; height: 13px; fill: currentColor; flex-shrink: 0; }

  /* typing */
  .typing-bubble {
    padding: 12px 16px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 18px; border-top-left-radius: 4px;
    display: flex; align-items: center; gap: 4px;
  }
  .typing-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent); opacity: .3;
    animation: pulse 1.4s ease-in-out infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: .2s; }
  .typing-dot:nth-child(3) { animation-delay: .4s; }
  @keyframes pulse { 0%,60%,100%{opacity:.2;transform:scale(1)} 30%{opacity:1;transform:scale(1.2)} }

  /* ══ Input area ══════════════════════════════════════════════════════════ */
  #input-area {
    padding: 10px 20px 18px;
    border-top: 1px solid var(--border);
    background: var(--bg); flex-shrink: 0;
  }
  #input-row {
    display: flex; gap: 8px; align-items: flex-end;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 8px 8px 8px 16px;
    transition: border-color .15s;
  }
  #input-row:focus-within { border-color: #3b5bdb; }
  #user-input {
    flex: 1; background: transparent; border: none; outline: none;
    color: var(--text); font-size: 14px; line-height: 1.55;
    resize: none; max-height: 140px; font-family: inherit; padding: 2px 0;
  }
  #user-input::placeholder { color: #444; }
  #send-btn {
    background: var(--accent); border: none; border-radius: 10px;
    width: 36px; height: 36px; cursor: pointer; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    transition: background .15s, opacity .15s;
  }
  #send-btn:hover:not(:disabled) { background: #1d4ed8; }
  #send-btn:disabled { opacity: .35; cursor: default; }
  #send-btn svg { width: 16px; height: 16px; fill: white; }
  #footer-row {
    display: flex; align-items: center; justify-content: flex-end;
    margin-top: 6px;
  }
  #reset-btn {
    background: none; border: none; color: #3a3a3a; font-size: 12px;
    cursor: pointer; padding: 2px 0; transition: color .15s;
    display: flex; align-items: center; gap: 4px;
  }
  #reset-btn:hover { color: #666; }

  /* ══ Responsive ══════════════════════════════════════════════════════════ */
  @media (max-width: 640px) {
    .sidebar { display: none; }
    #chat-output { padding: 14px 12px 4px; }
    #input-area  { padding: 8px 12px 14px; }
  }
</style>
</head>
<body>

<header>
  <div class="logo">&#127891;</div>
  <div>
    <h1>LearnMate</h1>
    <p>AI Career Learning Coach &mdash; powered by IBM Granite</p>
  </div>
</header>

<div class="layout">

  <!-- ══ Sidebar ══════════════════════════════════════════════════════════ -->
  <aside class="sidebar">
    <div class="tab-bar">
      <button class="tab-btn active" data-tab="progress">Progress</button>
      <button class="tab-btn"        data-tab="roadmap">My Roadmap</button>
      <button class="tab-btn"        data-tab="profile">Profile</button>
    </div>

    <!-- Progress tab -->
    <div class="tab-panel active" id="tab-progress">
      <div>
        <div class="prog-header">Your Progress</div>
        <div class="prog-sub" id="prog-sub">Start a conversation to begin.</div>
      </div>

      <div class="prog-ring-wrap">
        <div class="prog-ring">
          <svg viewBox="0 0 110 110">
            <circle class="track"  cx="55" cy="55" r="45"/>
            <circle class="fill" id="prog-fill" cx="55" cy="55" r="45"/>
          </svg>
          <div class="prog-pct" id="prog-pct">0%</div>
        </div>
        <div class="prog-label" id="prog-stage-label">No roadmap yet</div>
      </div>

      <div class="stage-list" id="stage-list">
        <div style="font-size:12px;color:var(--muted);text-align:center;padding:8px 0">
          Stages will appear once your roadmap is generated.
        </div>
      </div>
    </div>

    <!-- Roadmap tab -->
    <div class="tab-panel" id="tab-roadmap" style="gap:12px">
      <div id="roadmap-content">
        <div class="roadmap-empty">
          Your personalised roadmap will appear here once LearnMate generates it.
          Start chatting to get going!
        </div>
      </div>
      <button id="download-btn" disabled>
        <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zm-8 2V5h2v6h1.17L12 13.17 9.83 11H11zm-6 7h14v2H5v-2z"/></svg>
        Download Roadmap
      </button>
    </div>

    <!-- Profile tab -->
    <div class="tab-panel" id="tab-profile">
      <div class="profile-card">
        <div class="profile-row">
          <div class="profile-label">Career Goal</div>
          <div class="profile-val empty" id="pf-field">Not set yet</div>
        </div>
        <div class="profile-row">
          <div class="profile-label">Skill Level</div>
          <div class="profile-val empty" id="pf-level">Not set yet</div>
        </div>
        <div class="profile-row">
          <div class="profile-label">Study Time / Week</div>
          <div class="profile-val empty" id="pf-hours">Not set yet</div>
        </div>
        <div class="profile-row">
          <div class="profile-label">Current Stage</div>
          <div class="profile-val empty" id="pf-stage">—</div>
        </div>
        <div class="profile-row">
          <div class="profile-label">Stages Completed</div>
          <div class="profile-val empty" id="pf-done">0</div>
        </div>
      </div>
    </div>
  </aside>

  <!-- ══ Chat ═════════════════════════════════════════════════════════════ -->
  <div class="chat-area">
    <div id="chat-output" role="log" aria-live="polite" aria-label="Conversation"></div>

    <div id="input-area">
      <div id="input-row">
        <textarea id="user-input" rows="1"
          placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
          aria-label="Your message" autocomplete="off"></textarea>
        <button id="send-btn" aria-label="Send message">
          <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
        </button>
      </div>
      <div id="footer-row">
        <button id="reset-btn">&#8635; Start over</button>
      </div>
    </div>
  </div>
</div>

<!-- Congrats toast -->
<div id="congrats-toast"></div>

<script>
// ═══════════════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════════════
let appState = {
  chosen_field:  '',
  skill_level:   '',
  weekly_hours:  0,
  current_stage: 0,
  total_stages:  0,
  stages_done:   [],
  progress_pct:  0,
  roadmap_text:  '',
  roadmap_ready: false,
};

// ═══════════════════════════════════════════════════════════════════════════
// Markdown renderer (same as before, with table support added)
// ═══════════════════════════════════════════════════════════════════════════
function renderMarkdown(md) {
  let s = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  s = s.replace(/<&lt;[|](user|assistant|system|endoftext)[|]&gt;/gi, '');

  const lines = s.split('\n');
  const out = [];
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    const listMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (listMatch) {
      if (!inOl) { out.push('<ol>'); inOl = true; }
      out.push('<li>' + inlineFormat(listMatch[2]) + '</li>');
      continue;
    }
    if (inOl) { out.push('</ol>'); inOl = false; }
    if (line.trim() === '') { out.push('<p></p>'); continue; }
    out.push('<p>' + inlineFormat(line) + '</p>');
  }
  if (inOl) out.push('</ol>');
  return out.join('').replace(/(<p><\/p>){2,}/g, '<p></p>');
}

// Trusted domain allow-list for link validation.
// YouTube watch URLs are explicitly blocked (search URLs are allowed).
const TRUSTED_DOMAINS = [
  'youtube.com/results',          // YouTube search — always safe
  'developer.mozilla.org',
  'freecodecamp.org',
  'w3schools.com',
  'roadmap.sh',
  'docs.python.org',
  'javascript.info',
  'cs50.harvard.edu',
  'theodinproject.com',
  'odin-project.com',
  'kaggle.com/learn',
  'developers.google.com',
  'web.dev',
  'docs.github.com',
  'git-scm.com',
  'learnpython.org',
  'eloquentjavascript.net',
  'react.dev',
  'reactjs.org',
  'vuejs.org',
  'docs.djangoproject.com',
  'fastapi.tiangolo.com',
  'scikit-learn.org',
  'numpy.org',
  'pandas.pydata.org',
  'matplotlib.org',
  'tensorflow.org',
  'pytorch.org',
  'd3js.org',
  'cybrary.it',
  'tryhackme.com',
  'owasp.org',
  'portswigger.net',
  'figma.com',
  'material.io',
  'nngroup.com',
  'interaction-design.org',
  'docs.npmjs.com',
  'nodejs.org',
  'typescriptlang.org',
  'golang.org',
  'go.dev',
  'rust-lang.org',
  'docs.oracle.com',
  'spring.io',
  'kotlinlang.org',
  'developer.apple.com',
  'developer.android.com',
  'flutter.dev',
  'dart.dev',
  'aws.amazon.com/getting-started',
  'cloud.google.com/training',
  'learn.microsoft.com',
  'docs.docker.com',
  'kubernetes.io/docs',
  'prometheus.io/docs',
  'grafana.com/docs',
  'postgresql.org/docs',
  'mysql.com/documentation',
  'mongodb.com/docs',
  'redis.io/docs',
];

// YouTube watch links (fabricated video IDs) are never trustworthy.
const BLOCKED_PATTERNS = [
  /youtube\.com\/watch/i,
  /youtu\.be\//i,
];

function sanitizeUrl(url) {
  // Block fabricated YouTube watch links outright
  for (const pat of BLOCKED_PATTERNS) {
    if (pat.test(url)) return null;
  }
  // Allow only trusted domains
  try {
    const hostname = new URL(url).hostname.replace(/^www\./, '');
    const path     = new URL(url).pathname;
    const full     = hostname + path;
    for (const domain of TRUSTED_DOMAINS) {
      if (full.startsWith(domain) || hostname === domain ||
          hostname.endsWith('.' + domain)) {
        return url;
      }
    }
  } catch (e) { return null; }
  return null; // not on the allow-list → strip link
}

function inlineFormat(s) {
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Validate each link before rendering it
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (match, text, url) => {
    const safe = sanitizeUrl(url);
    if (safe) {
      return '<a href="' + safe + '" target="_blank" rel="noopener noreferrer">' + text + '</a>';
    }
    // Strip the link but keep the label text so content isn't lost
    return text;
  });
  return s;
}

// ═══════════════════════════════════════════════════════════════════════════
// Sidebar updates
// ═══════════════════════════════════════════════════════════════════════════
function updateSidebar(st) {
  appState = Object.assign(appState, st);

  // ── Progress ring ──
  const pct     = st.progress_pct || 0;
  const fill    = document.getElementById('prog-fill');
  const pctEl   = document.getElementById('prog-pct');
  const lblEl   = document.getElementById('prog-stage-label');
  const subEl   = document.getElementById('prog-sub');
  const circumf = 283; // 2π×45
  fill.style.strokeDashoffset = circumf - (circumf * pct / 100);
  fill.classList.toggle('complete', pct === 100);
  pctEl.textContent = pct + '%';

  if (st.total_stages > 0) {
    lblEl.textContent = `Stage ${Math.min(st.current_stage, st.total_stages)} of ${st.total_stages}`;
    subEl.textContent = `${st.stages_done.length} stage${st.stages_done.length !== 1 ? 's' : ''} completed`;
  } else {
    lblEl.textContent = 'No roadmap yet';
    subEl.textContent = 'Start a conversation to begin.';
  }

  // ── Stage list ──
  const list = document.getElementById('stage-list');
  if (st.total_stages > 0) {
    list.innerHTML = '';
    for (let i = 1; i <= st.total_stages; i++) {
      const done    = st.stages_done.includes(i);
      const current = (i === st.current_stage);
      const item = document.createElement('div');
      item.className = 'stage-item' + (done ? ' done' : current ? ' current' : '');
      item.innerHTML =
        `<div class="stage-dot"></div>` +
        `<div class="stage-name">Stage ${i}</div>` +
        (done ? `<span class="stage-check">&#10003;</span>` : '');
      list.appendChild(item);
    }
  }

  // ── Roadmap tab ──
  const rdContent  = document.getElementById('roadmap-content');
  const dlBtn      = document.getElementById('download-btn');
  if (st.roadmap_ready && st.roadmap_text) {
    rdContent.innerHTML = renderMarkdown(st.roadmap_text);
    dlBtn.disabled = false;
  }

  // ── Profile tab ──
  function setField(id, val, unit) {
    const el = document.getElementById(id);
    if (val) {
      el.textContent = val + (unit || '');
      el.classList.remove('empty');
    } else {
      el.textContent = 'Not set yet';
      el.classList.add('empty');
    }
  }
  setField('pf-field', st.chosen_field
    ? st.chosen_field.charAt(0).toUpperCase() + st.chosen_field.slice(1) : '');
  setField('pf-level', st.skill_level
    ? st.skill_level.charAt(0).toUpperCase() + st.skill_level.slice(1) : '');
  setField('pf-hours', st.weekly_hours ? st.weekly_hours : '', st.weekly_hours ? ' hrs/week' : '');
  const stageEl = document.getElementById('pf-stage');
  if (st.total_stages > 0) {
    stageEl.textContent = `${st.current_stage} / ${st.total_stages}`;
    stageEl.classList.remove('empty');
  } else {
    stageEl.textContent = '—';
    stageEl.classList.add('empty');
  }
  const doneEl = document.getElementById('pf-done');
  doneEl.textContent = st.stages_done.length;
  doneEl.classList.toggle('empty', st.stages_done.length === 0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Congrats toast
// ═══════════════════════════════════════════════════════════════════════════
function showCongratsToast(msg) {
  const toast = document.getElementById('congrats-toast');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 4000);
}

// ═══════════════════════════════════════════════════════════════════════════
// Chat rendering
// ═══════════════════════════════════════════════════════════════════════════
const output  = document.getElementById('chat-output');
const input   = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

function appendMsg(role, text) {
  const wrap  = document.createElement('div');
  wrap.className = 'msg ' + role;
  const av    = document.createElement('div');
  av.className = 'avatar';
  av.textContent = role === 'bot' ? 'LM' : 'You';
  const bWrap = document.createElement('div');
  bWrap.className = 'bubble-wrap';
  const bub   = document.createElement('div');
  bub.className = 'bubble';

  if (role === 'bot') {
    bub.innerHTML = renderMarkdown(text);
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.setAttribute('aria-label', 'Copy message');
    copyBtn.innerHTML =
      '<svg viewBox="0 0 24 24"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"/></svg>' +
      '<span>Copy</span>';
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(text).then(() => {
        copyBtn.querySelector('span').textContent = 'Copied!';
        setTimeout(() => { copyBtn.querySelector('span').textContent = 'Copy'; }, 1800);
      });
    });
    bWrap.appendChild(bub);
    bWrap.appendChild(copyBtn);
  } else {
    bub.textContent = text;
    bWrap.appendChild(bub);
  }

  wrap.appendChild(av);
  wrap.appendChild(bWrap);
  output.appendChild(wrap);
  scrollToBottom();
}

function showTyping() {
  const wrap = document.createElement('div');
  wrap.className = 'msg bot'; wrap.id = 'typing-indicator';
  const av = document.createElement('div');
  av.className = 'avatar'; av.textContent = 'LM';
  const tb = document.createElement('div');
  tb.className = 'typing-bubble';
  tb.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
  wrap.appendChild(av); wrap.appendChild(tb);
  output.appendChild(wrap);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

function scrollToBottom() {
  requestAnimationFrame(() => { output.scrollTop = output.scrollHeight; });
}

// Boot greeting
const GREETING = "Hello! \uD83D\uDC4B What tech career field are you interested in pursuing? For example: software development, data science, cybersecurity, UX design, etc.";
appendMsg('bot', GREETING);

// ═══════════════════════════════════════════════════════════════════════════
// Send
// ═══════════════════════════════════════════════════════════════════════════
async function sendMessage() {
  const text = input.value.trim();
  if (!text || sendBtn.disabled) return;
  input.value = '';
  autoResize();
  appendMsg('user', text);
  sendBtn.disabled = true;
  showTyping();

  try {
    const res  = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    removeTyping();
    appendMsg('bot', data.reply || 'Something went wrong. Please try again.');

    // Update sidebar with fresh state
    if (data.state) updateSidebar(data.state);

    // Show congrats toast if a stage was just completed
    if (data.stage_completed && data.state && data.state.stages_done.length > 0) {
      const n = data.state.stages_done[data.state.stages_done.length - 1];
      showCongratsToast(
        `\uD83C\uDF89 Stage ${n} complete! Keep it up — you're making great progress!`
      );
      // Auto-switch to Progress tab to show the update
      switchTab('progress');
    }
  } catch (e) {
    removeTyping();
    appendMsg('bot', 'Connection error — is the server running?');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Reset
// ═══════════════════════════════════════════════════════════════════════════
async function resetConversation() {
  await fetch('/reset', { method: 'POST' });
  output.innerHTML = '';
  appState = { chosen_field:'', skill_level:'', weekly_hours:0,
               current_stage:0, total_stages:0, stages_done:[],
               progress_pct:0, roadmap_text:'', roadmap_ready:false };
  updateSidebar(appState);
  document.getElementById('roadmap-content').innerHTML =
    '<div class="roadmap-empty">Your personalised roadmap will appear here once LearnMate generates it. Start chatting to get going!</div>';
  document.getElementById('download-btn').disabled = true;
  appendMsg('bot', GREETING);
  input.focus();
}

// ═══════════════════════════════════════════════════════════════════════════
// Download roadmap as plain text file
// ═══════════════════════════════════════════════════════════════════════════
document.getElementById('download-btn').addEventListener('click', () => {
  if (!appState.roadmap_text) return;
  const header =
    `LearnMate — Career Roadmap\n` +
    `===========================\n` +
    `Field      : ${appState.chosen_field || 'N/A'}\n` +
    `Skill Level: ${appState.skill_level  || 'N/A'}\n` +
    `Study Time : ${appState.weekly_hours ? appState.weekly_hours + ' hrs/week' : 'N/A'}\n` +
    `Generated  : ${new Date().toLocaleDateString()}\n\n` +
    `───────────────────────────\n\n`;
  const blob = new Blob([header + appState.roadmap_text], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'LearnMate_Roadmap.txt';
  a.click();
  URL.revokeObjectURL(url);
});

// ═══════════════════════════════════════════════════════════════════════════
// Tab switching
// ═══════════════════════════════════════════════════════════════════════════
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === name);
  });
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + name);
  });
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ═══════════════════════════════════════════════════════════════════════════
// Auto-resize textarea
// ═══════════════════════════════════════════════════════════════════════════
function autoResize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
}

// ═══════════════════════════════════════════════════════════════════════════
// Event listeners
// ═══════════════════════════════════════════════════════════════════════════
sendBtn.addEventListener('click', sendMessage);
document.getElementById('reset-btn').addEventListener('click', resetConversation);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
input.addEventListener('input', autoResize);
input.focus();
</script>
</body>
</html>
"""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return render_template_string(HTML)


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    sid = session["sid"]

    data = request.get_json(force=True)
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"reply": ""}), 400

    try:
        ctx = _get_or_create(sid)
    except RuntimeError as exc:
        return jsonify({"reply": str(exc)}), 500

    ctx["turns"] += 1
    if ctx["turns"] % 20 == 0:
        ctx["token"] = get_iam_token(API_KEY)

    try:
        reply, stage_completed = chat(
            ctx["session"], user_message, ctx["token"], ctx["state"]
        )
    except Exception as exc:
        return jsonify({"reply": f"Model error: {exc}"}), 500

    return jsonify({
        "reply":           reply,
        "stage_completed": stage_completed,
        "state":           ctx["state"].to_dict(),
    })


@app.route("/reset", methods=["POST"])
def reset_endpoint():
    sid = session.get("sid")
    if sid and sid in _sessions:
        del _sessions[sid]
    session.clear()
    return jsonify({"status": "reset"})


@app.route("/state", methods=["GET"])
def state_endpoint():
    """Return current user state (for debugging or polling)."""
    sid = session.get("sid")
    if not sid or sid not in _sessions:
        return jsonify(UserState().to_dict())
    return jsonify(_sessions[sid]["state"].to_dict())


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("WATSONX_API_KEY is not set in .env")
    print("LearnMate web UI \u2192 http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
