"""Visual layer: tinted canvas, floating sheet, serif display headings,
mono micro-labels, accent-dotted reason rows.

Design language (after the reference the user provided, not a copy):
  * page canvas is a soft lavender; all content floats on one white
    rounded sheet, so the app reads as a single instrument panel
  * section titles are serif display type; statuses sit right-aligned
    on the same baseline (DECLINED / APPROVED / REVIEW)
  * reason rows lead with the contribution share (or RULE), then the
    humanized code name, approved consumer text underneath, and a
    colored accent dot per rank
  * identifiers are always mono chips; micro-labels are tracked
    uppercase mono
"""

CSS = """
<style>
/* ---- chrome removal + canvas ---- */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
[data-testid="stAppViewContainer"] { background: #dfe0f5; }
.block-container {
  padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1220px;
}
/* the floating sheet */
[data-testid="stMainBlockContainer"] > div:first-child { position: relative; }
.sheet-bg {
  position: fixed; inset: 0; background: #dfe0f5; z-index: -2;
}

/* ---- type ---- */
html, body, [class*="css"] {
  font-family: -apple-system, "SF Pro Text", "Segoe UI", Inter, Roboto, sans-serif;
  color: #23262e;
  -webkit-font-smoothing: antialiased;
}
/* app title becomes the tiny tracked mono masthead */
h1 {
  font-family: "SF Mono", ui-monospace, Menlo, monospace !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.38em !important;
  text-transform: uppercase !important;
  color: #6d7286 !important;
  text-align: center;
  padding-bottom: 0.4rem !important;
}
h1 + div [data-testid="stCaptionContainer"] p { text-align: center; }
[data-testid="stCaptionContainer"] p { color: #8a8fa3; font-size: 0.8rem; line-height: 1.6; }

/* serif display sections */
.display-row {
  display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 1px solid #ecedf2; padding: 0.35rem 0 0.75rem;
  margin: 0.6rem 0 1.1rem;
}
.display-title {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.55rem; font-weight: 600; letter-spacing: -0.01em; color: #17191f;
}
.display-status {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1.25rem; letter-spacing: 0.06em;
}
.status-decline { color: #17191f; }
.status-approve { color: #1d7a4f; }
.status-review  { color: #a06a00; }
.display-aux {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.75rem; letter-spacing: 0.12em; color: #8e4ec6;
}

/* micro labels */
.micro {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.66rem; letter-spacing: 0.22em; text-transform: uppercase;
  color: #8a8fa3; margin: 0.2rem 0 0.6rem;
}

/* ---- the white sheet look: only the two TOP-LEVEL columns are cards ---- */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
  background: #ffffff;
  border-radius: 22px;
  padding: 1.6rem 1.7rem 1.9rem;
  box-shadow: 0 18px 45px rgba(52,54,94,0.10), 0 2px 6px rgba(52,54,94,0.05);
}

/* nested columns are layout only, never cards */
[data-testid="stColumn"] [data-testid="stColumn"] {
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  border-radius: 0 !important;
}

/* ---- reason rows (reference style: pct | name+text | dot) ---- */
.reason-list { margin: 0.2rem 0 1.2rem; }
.reason-row {
  display: flex; align-items: center; gap: 1.1rem;
  padding: 0.95rem 0.2rem;
  border-bottom: 1px solid #f0f1f5;
}
.reason-row:last-child { border-bottom: none; }
.reason-share {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.86rem; color: #3d414d; min-width: 3.2rem; text-align: right;
}
.reason-main { flex: 1 1 14ch; min-width: 12ch; }
.reason-name { display: block; font-size: 0.98rem; font-weight: 620; color: #17191f; }
.reason-consumer { display: block; font-size: 0.83rem; color: #7d8294; margin-top: 0.15rem; }
.reason-dot {
  width: 26px; height: 26px; border-radius: 50%;
  border: 4px solid var(--dot, #8e4ec6);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--dot, #8e4ec6) 25%, transparent);
  flex: none;
}
.reason-codechip {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.62rem; letter-spacing: 0.06em; color: #9aa0b2;
  margin-top: 0.25rem; display: block;
}

/* ---- timeline (snapshot history) ---- */
.timeline { margin: 0.4rem 0 1.2rem; }
.tl-item { display: flex; gap: 0.85rem; padding: 0.45rem 0; }
.tl-bullet {
  width: 9px; height: 9px; border-radius: 50%; margin-top: 0.35rem; flex: none;
  background: #c9ccdb;
}
.tl-bullet.active { background: #8e4ec6; box-shadow: 0 0 0 3px rgba(142,78,198,0.2); }
.tl-title { font-size: 0.9rem; font-weight: 620; color: #23262e; }
.tl-title.active { color: #8e4ec6; }
.tl-meta {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.72rem; color: #9aa0b2; margin-top: 0.1rem;
}

/* ---- logic / info card ---- */
.logic-card {
  background: #f7f7fd; border-radius: 16px; padding: 1.15rem 1.25rem 1.3rem;
  margin: 0.6rem 0 1rem;
}
.logic-card p { font-size: 0.88rem; color: #4a4e5c; line-height: 1.6; margin: 0.5rem 0 0; }

/* ---- verdict paragraph under Governed Replay ---- */
.replay-note { font-size: 0.92rem; color: #3d414d; line-height: 1.75; }
.replay-note code { font-size: 0.8em; }

/* ---- controls ---- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 999px;
  border: none;
  background: #17191f;
  color: #ffffff;
  padding: 0.5rem 1.35rem;
  font-weight: 550; font-size: 0.88rem;
}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {
  background: #34363e; color: #fff;
}
.stButton > button[kind="secondary"] {
  background: #ffffff; color: #23262e; border: 1px solid #dcdee8;
}
.stButton > button[kind="secondary"]:hover { border-color: #a9adc0; background: #f7f7fd; }
[data-testid="stForm"] { border: none; padding: 0; }
[data-baseweb="select"] > div { border-radius: 12px !important; border-color: #e3e5ee !important; background: #f7f7fd !important; }
.stRadio label p { font-size: 0.85rem; }

/* ---- chips ---- */
code {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.76em;
  background: #f0f1f8 !important;
  color: #4a4e5c !important;
  border: none;
  border-radius: 6px;
  padding: 0.14em 0.5em;
}

/* ---- tabs ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid #ecedf2; }
[data-testid="stTabs"] [data-baseweb="tab"] { font-size: 0.85rem; color: #8a8fa3; padding-bottom: 0.6rem; }
[data-testid="stTabs"] [aria-selected="true"] { color: #17191f !important; font-weight: 600; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #17191f; }

/* ---- notice text blocks ---- */
[data-testid="stText"] {
  background: #f7f7fd;
  border: none;
  border-radius: 16px;
  padding: 1.2rem 1.35rem;
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.78rem; line-height: 1.7; color: #4a4e5c;
  white-space: pre-wrap;
}

/* ---- alerts (verify success etc) ---- */
[data-testid="stAlert"] { border-radius: 14px; border: none; }

/* ---- expander + tables ---- */
[data-testid="stExpander"] {
  border: 1px solid #eef0f5 !important; border-radius: 16px !important; background: #ffffff;
}
[data-testid="stExpander"] summary { font-size: 0.84rem; color: #6d7286; }
[data-testid="stTable"] { border: none; font-size: 0.84rem; }
[data-testid="stTable"] thead th {
  background: #f7f7fd; text-transform: uppercase; letter-spacing: 0.1em;
  font-size: 0.64rem; color: #9aa0b2;
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
}
</style>
"""

# accent palette cycled by rank, after the reference's dot colors
DOT_COLORS = ["#e5484d", "#8e4ec6", "#ffb224", "#6e56cf"]


def humanize(code_id: str) -> str:
    return code_id.replace("_", " ").title()


def display_row(title: str, status_text: str = "", status_class: str = "", aux: str = "") -> str:
    right = ""
    if status_text:
        right = f'<span class="display-status {status_class}">{status_text}</span>'
    elif aux:
        right = f'<span class="display-aux">{aux}</span>'
    return (
        f'<div class="display-row"><span class="display-title">{title}</span>{right}</div>'
    )


def reason_list(codes, contributions=None) -> str:
    """codes: list[ReasonCode]; contributions: dict feature->contribution
    used to compute each contribution-sourced code's share of the total
    positive contribution mass. Rule codes lead with RULE instead."""
    rows = []
    shares = {}
    if contributions:
        positive = {f: c for f, c in contributions.items() if c > 0}
        total = sum(positive.values()) or 1.0
        shares = {f: c / total for f, c in positive.items()}
    for i, c in enumerate(codes):
        dot = DOT_COLORS[i % len(DOT_COLORS)]
        if c.source == "rule":
            lead = "RULE"
        else:
            # find the share for the feature(s) this code maps to via rank order fallback
            lead = getattr(c, "_share_label", "")
        rows.append(
            f'<div class="reason-row">'
            f'<span class="reason-share">{lead}</span>'
            f'<span class="reason-main"><span class="reason-name">{humanize(c.code_id)}</span>'
            f'<span class="reason-consumer">{c.consumer_text}</span>'
            f'<span class="reason-codechip">{c.code_id}</span></span>'
            f'<span class="reason-dot" style="--dot:{dot}"></span>'
            f"</div>"
        )
    return f'<div class="reason-list">{"".join(rows)}</div>'


def timeline(items) -> str:
    """items: list of (title, meta, active: bool)."""
    rows = []
    for title, meta, active in items:
        cls = " active" if active else ""
        rows.append(
            f'<div class="tl-item"><span class="tl-bullet{cls}"></span>'
            f'<span><span class="tl-title{cls}">{title}</span>'
            f'<div class="tl-meta">{meta}</div></span></div>'
        )
    return f'<div class="timeline">{"".join(rows)}</div>'
