"""
learnmate_agent.py
------------------
LearnMate — Agentic AI personal learning coach.
Backed by ibm/granite-4-h-small on watsonx.ai.

Usage (terminal):
    pip install -r requirements.txt
    python learnmate_agent.py

Usage (web UI):
    python app.py          # starts Flask server on http://localhost:5000
"""

import os
import re
import requests
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(override=True)

# ── Config ────────────────────────────────────────────────────────────────────
API_URL    = os.getenv(
    "WATSONX_API_URL",
    "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2023-05-29",
)
MODEL_ID   = os.getenv("WATSONX_MODEL_ID",   "ibm/granite-4-h-small")
PROJECT_ID = os.getenv("WATSONX_PROJECT_ID", "436c62bd-c6a7-4ae5-97d2-d01538f32a66")
API_KEY    = os.getenv("WATSONX_API_KEY",    "")

# ── Exact opening greeting ────────────────────────────────────────────────────
GREETING = (
    "Hello! \U0001f44b What tech career field are you interested in pursuing? "
    "For example: software development, data science, cybersecurity, "
    "UX design, etc."
)

# ── Special tokens to strip from model output ────────────────────────────────
_SPECIAL_TOKEN_RE = re.compile(
    r"<\|(?:user|assistant|system|endoftext)\|>", re.IGNORECASE
)

def _clean(text: str) -> str:
    """Strip any leaked Granite special tokens from a generation result."""
    return _SPECIAL_TOKEN_RE.sub("", text).strip()


# ── Completion detection ──────────────────────────────────────────────────────
_COMPLETION_RE = re.compile(
    r"\b(?:i(?:'ve|\s+have)?\s+(?:finished|completed|done(?:\s+with)?|wrapped\s+up)"
    r"|done\s+with|finished|completed)\s+(?:stage\s*)?(\d+)\b",
    re.IGNORECASE,
)
_FIELD_CHANGE_RE = re.compile(
    r"\b(?:switch(?:ing)?\s+to|change\s+to|want\s+to\s+(?:do|learn|try)|"
    r"interested\s+in|pivot\s+to)\s+([a-z][a-z\s/]+?)(?:\s+instead|\s+now|[.,!?]|$)",
    re.IGNORECASE,
)
_TIME_CHANGE_RE = re.compile(
    r"\b(?:now\s+(?:have|can\s+do)|can\s+(?:now\s+)?(?:do|dedicate|give)|"
    r"changed?\s+to|have\s+(?:more|less)\s+time.*?|"
    r"only\s+have)\s+(\d+)\s*h(?:ours?)?(?:\s+(?:a|per)\s+week)?\b",
    re.IGNORECASE,
)


def detect_completion(text: str) -> int | None:
    """Return stage number if user says they finished a stage, else None."""
    m = _COMPLETION_RE.search(text)
    return int(m.group(1)) if m else None


def detect_field_change(text: str) -> str | None:
    """Return new field name if user signals a switch, else None."""
    m = _FIELD_CHANGE_RE.search(text)
    return m.group(1).strip().lower() if m else None


def detect_time_change(text: str) -> int | None:
    """Return new weekly hours if user says their time changed, else None."""
    m = _TIME_CHANGE_RE.search(text)
    return int(m.group(1)) if m else None


# ── User state ────────────────────────────────────────────────────────────────
@dataclass
class UserState:
    """Tracks the student's profile, roadmap, and progress across turns."""
    chosen_field:    str        = ""
    skill_level:     str        = ""        # beginner | intermediate | advanced
    weekly_hours:    int        = 0
    current_stage:   int        = 0         # 0 = roadmap not yet generated
    total_stages:    int        = 0
    stages_done:     list[int]  = field(default_factory=list)
    roadmap_text:    str        = ""        # latest full roadmap markdown
    roadmap_ready:   bool       = False

    @property
    def progress_pct(self) -> int:
        if self.total_stages <= 0:
            return 0
        return round(len(self.stages_done) / self.total_stages * 100)

    def mark_done(self, stage: int) -> bool:
        """Mark a stage complete. Returns True if it was newly completed."""
        if stage not in self.stages_done and 1 <= stage <= max(self.total_stages, stage):
            self.stages_done.append(stage)
            self.current_stage = max(self.stages_done) + 1
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "chosen_field":  self.chosen_field,
            "skill_level":   self.skill_level,
            "weekly_hours":  self.weekly_hours,
            "current_stage": self.current_stage,
            "total_stages":  self.total_stages,
            "stages_done":   self.stages_done,
            "progress_pct":  self.progress_pct,
            "roadmap_text":  self.roadmap_text,
            "roadmap_ready": self.roadmap_ready,
        }


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are LearnMate, an agentic AI personal learning coach for students.
Every reply reads like a message from a supportive, knowledgeable mentor.

Your exact opening message when the user first says hello is:
"Hello! What tech career field are you interested in pursuing? For example: software development, data science, cybersecurity, UX design, etc."

Session flow:
1. After the user names a field, ask 2-3 short questions to find out:
   a) their current skill level (beginner, intermediate, or advanced), and
   b) how many hours per week they can realistically dedicate.
2. Once you have field + level + weekly hours, generate a structured numbered roadmap.
   Each stage must include: the stage name, what they will learn, estimated duration
   (calculated from weekly hours), and 1-2 free resources with links following the
   STRICT LINK RULES below.
   Always end the roadmap with a line: "Total stages: N" where N is the number of stages.
3. When the user says they finished a stage (e.g. "I finished stage 2", "done with stage 3"):
   - Congratulate them warmly and specifically (mention what they mastered).
   - Give a short motivational nudge toward the next stage.
   - Do NOT re-print the full roadmap unless they ask.
4. If the user changes their available time or switches career field mid-conversation:
   - Acknowledge the change explicitly.
   - Update the roadmap from their current stage onward to fit the new constraint.
   - Do NOT restart from stage 1 unless they explicitly ask to.
5. If they ask a general career question (salary, job demand, resume tips, etc.),
   answer briefly and helpfully, then offer to return to the roadmap.

STRICT LINK RULES — follow these exactly, no exceptions:
- For YouTube recommendations: NEVER invent a video URL (e.g. never use youtube.com/watch?v=...).
  Instead, always use a YouTube search link:
  https://www.youtube.com/results?search_query=topic+keywords+here
  Replace spaces with + signs in the query. Example:
  [Python for Beginners – YouTube](https://www.youtube.com/results?search_query=python+for+beginners+tutorial)
- For courses and articles: only link to these trusted stable domains you know exist:
    developer.mozilla.org, freecodecamp.org, w3schools.com, roadmap.sh,
    docs.python.org, javascript.info, cs50.harvard.edu, odin-project.com,
    theodinproject.com, kaggle.com/learn, developers.google.com,
    web.dev, docs.github.com, git-scm.com/doc, learnpython.org,
    eloquentjavascript.net, reactjs.org, vuejs.org, docs.djangoproject.com,
    fastapi.tiangolo.com, scikit-learn.org, numpy.org, pandas.pydata.org,
    matplotlib.org, tensorflow.org, pytorch.org, d3js.org,
    cybrary.it, tryhackme.com, owasp.org, portswigger.net/web-security,
    figma.com/resources, material.io, nngroup.com, interaction-design.org
- If you are not 100% certain a specific page exists on those domains, link to the
  domain root or a search link instead of guessing a deep path.
- NEVER fabricate URLs to specific blog posts, course pages, or video IDs.
- If you cannot produce a valid link for a resource, write the resource name as
  plain text only — no link at all. Do not use a placeholder like example.com.

Formatting rules:
- Use markdown: **bold** for stage names, numbered lists for stages,
  and [Title](URL) links for every resource.
- Do NOT use raw HTML. Do NOT use bullet symbols (-, *, •).
- Do NOT emit special tokens like <|user|>, <|assistant|>, or <|endoftext|>.

State you must track silently across every turn:
- chosen_field      (e.g. "data science")
- skill_level       (beginner | intermediate | advanced)
- weekly_hours      (number)
- current_stage     (integer, starts at 1 once roadmap is generated)
- total_stages      (integer, set when roadmap is first generated)

Tone: always encouraging, concise, and conversational. Never over-explain."""


# ── Roadmap parser ────────────────────────────────────────────────────────────
_TOTAL_STAGES_RE = re.compile(r"total\s+stages?\s*[:=]\s*(\d+)", re.IGNORECASE)
_STAGE_HEADER_RE = re.compile(r"^\d+\.", re.MULTILINE)
_PROFILE_FIELD_RE = re.compile(
    r"\b(?:field|career|goal)[:\s]+([a-z][a-z\s/&+]+?)(?:\n|,|\.|$)", re.IGNORECASE
)
_PROFILE_LEVEL_RE = re.compile(
    r"\b(beginner|intermediate|advanced)\b", re.IGNORECASE
)
_PROFILE_HOURS_RE = re.compile(
    r"\b(\d+)\s*h(?:ours?)?(?:\s*(?:a|per)\s*week)?\b", re.IGNORECASE
)


def parse_roadmap_from_reply(reply: str, state: UserState) -> None:
    """
    Extract total_stages, roadmap_text, and profile fields from a model reply
    and update state in-place.
    """
    # Total stages hint the model was asked to emit
    m = _TOTAL_STAGES_RE.search(reply)
    if m:
        state.total_stages = int(m.group(1))
    else:
        # Fall back: count numbered stage headers
        count = len(_STAGE_HEADER_RE.findall(reply))
        if count >= 2:
            state.total_stages = count

    if state.total_stages > 0:
        state.roadmap_text  = reply
        state.roadmap_ready = True
        if state.current_stage == 0:
            state.current_stage = 1

    # Extract profile fields if not yet set
    if not state.chosen_field:
        m2 = _PROFILE_FIELD_RE.search(reply)
        if m2:
            state.chosen_field = m2.group(1).strip().lower()
    if not state.skill_level:
        m3 = _PROFILE_LEVEL_RE.search(reply)
        if m3:
            state.skill_level = m3.group(1).lower()
    if not state.weekly_hours:
        m4 = _PROFILE_HOURS_RE.search(reply)
        if m4:
            state.weekly_hours = int(m4.group(1))


def update_profile_from_user(msg: str, state: UserState) -> None:
    """Parse a user message for profile signals and update state."""
    if not state.chosen_field:
        m = _PROFILE_FIELD_RE.search(msg)
        if m:
            state.chosen_field = m.group(1).strip().lower()
    if not state.skill_level:
        m = _PROFILE_LEVEL_RE.search(msg)
        if m:
            state.skill_level = m.group(1).lower()
    if not state.weekly_hours:
        m = _PROFILE_HOURS_RE.search(msg)
        if m:
            state.weekly_hours = int(m.group(1))

    # Field / time changes
    new_field = detect_field_change(msg)
    if new_field and len(new_field) > 2:
        state.chosen_field  = new_field
        state.roadmap_ready = False   # will be refreshed when model responds
        state.stages_done   = []
        state.total_stages  = 0

    new_hours = detect_time_change(msg)
    if new_hours:
        state.weekly_hours = new_hours


# ── Session (conversation history) ───────────────────────────────────────────
class Session:
    """Holds the full conversation history for one user session."""

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.history.append({"role": "assistant", "content": GREETING})

    def add_user(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})

    def build_prompt(self) -> str:
        parts = [f"<|system|>\n{SYSTEM_PROMPT}\n"]
        for turn in self.history:
            if turn["role"] == "user":
                parts.append(f"<|user|>\n{turn['content']}\n")
            else:
                parts.append(f"<|assistant|>\n{turn['content']}\n")
        parts.append("<|assistant|>\n")
        return "".join(parts)


# ── IAM token ─────────────────────────────────────────────────────────────────
def get_iam_token(api_key: str) -> str:
    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
              "apikey": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── watsonx generation ────────────────────────────────────────────────────────
_STOP_SEQUENCES = ["<|user|>", "<|assistant|>", "<|system|>", "<|endoftext|>"]

def generate(token: str, prompt: str) -> str:
    payload = {
        "model_id":   MODEL_ID,
        "project_id": PROJECT_ID,
        "input":      prompt,
        "parameters": {
            "decoding_method":    "greedy",
            "max_new_tokens":     900,
            "stop_sequences":     _STOP_SEQUENCES,
            "temperature":        0.7,
            "repetition_penalty": 1.05,
        },
    }
    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    raw = resp.json()["results"][0]["generated_text"]
    return _clean(raw)


# ── chat() — one turn, updates session + state ────────────────────────────────
def chat(
    session: Session,
    user_message: str,
    token: str,
    state: UserState | None = None,
) -> tuple[str, bool]:
    """
    Process one user turn.
    Returns (reply_text, stage_completed: bool).
    If `state` is provided, updates it from the conversation.
    """
    completed_stage: int | None = None

    if state is not None:
        update_profile_from_user(user_message, state)
        completed_stage = detect_completion(user_message)
        if completed_stage:
            state.mark_done(completed_stage)

    session.add_user(user_message)
    reply = generate(token, session.build_prompt())
    session.add_assistant(reply)

    if state is not None:
        parse_roadmap_from_reply(reply, state)
        # Also try to fill profile fields from model replies
        if not state.skill_level:
            m = _PROFILE_LEVEL_RE.search(reply)
            if m:
                state.skill_level = m.group(1).lower()

    return reply, completed_stage is not None


# ── Terminal entry point ──────────────────────────────────────────────────────
def main() -> None:
    if not API_KEY:
        raise SystemExit(
            "WATSONX_API_KEY is not set.\n"
            "Copy .env.example to .env and add your IBM Cloud IAM API key."
        )

    print("\nLearnMate is starting…\n")
    token   = get_iam_token(API_KEY)
    sess    = Session()
    state   = UserState()

    print(f"LearnMate: {GREETING}\n")

    turn_count = 0
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nLearnMate: Great work today! Come back any time. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            print("LearnMate: Great work today! Come back any time. Goodbye!")
            break

        turn_count += 1
        if turn_count % 20 == 0:
            token = get_iam_token(API_KEY)

        reply, _ = chat(sess, user_input, token, state)
        print(f"\nLearnMate: {reply}\n")
        if state.roadmap_ready:
            print(f"  [Progress: {state.progress_pct}% — "
                  f"stage {state.current_stage}/{state.total_stages}]\n")


if __name__ == "__main__":
    main()
