"""Visual layer for the demo: quiet, editorial, hairline-bordered.

Design intent (kept deliberately restrained): white page, a narrow
measure, small tracked uppercase section labels, cards with 1px borders
instead of shadows and color, monospace chips for identifiers. The
decision banner is the only moment of color on the page.
"""

CSS = """
<style>
/* ---- chrome removal ---- */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 3.5rem; padding-bottom: 4rem; max-width: 1160px; }

/* ---- type ---- */
html, body, [class*="css"] {
  font-family: -apple-system, "SF Pro Text", "Segoe UI", Inter, Roboto, sans-serif;
  color: #1a1d21;
  -webkit-font-smoothing: antialiased;
}
h1 {
  font-size: 2.35rem !important;
  font-weight: 650 !important;
  letter-spacing: -0.035em !important;
  line-height: 1.12 !important;
  color: #111418 !important;
  max-width: 22ch;
}
h3, .stSubheader h3 {
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.14em !important;
  text-transform: uppercase !important;
  color: #8a9099 !important;
  border-bottom: 1px solid #ececee;
  padding-bottom: 0.55rem;
  margin-top: 0.4rem !important;
}
[data-testid="stCaptionContainer"] p { color: #8a9099; font-size: 0.83rem; line-height: 1.55; }

/* ---- cards: banners, tables, expanders ---- */
[data-testid="stAlert"] {
  border-radius: 12px;
  border: 1px solid #e7e8ea;
  box-shadow: 0 1px 2px rgba(17,20,24,0.04);
}
[data-testid="stExpander"] {
  border: 1px solid #e7e8ea !important;
  border-radius: 12px !important;
  background: #ffffff;
}
[data-testid="stExpander"] summary { font-size: 0.85rem; color: #5c636b; }
[data-testid="stTable"] {
  border: 1px solid #e7e8ea;
  border-radius: 12px;
  overflow: hidden;
  font-size: 0.85rem;
}
[data-testid="stTable"] thead th {
  background: #fafafa;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.68rem;
  color: #8a9099;
}

/* ---- controls ---- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 10px;
  border: 1px solid #111418;
  padding: 0.45rem 1.15rem;
  font-weight: 550;
  font-size: 0.88rem;
  transition: background 120ms ease;
}
.stButton > button[kind="secondary"] {
  border: 1px solid #d9dbde;
  background: #ffffff;
  color: #1a1d21;
}
.stButton > button[kind="secondary"]:hover { border-color: #9aa0a8; background: #fafafa; }
[data-testid="stForm"] {
  border: 1px solid #e7e8ea;
  border-radius: 12px;
  padding: 1.35rem 1.35rem 1.1rem;
  background: #ffffff;
}
[data-baseweb="select"] > div { border-radius: 10px !important; border-color: #d9dbde !important; }

/* ---- tabs ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 1.6rem; border-bottom: 1px solid #ececee; }
[data-testid="stTabs"] [data-baseweb="tab"] {
  font-size: 0.85rem;
  color: #8a9099;
  padding-bottom: 0.6rem;
}
[data-testid="stTabs"] [aria-selected="true"] { color: #111418 !important; font-weight: 600; }
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: #111418; }

/* ---- code / chips ---- */
code {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.78em;
  background: #f4f5f6 !important;
  color: #43484e !important;
  border: 1px solid #e7e8ea;
  border-radius: 6px;
  padding: 0.1em 0.45em;
}
.stMarkdown pre, [data-testid="stText"] {
  background: #fafafa;
  border: 1px solid #e7e8ea;
  border-radius: 12px;
  padding: 1.1rem 1.25rem;
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.8rem;
  line-height: 1.65;
  color: #43484e;
  white-space: pre-wrap;
}

/* ---- ranked reason list ---- */
.reason-row {
  display: flex; align-items: baseline; gap: 0.8rem;
  padding: 0.7rem 0.95rem;
  border: 1px solid #e7e8ea; border-radius: 10px;
  margin-bottom: 0.45rem; background: #ffffff;
}
.reason-rank {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.72rem; color: #8a9099; min-width: 1.1rem;
}
.reason-id {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 0.72rem; letter-spacing: 0.02em;
  background: #f4f5f6; border: 1px solid #e7e8ea; border-radius: 6px;
  padding: 0.12em 0.5em; color: #43484e; white-space: nowrap;
}
.reason-text { font-size: 0.92rem; color: #1a1d21; }
.reason-src { font-size: 0.7rem; color: #b0b5bc; text-transform: uppercase; letter-spacing: 0.1em; margin-left: auto; }
</style>
"""


def reason_row(rank: int, code_id: str, text: str, source: str) -> str:
    return (
        f'<div class="reason-row"><span class="reason-rank">{rank:02d}</span>'
        f'<span class="reason-id">{code_id}</span>'
        f'<span class="reason-text">{text}</span>'
        f'<span class="reason-src">{source}</span></div>'
    )
