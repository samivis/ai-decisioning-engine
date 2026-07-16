"""Visual layer: tinted canvas, floating cards, two fonts total.

Type system, deliberately strict:
  * SANS (system SF/Segoe stack) for every word on the page, including
    Streamlit widgets, which otherwise leak their own default font
  * MONO only for machine identifiers and numbers: decision ids, hashes,
    code ids, shares, table values

Meaning over decoration: the element beside each reason is a share bar
whose fill is that code's slice of the model's positive contribution
mass (RULE rows show a full dark bar because a fired hard rule is
categorical, not proportional). Tables are hand-rendered so values are
mono, right-aligned, and there is no phantom index column.
"""

SANS = '"Geist", -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
MONO = '"Geist Mono", "SF Mono", ui-monospace, Menlo, Consolas, monospace'

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500;600&display=swap');
/* ---- chrome removal + canvas ---- */
#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
[data-testid="stAppViewContainer"] {{ background: #dfe0f5; }}
.block-container {{ padding-top: 2.4rem; padding-bottom: 3rem; max-width: 1220px; }}

/* ---- ONE sans everywhere (kill Streamlit's font leaks); mono opt-in ---- */
[data-testid="stAppViewContainer"] p,
[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] input,
[data-testid="stAppViewContainer"] button,
[data-testid="stAppViewContainer"] li,
[data-testid="stAppViewContainer"] div[data-baseweb] {{
  font-family: {SANS};
}}
[data-testid="stAppViewContainer"] [data-testid="stIconMaterial"],
[data-testid="stAppViewContainer"] [class*="material-symbols"] {{
  font-family: "Material Symbols Rounded" !important;
}}
html, body {{ font-family: {SANS}; color: #23262e; -webkit-font-smoothing: antialiased; }}

/* ---- masthead: big, confident ---- */
h1 {{
  font-family: {SANS} !important;
  font-size: 1.9rem !important;
  font-weight: 750 !important;
  letter-spacing: -0.035em !important;
  color: #17191f !important;
  text-align: left;
  padding-bottom: 0 !important;
}}
h1::before {{
  content: "REFERENCE IMPLEMENTATION | ADVERSE ACTION FIRST";
  display: block;
  font-family: {MONO};
  font-size: 0.66rem; font-weight: 500;
  letter-spacing: 0.28em; color: #6e56cf;
  margin-bottom: 0.5rem;
}}
[data-testid="stCaptionContainer"] p {{ color: #8a8fa3; font-size: 0.84rem; line-height: 1.6; }}

/* ---- section display rows ---- */
.display-row {{
  display: flex; align-items: baseline; justify-content: space-between; gap: 1rem;
  border-bottom: 2px solid #17191f; padding: 0.3rem 0 0.65rem;
  margin: 0.7rem 0 1.15rem;
}}
.display-title {{
  font-family: {SANS};
  font-size: 1.7rem; font-weight: 700; letter-spacing: -0.025em; color: #17191f;
  white-space: nowrap;
}}
.display-status {{
  font-family: {SANS};
  font-size: 1.15rem; font-weight: 700; letter-spacing: 0.08em;
}}
.status-decline {{ color: #b3261e; }}
.status-approve {{ color: #1d7a4f; }}
.status-review  {{ color: #a06a00; }}
.display-aux {{
  font-family: {MONO};
  font-size: 0.78rem; letter-spacing: 0.1em; color: #6e56cf; font-weight: 600;
}}

/* ---- micro labels (mono, tracked) ---- */
.micro {{
  font-family: {MONO};
  font-size: 0.68rem; letter-spacing: 0.2em; text-transform: uppercase;
  color: #8a8fa3; margin: 0.2rem 0 0.7rem;
}}

/* ---- top-level columns are the two cards ---- */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
  background: #ffffff;
  border-radius: 22px;
  padding: 1.7rem 1.8rem 2rem;
  box-shadow: 0 18px 45px rgba(52,54,94,0.10), 0 2px 6px rgba(52,54,94,0.05);
}}
[data-testid="stColumn"] [data-testid="stColumn"] {{
  background: transparent !important; box-shadow: none !important;
  padding: 0 !important; border-radius: 0 !important;
}}

/* ---- reason rows: share% | name + approved text | share bar ---- */
.reason-list {{ margin: 0.2rem 0 1.3rem; }}
.reason-row {{
  display: flex; align-items: center; gap: 1.2rem;
  padding: 1rem 0.2rem;
  border-bottom: 1px solid #eef0f5;
}}
.reason-row:last-child {{ border-bottom: none; }}
.reason-share {{
  font-family: {MONO};
  font-size: 0.95rem; font-weight: 600; color: #17191f;
  min-width: 3.4rem; text-align: right;
}}
.reason-main {{ flex: 1 1 14ch; min-width: 12ch; }}
.reason-name {{ display: block; font-size: 1.02rem; font-weight: 650; color: #17191f; }}
.reason-consumer {{ display: block; font-size: 0.85rem; color: #7d8294; margin-top: 0.2rem; line-height: 1.45; }}
.reason-codechip {{
  font-family: {MONO};
  font-size: 0.64rem; letter-spacing: 0.05em; color: #a3a8ba; margin-top: 0.3rem; display: block;
}}
/* the share bar: fill = this code's slice of positive contribution mass */
.reason-bar {{
  display: inline-block; flex: none; width: 92px; height: 8px; border-radius: 999px;
  background: #eef0f8; overflow: hidden; position: relative;
}}
.reason-bar > i {{
  display: block; height: 100%; border-radius: 999px;
  background: #6e56cf; width: var(--w, 0%);
}}
.reason-bar.rule > i {{ background: #17191f; width: 100%; }}
.reason-barlabel {{
  font-family: {MONO}; font-size: 0.62rem; letter-spacing: 0.14em;
  color: #a3a8ba; display: block; text-align: right; margin-top: 0.3rem;
}}

/* ---- timeline ---- */
.timeline {{ margin: 0.4rem 0 1.2rem; }}
.tl-item {{ display: flex; gap: 0.85rem; padding: 0.5rem 0; }}
.tl-bullet {{ width: 9px; height: 9px; border-radius: 50%; margin-top: 0.4rem; flex: none; background: #c9ccdb; }}
.tl-bullet.active {{ background: #6e56cf; box-shadow: 0 0 0 3px rgba(110,86,207,0.22); }}
.tl-title {{ font-size: 0.94rem; font-weight: 650; color: #23262e; }}
.tl-title.active {{ color: #6e56cf; }}
.tl-meta {{ font-family: {MONO}; font-size: 0.72rem; color: #9aa0b2; margin-top: 0.15rem; }}

/* ---- info cards ---- */
.logic-card {{ background: #f7f7fd; border-radius: 16px; padding: 1.2rem 1.3rem 1.35rem; margin: 0.6rem 0 1rem; }}
.logic-card p {{ font-size: 0.9rem; color: #4a4e5c; line-height: 1.65; margin: 0.5rem 0 0; }}
.replay-note {{ font-size: 0.93rem; color: #3d414d; line-height: 1.75; }}

/* ---- hand-rendered data tables (mono values, no phantom column) ---- */
.dtable-wrap {{ overflow-x: auto; margin: 0.4rem 0 1.1rem; border-radius: 10px; }}
.dtable {{ width: 100%; min-width: 480px; border-collapse: collapse; }}
.dtable th {{
  font-family: {MONO}; font-size: 0.64rem; letter-spacing: 0.16em; text-transform: uppercase;
  color: #8a8fa3; text-align: left; font-weight: 500;
  padding: 0.45rem 0.75rem; border-bottom: 1px solid #e4e6ef; background: #f7f7fd;
}}
.dtable th.num, .dtable td.num {{ text-align: right; }}
.dtable td {{
  font-family: {SANS}; font-size: 0.86rem; color: #23262e;
  padding: 0.5rem 0.75rem; border-bottom: 1px solid #f0f1f5;
  overflow-wrap: break-word; vertical-align: top;
}}
.dtable td.num, .dtable td.mono {{ font-family: {MONO}; font-size: 0.8rem; color: #3d414d; }}
.dtable td.mono {{ white-space: nowrap; overflow-wrap: normal; }}
.dtable tr:last-child td {{ border-bottom: none; }}
.dtable .fired-yes {{ color: #b3261e; font-weight: 650; white-space: nowrap; }}
.dtable .fired-no {{ color: #a3a8ba; }}
.rt-name {{ display: block; font-weight: 600; color: #23262e; }}
.rt-id {{ display: block; font-family: {MONO}; font-size: 0.66rem; color: #a3a8ba; margin-top: 0.2rem; }}
.rt-would {{ display: block; font-size: 0.72rem; color: #a3a8ba; margin-top: 0.15rem; }}
.rt-desc {{ display: block; line-height: 1.5; }}
.rt-expr {{ display: block; font-family: {MONO}; font-size: 0.68rem; color: #a3a8ba; margin-top: 0.35rem; overflow-wrap: anywhere; }}
.dtable.rt th:nth-child(1) {{ width: 24%; }}
.dtable.rt th:nth-child(2) {{ width: 20%; }}

/* ---- controls ---- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {{
  border-radius: 999px; border: none; background: #17191f; color: #ffffff;
  padding: 0.55rem 1.4rem; font-weight: 600; font-size: 0.9rem;
}}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {{ background: #34363e; color: #fff; }}
.stButton > button[kind="secondary"] {{ background: #ffffff; color: #23262e; border: 1.5px solid #d5d7e4; }}
.stButton > button[kind="secondary"]:hover {{ border-color: #a9adc0; background: #f7f7fd; }}
[data-testid="stForm"] {{ border: none; padding: 0; }}
[data-baseweb="select"] > div {{ border-radius: 12px !important; border-color: #e3e5ee !important; background: #f7f7fd !important; }}
.stRadio label p {{ font-size: 0.86rem; }}
[data-testid="stWidgetLabel"] p {{ font-size: 0.8rem; font-weight: 600; color: #4a4e5c; }}

/* ---- chips ---- */
code {{
  font-family: {MONO};
  font-size: 0.76em;
  background: #f0f1f8 !important; color: #4a4e5c !important;
  border: none; border-radius: 6px; padding: 0.14em 0.5em;
}}

/* ---- tabs ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid #ecedf2; }}
[data-testid="stTabs"] [data-baseweb="tab"] {{ font-size: 0.88rem; color: #8a8fa3; padding-bottom: 0.6rem; }}
[data-testid="stTabs"] [aria-selected="true"] {{ color: #17191f !important; font-weight: 650; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color: #17191f; }}

/* ---- notice text blocks ---- */
[data-testid="stText"] {{
  background: #f7f7fd; border: none; border-radius: 16px;
  padding: 1.25rem 1.4rem;
  font-family: {MONO};
  font-size: 0.78rem; line-height: 1.7; color: #4a4e5c; white-space: pre-wrap;
}}

.prose-block {{
  background: #f7f7fd; border-radius: 16px; padding: 1.25rem 1.4rem; margin-bottom: 0.6rem;
}}
.prose-block p {{ font-size: 0.88rem; line-height: 1.7; color: #4a4e5c; margin: 0 0 0.8rem; }}
.prose-block p:last-child {{ margin-bottom: 0; }}
.prose-block strong {{ color: #23262e; font-weight: 650; }}

[data-testid="stAlert"] {{ border-radius: 14px; border: none; }}
[data-testid="stExpander"] {{ border: 1px solid #eef0f5 !important; border-radius: 16px !important; background: #ffffff; }}
[data-testid="stExpander"] summary {{ font-size: 0.86rem; color: #6d7286; }}

/* ---- narrow windows: tighten, never spill ---- */
@media (max-width: 1000px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > div > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
    padding: 1.2rem 1.1rem 1.4rem;
  }}
  .dtable {{ min-width: 420px; }}
  .dtable td, .dtable th {{ padding: 0.4rem 0.5rem; font-size: 0.78rem; }}
  .display-title {{ font-size: 1.35rem; white-space: normal; }}
  .reason-bar {{ width: 64px; }}
}}
</style>
"""


def humanize(code_id: str) -> str:
    return code_id.replace("_", " ").title()


def display_row(title: str, status_text: str = "", status_class: str = "", aux: str = "") -> str:
    right = ""
    if status_text:
        right = f'<span class="display-status {status_class}">{status_text}</span>'
    elif aux:
        right = f'<span class="display-aux">{aux}</span>'
    return f'<div class="display-row"><span class="display-title">{title}</span>{right}</div>'


def reason_list(codes) -> str:
    """codes: list[ReasonCode], optionally carrying _share (0..1) set by the
    app for contribution-sourced codes. The right-hand bar VISUALIZES that
    share; rule rows render a full dark bar labeled HARD RULE because a
    fired policy rule is categorical, not proportional."""
    rows = []
    for c in codes:
        share = getattr(c, "_share", None)
        if c.source == "rule":
            lead = "RULE"
            bar = '<span><span class="reason-bar rule"><i></i></span><span class="reason-barlabel">HARD RULE</span></span>'
        else:
            pct = round((share or 0) * 100)
            lead = f"{pct}%"
            bar = (
                f'<span><span class="reason-bar"><i style="--w:{pct}%"></i></span>'
                f'<span class="reason-barlabel">OF MODEL SIGNAL</span></span>'
            )
        rows.append(
            f'<div class="reason-row">'
            f'<span class="reason-share">{lead}</span>'
            f'<span class="reason-main"><span class="reason-name">{humanize(c.code_id)}</span>'
            f'<span class="reason-consumer">{c.consumer_text}</span>'
            f'<span class="reason-codechip">{c.code_id}</span></span>'
            f"{bar}"
            f"</div>"
        )
    return f'<div class="reason-list">{"".join(rows)}</div>'


def prose_block(text: str) -> str:
    """Render LLM prose (with markdown bold) as a styled block: asterisk
    pairs become real bold, newlines become breaks. Escapes HTML first."""
    import html as _html
    import re

    t = _html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t, flags=re.S)
    t = t.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return f'<div class="prose-block"><p>{t}</p></div>'


def timeline(items) -> str:
    rows = []
    for title, meta, active in items:
        cls = " active" if active else ""
        rows.append(
            f'<div class="tl-item"><span class="tl-bullet{cls}"></span>'
            f'<span><span class="tl-title{cls}">{title}</span>'
            f'<div class="tl-meta">{meta}</div></span></div>'
        )
    return f'<div class="timeline">{"".join(rows)}</div>'


def contributions_table(contributions) -> str:
    rows = "".join(
        f'<tr><td>{humanize(c.feature)}</td>'
        f'<td class="num">{c.value:,.3f}</td>'
        f'<td class="num">{c.contribution:+.4f}</td></tr>'
        for c in contributions
    )
    return (
        '<div class="dtable-wrap"><table class="dtable"><thead><tr>'
        "<th>Feature</th><th class=\"num\">Standardized value</th><th class=\"num\">Contribution</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def rule_trace_table(trace, rule_effects=None) -> str:
    """Three readable columns: humanized rule name (mono id beneath),
    a single outcome cell (FIRED -> DECLINE, or pass with the would-be
    effect), and the plain-language reason with the machine expression
    tucked underneath in small mono."""
    import re

    rule_effects = rule_effects or {}
    rows = ""
    for t in trace:
        effect = (t.effect or rule_effects.get(t.rule_id, "")).strip()
        name = f'<span class="rt-name">{humanize(t.rule_id)}</span><span class="rt-id">{t.rule_id}</span>'
        if t.fired:
            outcome = f'<span class="fired-yes">FIRED &rarr; {effect.upper()}</span>'
        else:
            outcome = f'<span class="fired-no">pass</span><span class="rt-would">would {effect}</span>'
        m = re.match(r"^(.*?)\s*->\s*(True|False)\s*\((.*)\)\s*$", t.detail, flags=re.S)
        if m:
            expr, result, desc = m.groups()
            detail = (f'<span class="rt-desc">{desc}</span>'
                      f'<span class="rt-expr">{expr} evaluated {result.lower()}</span>')
        else:
            detail = f'<span class="rt-desc">{t.detail}</span>'
        rows += f"<tr><td>{name}</td><td>{outcome}</td><td>{detail}</td></tr>"
    return (
        '<div class="dtable-wrap"><table class="dtable rt"><thead><tr>'
        "<th>Rule</th><th>Outcome</th><th>Why</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )
