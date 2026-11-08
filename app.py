import re
import streamlit as st
import pandas as pd
import plotly.express as px

from database import init_db, get_connection

from modules.employees import (
    add_employee,
    get_all_employees,
    delete_employee,
    update_employee,
)

from modules.tasks import (
    add_task,
    get_all_tasks,
    delete_task,
    update_task_status,
)

from modules.allocation import get_recommendations, assign_task

from modules.disturbances import (
    report_unavailability,
    report_workload_overload,
    report_task_delay,
    get_all_disturbances,
)

from modules.reallocation import (
    get_affected_assignments,
    get_replacement_recommendations,
    approve_reallocation,
)

from modules.prediction import MODEL_PATH, predict_completion_time
from modules.modeling import model_version
from modules.prediction_history import get_prediction_records, record_prediction
from modules.health import check_health
from modules.extras import (
    compare_strategies,
    create_user,
    delete_user,
    get_audit_log,
    get_all_skill_levels,
    list_users,
    log_action,
    update_task_fields,
)
from modules.auth import authenticate_user, initialize_auth
from modules.extras import change_password


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Human-Aware Task Allocation",
    page_icon="📊",
    layout="wide",
)

init_db()
initialize_auth()


# ============================================================
# THEME
# ============================================================

INK = "#0B1F2E"
LABEL = "#2E4452"
MUTED = "#617684"
BRAND = "#0F766E"
CORAL = "#E4572E"
BLUE = "#2563EB"
GREEN = "#16A34A"
AMBER = "#D99100"
VIOLET = "#7C3AED"
SLATE = "#8A97A6"

STATUS_COLORS = {
    "Pending": SLATE,
    "In Progress": BLUE,
    "Completed": GREEN,
    "Delayed": CORAL,
}

CHART_SEQUENCE = [BRAND, CORAL, BLUE, AMBER, VIOLET, SLATE]


# ============================================================
# DISPLAY HELPERS
# These change only what the user sees. Actual database IDs
# continue to be used for all database operations.
# ============================================================

def employee_display_options(employees):
    """Map sequential employee labels to complete employee records."""
    return {
        f"{number} - {employee['name']}": employee
        for number, employee in enumerate(employees, start=1)
    }


def employee_id_display_options(employees):
    """Map sequential employee labels to actual employee database IDs."""
    return {
        f"{number} - {employee['name']}": employee["employee_id"]
        for number, employee in enumerate(employees, start=1)
    }


def task_display_options(tasks):
    """Map sequential task labels to actual task database IDs."""
    return {
        f"Task {number} - {task['title']}": task["task_id"]
        for number, task in enumerate(tasks, start=1)
    }


def task_record_display_options(tasks):
    """Map sequential task labels to complete task records."""
    return {
        f"Task {number} - {task['title']}": task
        for number, task in enumerate(tasks, start=1)
    }


def employee_display_dataframe(employees):
    """Hide internal employee IDs and show sequential row numbers."""
    rows = []
    for number, employee in enumerate(employees, start=1):
        row = dict(employee)
        row.pop("employee_id", None)
        rows.append({"No.": number, **row})
    return pd.DataFrame(rows)


def display_dataframe(records, hidden_columns=None):
    """Hide selected internal IDs and add sequential display numbering."""
    rows = [dict(record) for record in records]
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    hidden_columns = set(hidden_columns or [])

    df = df.drop(
        columns=[
            column for column in hidden_columns
            if column in df.columns
        ],
        errors="ignore",
    )

    # Avoid adding a second number column if one already exists.
    if "No." in df.columns:
        df = df.drop(columns=["No."])

    df.insert(0, "No.", range(1, len(df) + 1))
    return df


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');

    :root {
        --ink: #0B1F2E;
        --body: #2E4452;
        --muted: #617684;
        --line: #E3DED3;
        --surface: #FFFFFF;
        --canvas: #F7F5F0;
        --brand: #0F766E;
        --brand-hover: #0B5F59;
        --brand-soft: #DDF1EE;
        --coral: #E4572E;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        color: var(--ink);
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background: var(--canvas) !important;
        color: var(--ink) !important;
    }

    [data-testid="stHeader"] {
        background: rgba(247,245,240,.96) !important;
    }

    .block-container {
        padding-top: 4.5rem;
        padding-bottom: 3rem;
        max-width: 1420px;
    }

    h1, h2, h3, h4 {
        font-family: 'Manrope', sans-serif !important;
        color: var(--ink) !important;
        letter-spacing: -.025em;
    }

    h1 { font-weight: 800 !important; font-size: 2rem !important; }
    h2 { font-size: 1.35rem !important; font-weight: 700 !important; }
    h3 { font-size: 1.05rem !important; font-weight: 700 !important; }

    p, li, [data-testid="stMarkdownContainer"] { color: var(--body); }

    small, .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--muted) !important;
    }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0B1F2E 0%, #0E2837 100%) !important;
        border-right: 1px solid #12303F;
    }

    [data-testid="stSidebar"] * { color: #CFE3EA; }
    [data-testid="stSidebar"] .brand-mark { color: #FFFFFF !important; }
    [data-testid="stSidebar"] .brand-mark span { color: #2DD4BF !important; }
    [data-testid="stSidebar"] .small-muted { color: #7FA3B3 !important; }
    [data-testid="stSidebar"] hr { border-color: #1D3F50 !important; }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        color: #7FA3B3 !important;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .1em;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: .55rem .7rem;
        border-radius: 8px;
        transition: background .2s ease, transform .2s ease;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label * {
        color: #CFE3EA !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background: #14394D;
        border-left: 3px solid #2DD4BF;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(45,212,191,.10);
        transform: translateX(3px);
    }

    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: 1px solid #2A4A5E !important;
        color: #E6F2F5 !important;
    }

    /* LABELS */
    [data-testid="stMain"] [data-testid="stWidgetLabel"],
    [data-testid="stMain"] [data-testid="stWidgetLabel"] *,
    .stMain label {
        color: var(--body) !important;
        opacity: 1 !important;
        font-weight: 600;
    }

    /* INPUTS */
    .stTextInput input, .stNumberInput input, .stTextArea textarea,
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
        background: #FFFFFF !important;
        color: var(--ink) !important;
        -webkit-text-fill-color: var(--ink) !important;
        border: 1px solid #CFC9BC !important;
        border-radius: 8px !important;
        transition: border-color .2s ease, box-shadow .2s ease;
    }

    div[data-baseweb="select"] > div {
        background: #FFFFFF !important;
        color: var(--ink) !important;
        border: 1px solid #CFC9BC !important;
        border-radius: 8px !important;
        transition: border-color .2s ease, box-shadow .2s ease;
    }

    div[data-baseweb="select"] *, [data-baseweb="popover"] *,
    [role="listbox"], [role="option"] {
        color: var(--ink) !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 3px rgba(15,118,110,.10) !important;
    }

    /* METRIC CARDS */
    [data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid var(--line);
        border-left: 5px solid var(--brand);
        padding: 1rem 1.1rem;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(11,31,46,.05);
        transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
    }

    [data-testid="stMetric"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 9px 22px rgba(11,31,46,.10);
        border-color: #B7DCD6;
    }

    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
        color: var(--muted) !important;
        font-size: .8rem;
        font-weight: 700;
    }

    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        color: var(--ink) !important;
        font-family: 'Manrope', sans-serif;
        font-size: 1.75rem;
        font-weight: 800;
    }

    /* FORMS AND EXPANDERS */
    [data-testid="stForm"], [data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: .85rem;
        box-shadow: 0 2px 6px rgba(11,31,46,.05);
        transition: box-shadow .25s ease, border-color .25s ease;
    }

    [data-testid="stForm"]:hover, [data-testid="stExpander"]:hover {
        box-shadow: 0 6px 18px rgba(11,31,46,.07);
        border-color: #D1DCD8;
    }

    /* BUTTONS */
    .stButton > button, .stFormSubmitButton > button {
        border: 1.5px solid var(--brand);
        border-radius: 8px;
        background: #FFFFFF;
        color: var(--brand) !important;
        font-weight: 700;
        padding: .5rem 1.1rem;
        transition: background .22s ease, color .22s ease,
                    border-color .22s ease, transform .18s ease,
                    box-shadow .22s ease;
        box-shadow: 0 2px 4px rgba(11,31,46,.04);
    }

    .stButton > button:hover, .stFormSubmitButton > button:hover {
        color: #FFFFFF !important;
        background: var(--brand);
        transform: translateY(-2px);
        box-shadow: 0 5px 12px rgba(15,118,110,.16);
    }

    .stButton > button:active, .stFormSubmitButton > button:active {
        transform: translateY(0) scale(.98);
    }

    .stButton > button *, .stFormSubmitButton > button * {
        color: inherit !important;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primaryFormSubmit"] {
        background: var(--brand) !important;
        border-color: var(--brand) !important;
        color: #FFFFFF !important;
    }

    /* ALERTS */
    [data-testid="stAlert"] {
        border-radius: 10px;
        animation: pageFadeIn .3s ease-out;
    }

    /* TABLES */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
        background: #FFFFFF !important;
        transition: box-shadow .25s ease, border-color .25s ease;
    }

    [data-testid="stDataFrame"]:hover, [data-testid="stTable"]:hover {
        box-shadow: 0 6px 18px rgba(11,31,46,.07);
        border-color: #CBDAD5;
    }

    /* TEXT STYLES */
    .eyebrow {
        color: var(--coral);
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .page-subtitle {
        color: var(--muted);
        font-size: .95rem;
        margin-top: -.45rem;
        margin-bottom: 1.2rem;
    }

    .brand-mark {
        font-family: 'Manrope', sans-serif;
        font-size: 1.25rem;
        font-weight: 800;
        color: var(--ink);
    }

    .brand-mark span { color: var(--brand); }

    .login-title {
        font-family: 'Manrope', sans-serif;
        font-size: 2.15rem;
        font-weight: 800;
        color: var(--ink);
        margin: 1.2rem 0 .5rem;
    }

    .login-sub {
        color: var(--muted);
        font-size: .98rem;
        line-height: 1.65;
        margin-bottom: 1rem;
    }

    .login-visual {
        min-height: 390px;
        border-radius: 16px;
        padding: 2rem;
        color: #FFFFFF;
        background: linear-gradient(155deg, #0B1F2E 0%, #0F4C57 100%);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .login-visual h2 { color: #FFFFFF !important; font-size: 2rem; }
    .login-visual p { color: #B7D2DA; line-height: 1.7; }
    .login-visual .eyebrow { color: #2DD4BF; }
    .small-muted { color: var(--muted) !important; font-size: .84rem; }

    /* LOGIN FORM CARD */
    [data-testid="stForm"] {
        background: #FFFFFF !important;
        border: 1px solid #E3DED3 !important;
        border-radius: 14px !important;
        padding: 1.1rem !important;
        box-shadow: 0 5px 16px rgba(11,31,46,.05);
    }

    /* PAGE TRANSITION */
    @keyframes pageFadeIn {
        from { opacity: 0; transform: translateY(9px); }
        to { opacity: 1; transform: translateY(0); }
    }

    [data-testid="stMain"] .block-container {
        animation: pageFadeIn .45s ease-out;
    }

    /* CHART CONTAINERS */
    [data-testid="stPlotlyChart"] {
        background: #FFFFFF;
        border: 1px solid #E3DED3;
        border-radius: 12px;
        padding: 8px;
        transition: box-shadow .25s ease, transform .25s ease;
    }

    [data-testid="stPlotlyChart"]:hover {
        box-shadow: 0 7px 20px rgba(11,31,46,.07);
        transform: translateY(-2px);
    }

    [data-testid="stProgressBar"] > div > div {
        transition: width .6s ease;
    }

    hr, [data-testid="stDivider"] {
        border-color: var(--line) !important;
        opacity: .75;
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: .01ms !important;
            transition-duration: .01ms !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CHART THEME
# ============================================================

px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = CHART_SEQUENCE


def apply_chart_theme(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="DM Sans", color=LABEL, size=12),
        title_font=dict(family="Manrope", color=INK, size=15),
        colorway=CHART_SEQUENCE,
        margin=dict(l=16, r=16, t=48, b=16),
    )

    axis_style = dict(
        gridcolor="#EFEBE2",
        linecolor="#D9D3C6",
        tickfont=dict(color=MUTED),
        title_font=dict(color=LABEL),
    )

    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig


# ============================================================
# SKILL PARSING, EXPLANATION AND VALIDATION HELPERS
# ============================================================

def split_skills(text):
    """Turn a skills string into a clean list of skills.

    * If the text contains a comma, semicolon, pipe or new line, only those
      are used as separators, so multi-word skills such as
      "machine learning, sql" stay intact.
    * Otherwise whitespace separates the skills, so "python sql" becomes
      ["python", "sql"].
    Duplicates are removed (case-insensitive) and the first spelling is kept.
    """
    text = str(text or "").strip()
    if re.search(r"[,;|\n]", text):
        parts = re.split(r"[,;|\n]+", text)
    else:
        parts = text.split()

    seen = set()
    skills = []
    for part in parts:
        skill = " ".join(part.split())
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            skills.append(skill)
    return skills


def normalize_skills(text):
    """Canonical storage format: 'Python, SQL' (comma separated)."""
    return ", ".join(split_skills(text))


def skill_set(text):
    return {skill.lower() for skill in split_skills(text)}


def utilization_value(employee):
    capacity = float(employee["max_capacity"] or 0)
    current = float(employee["current_workload"] or 0)
    return current / capacity * 100 if capacity > 0 else 0.0


def explain_match(employee, task):
    """Facts that explain how well an employee fits a task."""
    required = split_skills(task["required_skills"])
    have = skill_set(employee["skills"])
    matched = [s for s in required if s.lower() in have]
    missing = [s for s in required if s.lower() not in have]

    capacity = float(employee["max_capacity"] or 0)
    current = float(employee["current_workload"] or 0)
    hours = float(task["estimated_hours"] or 0)

    return {
        "matched": matched,
        "missing": missing,
        "ratio": len(matched) / len(required) if required else 0.0,
        "before": current / capacity * 100 if capacity > 0 else 0.0,
        "after": (current + hours) / capacity * 100 if capacity > 0 else 0.0,
        "remaining_after": capacity - current - hours,
    }


def allocation_problems(employee, task):
    """Return blockers (must not assign) and warnings (assign with care)."""
    info = explain_match(employee, task)
    name = employee["name"]
    blockers, warnings = [], []

    if employee["availability"] != "Available":
        blockers.append(f"{name} is marked unavailable.")

    if info["ratio"] == 0:
        needed = ", ".join(split_skills(task["required_skills"]))
        blockers.append(
            f"{name} has none of the required skills ({needed})."
        )
    elif info["missing"]:
        warnings.append(
            f"{name} is missing: {', '.join(info['missing'])}."
        )

    if info["after"] > 100:
        blockers.append(
            f"Assigning this task would put {name} at "
            f"{info['after']:.0f}% of capacity."
        )
    elif info["after"] >= 90:
        warnings.append(
            f"{name} would be at {info['after']:.0f}% of capacity "
            "after this task."
        )

    return {"blockers": blockers, "warnings": warnings, "info": info}


def explanation_text(employee, task):
    info = explain_match(employee, task)
    total = len(info["matched"]) + len(info["missing"])
    lines = []

    if total:
        skill_line = (
            f"- **Skills:** covers {len(info['matched'])} of {total} "
            "required skills"
        )
        if info["matched"]:
            skill_line += " (" + ", ".join(info["matched"]) + ")"
        if info["missing"]:
            skill_line += "; missing " + ", ".join(info["missing"])
        lines.append(skill_line + ".")

    lines.append(
        f"- **Workload:** {info['before']:.0f}% of capacity now, "
        f"{info['after']:.0f}% after this task "
        f"({max(info['remaining_after'], 0):.1f} h/week left)."
    )
    lines.append(
        f"- **Experience:** {float(employee['experience_years'] or 0):g} "
        f"years; performance factor "
        f"{float(employee['historical_performance'] or 1.0):.2f}."
    )
    return f"**Why {employee['name']}?**\n\n" + "\n".join(lines)


def explanation_rows(recommendations, task, employees_by_id):
    rows = []
    for rank, recommendation in enumerate(recommendations, start=1):
        employee = employees_by_id.get(recommendation["employee_id"])
        if employee is None:
            continue

        info = explain_match(employee, task)
        total = len(info["matched"]) + len(info["missing"])

        try:
            score = recommendation["total_score"]
        except (KeyError, IndexError):
            score = None

        rows.append({
            "Rank": rank,
            "Employee": employee["name"],
            "Skills matched": f"{len(info['matched'])} of {total}",
            "Missing skills": ", ".join(info["missing"]) or "None",
            "Workload now": f"{info['before']:.0f}%",
            "After assignment": f"{info['after']:.0f}%",
            "Experience (years)": float(employee["experience_years"] or 0),
            "Performance factor": float(
                employee["historical_performance"] or 1.0
            ),
            "Model score": score,
            "_before": info["before"],
            "_after": info["after"],
        })
    return rows


UTILIZATION_COLORS = {
    "Over 100%": CORAL,
    "80-100%": AMBER,
    "50-80%": BRAND,
    "Under 50%": SLATE,
}


def utilization_band(value):
    if value > 100:
        return "Over 100%"
    if value >= 80:
        return "80-100%"
    if value >= 50:
        return "50-80%"
    return "Under 50%"


def utilization_figure(rows, limit=None, height=None):
    """Horizontal bars of capacity used, coloured by load band."""
    df = pd.DataFrame(rows).sort_values("Utilization", ascending=False)
    if limit:
        df = df.head(limit)
    df["Band"] = df["Utilization"].apply(utilization_band)

    fig = px.bar(
        df,
        x="Utilization",
        y="Employee",
        orientation="h",
        color="Band",
        color_discrete_map=UTILIZATION_COLORS,
        category_orders={"Band": list(UTILIZATION_COLORS)},
        text=df["Utilization"].map(lambda value: f"{value:.0f}%"),
    )
    apply_chart_theme(fig)
    fig.add_vline(x=100, line_dash="dash", line_color=INK, opacity=0.45)
    fig.update_layout(
        height=height or max(260, 34 * len(df) + 90),
        legend_title_text="",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0),
        margin=dict(l=16, r=16, t=24, b=80),
        xaxis_title=None,
        yaxis_title=None,
    )
    fig.update_xaxes(range=[0, max(110, float(df["Utilization"].max()) * 1.15)])
    fig.update_yaxes(autorange="reversed")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


def workload_impact_figure(rows):
    """Workload now vs after taking the task, per recommended employee."""
    data = []
    for row in rows:
        data.append({"Employee": row["Employee"], "When": "Now",
                     "Utilization": row["_before"]})
        data.append({"Employee": row["Employee"], "When": "After assignment",
                     "Utilization": row["_after"]})

    df = pd.DataFrame(data)
    fig = px.bar(
        df,
        x="Utilization",
        y="Employee",
        color="When",
        orientation="h",
        barmode="group",
        color_discrete_map={"Now": SLATE, "After assignment": BRAND},
    )
    apply_chart_theme(fig)
    fig.add_vline(x=100, line_dash="dash", line_color=INK, opacity=0.45)
    fig.update_layout(
        height=max(240, 60 * len(rows) + 90),
        legend_title_text="",
        xaxis_title="Capacity used (%)",
        yaxis_title=None,
    )
    fig.update_xaxes(range=[0, max(110, float(df["Utilization"].max()) * 1.15)])
    fig.update_yaxes(autorange="reversed")
    return fig


# ============================================================
# LOGIN
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.authenticated:
    left, right = st.columns(
        [1.05, 0.95],
        gap="large",
        vertical_alignment="center",
    )

    with left:
        st.markdown(
            '<div class="login-visual">'
            '<div>'
            '<div class="eyebrow">WORKFORCE OPERATIONS</div>'
            '<h2 style="margin-top:22px">A clearer way to<br>coordinate work.</h2>'
            '<p>Bring employee skills, availability and workload into one workspace. '
            'Make informed allocation decisions and respond to changes with confidence.</p>'
            '</div>'
            '<div>'
            '<div style="font-weight:700;color:#FFFFFF">Plan &nbsp;·&nbsp; Allocate &nbsp;·&nbsp; Adapt</div>'
            '<div style="margin-top:8px;font-size:.84rem;color:#8FB4C0">'
            'Human-aware task allocation workspace</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            '<div class="eyebrow">MANAGER WORKSPACE</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="login-title">Welcome back.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="login-sub">Sign in to manage your team, tasks and allocation decisions.</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button(
                "Sign in",
                use_container_width=True,
                type="primary",
            )

        if login_clicked:
            identity = authenticate_user(username, password)
            if identity:
                st.session_state.authenticated = True
                st.session_state.user = identity
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    st.stop()


# Require the seeded account to choose a real password before using the app.
if st.session_state.user and st.session_state.user.get("must_change"):
    st.title("Choose a new password")
    st.write("Your account is using its initial password. Choose a new password to continue.")
    with st.form("change_password_form"):
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        change_clicked = st.form_submit_button("Save password", type="primary")

    if change_clicked:
        if new_password != confirm_password:
            st.error("The passwords do not match.")
        else:
            changed, message = change_password(
                st.session_state.user["username"], new_password
            )
            if changed:
                st.session_state.user["must_change"] = False
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    '<div class="brand-mark">WORK<span>FLOW</span></div>'
    '<div class="small-muted">HUMAN-AWARE TASK ALLOCATION</div>',
    unsafe_allow_html=True,
)

health = check_health(MODEL_PATH)
if health["ready"]:
    st.sidebar.caption("System status: ready")
else:
    missing = [name for name, available in health.items() if name != "ready" and not available]
    st.sidebar.warning(f"System check: unavailable {', '.join(missing)}")

st.sidebar.divider()

st.sidebar.markdown(
    f"<div class='small-muted'>SIGNED IN AS</div>"
    f"<div style='font-weight:700;margin-top:3px'>"
    f"{st.session_state.get('user', {}).get('username', 'Manager')}</div>",
    unsafe_allow_html=True,
)

if st.sidebar.button("Log out", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.pop("user", None)
    st.rerun()

st.sidebar.divider()

available_pages = [
    "Dashboard",
    "Completion-Time Prediction",
    "Analytics & Performance Evaluation",
]
if st.session_state.get("user", {}).get("role") == "manager":
    available_pages[1:1] = [
        "Employee Management",
        "Task Management",
        "Initial Task Allocation",
        "Disturbance Management",
        "Dynamic Reallocation",
        "User & Audit Management",
    ]

page = st.sidebar.radio(
    "WORKSPACE",
    available_pages,
)


# ============================================================
# DASHBOARD
# ============================================================

if page == "User & Audit Management":
    st.title("User & Audit Management")
    st.write("Create manager or viewer accounts and review recorded system actions.")

    st.subheader("Current Users")
    users = list_users()
    if users:
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)

    st.subheader("Create User")
    with st.form("create_user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Temporary password", type="password")
        new_role = st.selectbox("Role", ["viewer", "manager"])
        create_clicked = st.form_submit_button("Create User", type="primary")
    if create_clicked:
        created, message = create_user(new_username, new_password, new_role)
        if created:
            log_action(
                st.session_state["user"]["username"],
                "user_created",
                f"username={new_username.strip()} role={new_role}",
            )
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.subheader("Delete User")
    deletable = [user["username"] for user in users if user["username"] != st.session_state["user"]["username"]]
    if deletable:
        delete_username = st.selectbox("Select user", deletable)
        if st.button("Delete Selected User"):
            deleted, message = delete_user(delete_username)
            if deleted:
                log_action(
                    st.session_state["user"]["username"],
                    "user_deleted",
                    f"username={delete_username}",
                )
                st.success(message)
                st.rerun()
            else:
                st.error(message)
    else:
        st.info("No other users are available to delete.")

    st.subheader("Audit Log")
    audit_log = get_audit_log(limit=200)
    if audit_log:
        st.dataframe(pd.DataFrame(audit_log), use_container_width=True, hide_index=True)
    else:
        st.info("No audit events have been recorded yet.")

elif page == "Dashboard":
    employees = get_all_employees()
    tasks = get_all_tasks()

    active_tasks = sum(t["status"] == "In Progress" for t in tasks)
    pending_tasks = sum(t["status"] == "Pending" for t in tasks)
    completed_tasks = sum(t["status"] == "Completed" for t in tasks)
    delayed_tasks = sum(t["status"] == "Delayed" for t in tasks)

    available_employees = sum(
        e["availability"] == "Available" for e in employees
    )

    st.markdown('<div class="eyebrow">OVERVIEW</div>', unsafe_allow_html=True)
    st.title("Good to see you.")
    st.markdown(
        '<div class="page-subtitle">A live snapshot of your team, workload and project activity.</div>',
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Team members", len(employees))
    m2.metric("Total tasks", len(tasks))
    m3.metric("In progress", active_tasks)
    m4.metric("Completed", completed_tasks)
    m5.metric("Available", available_employees)

    left, right = st.columns([1.35, 1], gap="large")

    with left:
        st.subheader("Task progress")
        status_order = ["Pending", "In Progress", "Completed", "Delayed"]
        status_counts = {
            status: sum(t["status"] == status for t in tasks)
            for status in status_order
        }

        if tasks:
            df = pd.DataFrame({
                "Status": status_order,
                "Tasks": [status_counts[s] for s in status_order],
            })
            fig = px.bar(
                df,
                x="Status",
                y="Tasks",
                color="Status",
                color_discrete_map=STATUS_COLORS,
            )
            apply_chart_theme(fig)
            fig.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Create your first task to see project progress.")

    with right:
        st.subheader("Workload at a glance")
        if employees:
            rows = []
            for employee in employees:
                capacity = float(employee["max_capacity"] or 0)
                current = float(employee["current_workload"] or 0)
                utilization = current / capacity * 100 if capacity else 0
                rows.append({
                    "Employee": employee["name"],
                    "Utilization": round(utilization, 1),
                })

            st.plotly_chart(
                utilization_figure(rows, limit=8, height=300),
                use_container_width=True,
            )
        else:
            st.info("Add employees to view workload distribution.")

    st.divider()
    lower_left, lower_right = st.columns([1.35, 1])

    with lower_left:
        st.subheader("Tasks needing attention")
        attention = [
            dict(t) for t in tasks
            if t["status"] in ("Pending", "Delayed")
        ]

        if attention:
            df = pd.DataFrame(attention)
            columns = [
                column for column in
                ["title", "priority", "status", "estimated_hours"]
                if column in df.columns
            ]
            st.dataframe(
                df[columns],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No pending or delayed tasks.")

    with lower_right:
        st.subheader("Team availability")
        if employees:
            available = sum(
                e["availability"] == "Available" for e in employees
            )
            a, b = st.columns(2)
            a.metric("Available", available)
            b.metric("Unavailable", len(employees) - available)
            st.progress(available / len(employees))
        else:
            st.info("Add employees to view availability.")

    st.divider()
    st.subheader("Workspace shortcuts")
    shortcut_cols = st.columns(4)
    shortcuts = [
        ("Employees", "Maintain employee skills and capacity."),
        ("Tasks", "Create tasks and update their progress."),
        ("Allocation", "Find suitable employees for pending work."),
        ("Reallocation", "Review changes and approve replacements."),
    ]

    for col, (heading, description) in zip(shortcut_cols, shortcuts):
        with col:
            st.markdown(f"**{heading}**")
            st.caption(description)

    st.caption(
        f"Summary: {pending_tasks} pending · {active_tasks} in progress · "
        f"{completed_tasks} completed · {delayed_tasks} delayed."
    )


# ============================================================
# EMPLOYEE MANAGEMENT
# ============================================================

elif page == "Employee Management":
    st.title("Employee Management")
    st.write("Manage employee skills, availability, experience and workload.")
    st.divider()
    st.subheader("Add New Employee")

    with st.form("employee_form"):
        name = st.text_input("Employee Name")
        skills = st.text_input(
            "Skills",
            placeholder="Python, Java, SQL  (commas or spaces)",
        )
        col1, col2 = st.columns(2)

        with col1:
            availability = st.selectbox(
                "Availability",
                ["Available", "Unavailable"],
            )
            max_capacity = st.number_input(
                "Maximum Working Capacity (hours/week)",
                min_value=1.0,
                max_value=100.0,
                value=40.0,
            )
            current_workload = st.number_input(
                "Current Workload (hours/week)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
            )

        with col2:
            experience_years = st.number_input(
                "Experience (years)",
                min_value=0.0,
                max_value=50.0,
                value=2.0,
                step=0.5,
            )
            historical_performance = st.number_input(
                "Historical Performance Factor",
                min_value=0.5,
                max_value=1.5,
                value=1.0,
                step=0.05,
                help=(
                    "A manually supplied prototype factor. 1.0 is neutral. "
                    "It is not automatically calculated from completed tasks."
                ),
            )

        st.caption(
            "Performance factor: 1.0 is neutral. Values above 1.0 represent "
            "stronger assumed performance; values below 1.0 represent weaker assumed performance."
        )
        submitted = st.form_submit_button("Add Employee")

        if submitted:
            clean_name = " ".join(name.split())
            clean_skills = normalize_skills(skills)
            existing_names = {
                str(e["name"]).strip().lower() for e in get_all_employees()
            }

            if not clean_name or not clean_skills:
                st.error("Please enter employee name and skills.")
            elif clean_name.lower() in existing_names:
                st.error(f"An employee named '{clean_name}' already exists.")
            elif current_workload > max_capacity:
                st.error("Current workload cannot exceed maximum capacity.")
            else:
                add_employee(
                    clean_name,
                    clean_skills,
                    availability,
                    max_capacity,
                    current_workload,
                    experience_years,
                    historical_performance,
                )
                st.success("Employee added successfully!")
                st.rerun()

    st.divider()
    st.subheader("Employee Records")
    employees = get_all_employees()

    if employees:
        st.dataframe(
            employee_display_dataframe(employees),
            use_container_width=True,
            hide_index=True,
        )

        stale_employees = [
            e for e in employees
            if normalize_skills(e["skills"]) != str(e["skills"]).strip()
        ]
        if stale_employees:
            with st.expander(
                f"Standardise skills format ({len(stale_employees)} record(s))"
            ):
                st.write(
                    "These employees have skills stored with spaces or "
                    "uneven separators. Standardising rewrites them as "
                    "comma-separated skills (for example 'python sql' "
                    "becomes 'python, sql')."
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Employee": e["name"],
                            "Stored as": e["skills"],
                            "Will become": normalize_skills(e["skills"]),
                        }
                        for e in stale_employees
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
                if st.button("Standardise employee skills"):
                    for e in stale_employees:
                        update_employee(
                            e["employee_id"],
                            e["name"],
                            normalize_skills(e["skills"]),
                            e["availability"],
                            e["max_capacity"],
                            e["current_workload"],
                            e["experience_years"] or 0,
                            e["historical_performance"] or 1.0,
                        )
                    st.success("Employee skills standardised.")
                    st.rerun()

        st.divider()
        st.subheader("Workload Comparison")
        st.plotly_chart(
            utilization_figure([
                {"Employee": e["name"], "Utilization": utilization_value(e)}
                for e in employees
            ]),
            use_container_width=True,
        )

        employee_options = employee_display_options(employees)
        st.divider()
        st.subheader("Edit Employee")

        selected_edit_label = st.selectbox(
            "Select Employee to Edit",
            list(employee_options.keys()),
            key="edit_employee_selection",
        )
        selected_edit_employee = employee_options[selected_edit_label]

        with st.form("edit_employee_form"):
            edit_name = st.text_input(
                "Employee Name",
                value=selected_edit_employee["name"],
            )
            edit_skills = st.text_input(
                "Skills",
                value=selected_edit_employee["skills"],
            )
            edit_availability = st.selectbox(
                "Availability",
                ["Available", "Unavailable"],
                index=(
                    0 if selected_edit_employee["availability"] == "Available"
                    else 1
                ),
            )
            edit_max_capacity = st.number_input(
                "Maximum Working Capacity (hours/week)",
                min_value=1.0,
                max_value=100.0,
                value=float(selected_edit_employee["max_capacity"] or 40),
            )
            edit_current_workload = st.number_input(
                "Current Workload (hours/week)",
                min_value=0.0,
                max_value=100.0,
                value=float(selected_edit_employee["current_workload"] or 0),
            )
            edit_experience = st.number_input(
                "Experience (years)",
                min_value=0.0,
                max_value=50.0,
                value=float(selected_edit_employee["experience_years"] or 0),
                step=0.5,
            )
            edit_performance = st.number_input(
                "Historical Performance Factor",
                min_value=0.5,
                max_value=1.5,
                value=float(
                    selected_edit_employee["historical_performance"] or 1.0
                ),
                step=0.05,
            )
            update_submitted = st.form_submit_button("Save Employee Changes")

            if update_submitted:
                clean_edit_name = " ".join(edit_name.split())
                clean_edit_skills = normalize_skills(edit_skills)
                other_names = {
                    str(e["name"]).strip().lower()
                    for e in employees
                    if e["employee_id"] != selected_edit_employee["employee_id"]
                }

                if not clean_edit_name or not clean_edit_skills:
                    st.error("Name and skills cannot be empty.")
                elif clean_edit_name.lower() in other_names:
                    st.error(
                        f"Another employee is already named '{clean_edit_name}'."
                    )
                elif edit_current_workload > edit_max_capacity:
                    st.error("Workload cannot exceed maximum capacity.")
                else:
                    update_employee(
                        selected_edit_employee["employee_id"],
                        clean_edit_name,
                        clean_edit_skills,
                        edit_availability,
                        edit_max_capacity,
                        edit_current_workload,
                        edit_experience,
                        edit_performance,
                    )
                    st.success("Employee updated successfully!")
                    st.rerun()

        st.divider()
        st.subheader("Delete Employee")
        selected_delete = st.selectbox(
            "Select Employee to Delete",
            list(employee_options.keys()),
            key="delete_employee_selection",
        )

        if st.button("Delete Selected Employee"):
            if delete_employee(employee_options[selected_delete]["employee_id"]):
                st.success("Employee deleted successfully!")
                st.rerun()
            else:
                st.error("Could not delete employee.")
    else:
        st.info("No employees added yet.")


# ============================================================
# TASK MANAGEMENT
# ============================================================

elif page == "Task Management":
    st.title("Task Management")
    st.write("Create, view and manage project tasks.")
    st.divider()
    st.subheader("Add New Task")

    with st.form("task_form"):
        title = st.text_input("Task Title")
        description = st.text_area("Task Description")
        required_skills = st.text_input(
            "Required Skills",
            placeholder="Python, SQL  (commas or spaces)",
        )
        col1, col2 = st.columns(2)

        with col1:
            priority = st.selectbox(
                "Task Priority",
                ["Low", "Medium", "High", "Critical"],
            )
            estimated_hours = st.number_input(
                "Estimated Completion Hours",
                min_value=1.0,
                max_value=1000.0,
                value=5.0,
            )

        with col2:
            task_complexity = st.number_input(
                "Task Complexity",
                min_value=1.0,
                max_value=5.0,
                value=3.0,
                step=0.5,
                help="1 = Simple, 5 = Very Complex",
            )

        submitted = st.form_submit_button("Add Task")

        if submitted:
            clean_title = " ".join(title.split())
            clean_required = normalize_skills(required_skills)
            existing_titles = {
                str(t["title"]).strip().lower() for t in get_all_tasks()
            }

            if not clean_title or not clean_required:
                st.error("Please enter task title and required skills.")
            elif clean_title.lower() in existing_titles:
                st.error(f"A task titled '{clean_title}' already exists.")
            else:
                add_task(
                    clean_title,
                    description.strip(),
                    clean_required,
                    priority,
                    estimated_hours,
                    task_complexity,
                )
                st.success("Task added successfully!")
                st.rerun()

    st.divider()
    st.subheader("Task Records")
    tasks = get_all_tasks()

    if tasks:
        st.dataframe(
            display_dataframe(tasks, hidden_columns=["task_id"]),
            use_container_width=True,
            hide_index=True,
        )

        stale_tasks = [
            t for t in tasks
            if normalize_skills(t["required_skills"])
            != str(t["required_skills"]).strip()
        ]
        if stale_tasks:
            with st.expander(
                f"Standardise skills format ({len(stale_tasks)} record(s))"
            ):
                st.write(
                    "These tasks have required skills stored with spaces or "
                    "uneven separators. Standardising rewrites them as "
                    "comma-separated skills."
                )
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Task": t["title"],
                            "Stored as": t["required_skills"],
                            "Will become": normalize_skills(
                                t["required_skills"]
                            ),
                        }
                        for t in stale_tasks
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )
                if st.button("Standardise task skills"):
                    for t in stale_tasks:
                        update_task_fields(
                            t["task_id"],
                            {
                                "required_skills": normalize_skills(
                                    t["required_skills"]
                                )
                            },
                        )
                    st.success("Task skills standardised.")
                    st.rerun()

        task_options = task_display_options(tasks)

        st.divider()
        st.subheader("Edit Task")

        task_records = task_record_display_options(tasks)
        edit_task_label = st.selectbox(
            "Select Task to Edit",
            list(task_records.keys()),
            key="edit_task_selection",
        )
        edit_record = dict(task_records[edit_task_label])
        edit_id = edit_record["task_id"]
        priority_choices = ["Low", "Medium", "High", "Critical"]

        with st.form("edit_task_form"):
            edit_task_title = st.text_input(
                "Task Title",
                value=edit_record.get("title") or "",
                key=f"edit_task_title_{edit_id}",
            )
            edit_task_description = st.text_area(
                "Task Description",
                value=edit_record.get("description") or "",
                key=f"edit_task_description_{edit_id}",
            )
            edit_task_skills = st.text_input(
                "Required Skills",
                value=edit_record.get("required_skills") or "",
                key=f"edit_task_skills_{edit_id}",
            )

            ec1, ec2, ec3, ec4 = st.columns(4)
            with ec1:
                edit_task_priority = st.selectbox(
                    "Task Priority",
                    priority_choices,
                    index=(
                        priority_choices.index(edit_record.get("priority"))
                        if edit_record.get("priority") in priority_choices
                        else 1
                    ),
                    key=f"edit_task_priority_{edit_id}",
                )
            with ec2:
                edit_task_hours = st.number_input(
                    "Estimated Completion Hours",
                    min_value=1.0,
                    max_value=1000.0,
                    value=min(
                        max(float(edit_record.get("estimated_hours") or 5.0), 1.0),
                        1000.0,
                    ),
                    key=f"edit_task_hours_{edit_id}",
                )
            with ec3:
                edit_task_complexity = st.number_input(
                    "Task Complexity",
                    min_value=1.0,
                    max_value=5.0,
                    value=min(
                        max(float(edit_record.get("task_complexity") or 3.0), 1.0),
                        5.0,
                    ),
                    step=0.5,
                    key=f"edit_task_complexity_{edit_id}",
                )
            with ec4:
                edit_actual_hours = st.number_input(
                    "Actual Hours (optional)",
                    min_value=0.0,
                    max_value=1000.0,
                    value=min(max(float(edit_record.get("actual_hours") or 0), 0), 1000),
                    step=0.5,
                    key=f"edit_actual_hours_{edit_id}",
                    help="Enter the completed hours to evaluate prediction accuracy.",
                )

            save_task = st.form_submit_button("Save Task Changes")

            if save_task:
                clean_edit_title = " ".join(edit_task_title.split())
                clean_edit_required = normalize_skills(edit_task_skills)
                other_titles = {
                    str(t["title"]).strip().lower()
                    for t in tasks
                    if t["task_id"] != edit_id
                }

                if not clean_edit_title or not clean_edit_required:
                    st.error("Task title and required skills cannot be empty.")
                elif clean_edit_title.lower() in other_titles:
                    st.error(
                        f"Another task is already titled '{clean_edit_title}'."
                    )
                else:
                    update_task_fields(
                        edit_id,
                        {
                            "title": clean_edit_title,
                            "description": edit_task_description.strip(),
                            "required_skills": clean_edit_required,
                            "priority": edit_task_priority,
                            "estimated_hours": edit_task_hours,
                            "task_complexity": edit_task_complexity,
                            "actual_hours": edit_actual_hours or None,
                        },
                    )
                    st.success("Task updated successfully!")
                    st.rerun()

        st.caption(
            "Changing estimated hours does not change workload already "
            "recorded for an employee who has been assigned this task."
        )

        st.divider()
        st.subheader("Update Task Status")

        selected_task = st.selectbox(
            "Select a Task",
            list(task_options.keys()),
            key="update_task_selection",
        )
        new_status = st.selectbox(
            "New Status",
            ["Pending", "In Progress", "Completed", "Delayed"],
        )

        if st.button("Update Status"):
            if update_task_status(task_options[selected_task], new_status):
                st.success("Task status updated!")
                st.rerun()
            else:
                st.error("Could not update task status.")

        st.divider()
        st.subheader("Delete Task")
        delete_selection = st.selectbox(
            "Select Task to Delete",
            list(task_options.keys()),
            key="delete_task",
        )

        if st.button("Delete Selected Task"):
            if delete_task(task_options[delete_selection]):
                st.success("Task deleted successfully!")
                st.rerun()
            else:
                st.error("Could not delete task.")
    else:
        st.info("No tasks added yet.")


# ============================================================
# INITIAL TASK ALLOCATION
# ============================================================

elif page == "Initial Task Allocation":
    st.title("Initial Task Allocation")
    st.write(
        "Find suitable employees based on skills, availability and workload."
    )
    st.divider()

    tasks = get_all_tasks()
    pending_tasks = [t for t in tasks if t["status"] == "Pending"]

    if not pending_tasks:
        st.warning("No pending tasks available for allocation.")
    else:
        task_options = task_display_options(pending_tasks)
        selected_task = st.selectbox(
            "Select a Task",
            list(task_options.keys()),
            key="initial_allocation_task",
        )
        task_id = task_options[selected_task]

        if st.button("Find Suitable Employees"):
            st.session_state["recommendations"] = get_recommendations(task_id)
            st.session_state["allocation_task_id"] = task_id

        if (
            st.session_state.get("allocation_task_id") == task_id
            and "recommendations" in st.session_state
        ):
            recommendations = st.session_state["recommendations"]
            st.subheader("Employee Recommendations")

            if recommendations:
                st.dataframe(
                    recommendations,
                    use_container_width=True,
                    hide_index=True,
                )

                employee_options = {
                    f"{number} - {employee['name']} - Score: {employee['total_score']}":
                    employee["employee_id"]
                    for number, employee in enumerate(recommendations, start=1)
                }
                selected_employee = st.selectbox(
                    "Select Employee",
                    list(employee_options.keys()),
                    key="initial_allocation_employee",
                )

                task_record = next(
                    t for t in pending_tasks if t["task_id"] == task_id
                )
                employees_by_id = {
                    e["employee_id"]: e for e in get_all_employees()
                }

                st.subheader("Why these employees?")
                explain_rows = explanation_rows(
                    recommendations, task_record, employees_by_id
                )
                if explain_rows:
                    st.dataframe(
                        pd.DataFrame(explain_rows).drop(
                            columns=["_before", "_after"]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.plotly_chart(
                        workload_impact_figure(explain_rows),
                        use_container_width=True,
                    )

                chosen_employee = employees_by_id.get(
                    employee_options[selected_employee]
                )
                allocation_check = None
                if chosen_employee is not None:
                    allocation_check = allocation_problems(
                        chosen_employee, task_record
                    )
                    st.markdown(explanation_text(chosen_employee, task_record))
                    for warning_text in allocation_check["warnings"]:
                        st.warning(warning_text)
                    for blocker_text in allocation_check["blockers"]:
                        st.error(blocker_text)

                if st.button("Allocate Task"):
                    if allocation_check and allocation_check["blockers"]:
                        st.error(
                            "This assignment was not made. Please choose a "
                            "suitable employee."
                        )
                    else:
                        success, message = assign_task(
                            task_id,
                            employee_options[selected_employee],
                        )
                        if success:
                            st.success(message)
                            st.session_state.pop("recommendations", None)
                            st.session_state.pop("allocation_task_id", None)
                            st.rerun()
                        else:
                            st.error(message)
            else:
                st.warning(
                    "No suitable employees found. Check employee skills, "
                    "availability and remaining capacity."
                )


# ============================================================
# DISTURBANCE MANAGEMENT
# ============================================================

elif page == "Disturbance Management":
    st.title("Disturbance Management")
    st.write(
        "Report employee unavailability, workload overload and task delays."
    )
    st.info(
        "Disturbances are entered by the manager and recorded for further "
        "analysis and dynamic reallocation."
    )

    employees = get_all_employees()
    tasks = get_all_tasks()

    st.divider()
    disturbance_type = st.selectbox(
        "Select Disturbance Type",
        [
            "Employee Unavailability",
            "Workload Overload",
            "Task Delay",
        ],
    )

    if disturbance_type == "Employee Unavailability":
        st.subheader("Report Employee Unavailability")

        if employees:
            employee_options = employee_id_display_options(employees)
            selected_employee = st.selectbox(
                "Select Employee",
                list(employee_options.keys()),
                key="unavailable_employee",
            )
            description = st.text_area(
                "Reason for Unavailability",
                key="unavailability_reason",
            )

            if st.button("Report Unavailability"):
                success, message = report_unavailability(
                    employee_options[selected_employee],
                    description,
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.warning("Add employees before reporting disturbances.")

    elif disturbance_type == "Workload Overload":
        st.subheader("Report Workload Overload")

        if employees:
            employee_options = employee_id_display_options(employees)
            selected_employee = st.selectbox(
                "Select Employee",
                list(employee_options.keys()),
                key="overload_employee",
            )
            employee_id = employee_options[selected_employee]
            record = next(
                e for e in employees if e["employee_id"] == employee_id
            )

            st.write(f"Maximum Capacity: {record['max_capacity']} hours")
            st.write(f"Current Workload: {record['current_workload']} hours")

            new_workload = st.number_input(
                "Updated Workload (hours/week)",
                min_value=0.0,
                max_value=200.0,
                value=float(record["current_workload"] or 0) + 5,
                key="updated_overload",
            )
            description = st.text_area(
                "Description of Overload",
                key="overload_description",
            )

            if st.button("Report Workload Overload"):
                success, message = report_workload_overload(
                    employee_id,
                    new_workload,
                    description,
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.warning("Add employees before reporting disturbances.")

    elif disturbance_type == "Task Delay":
        st.subheader("Report Task Delay")

        if tasks:
            task_options = task_display_options(tasks)
            selected_task = st.selectbox(
                "Select Delayed Task",
                list(task_options.keys()),
                key="delayed_task",
            )
            description = st.text_area(
                "Reason for Delay",
                key="delay_reason",
            )

            if st.button("Report Task Delay"):
                success, message = report_task_delay(
                    task_options[selected_task],
                    description,
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
        else:
            st.warning("Add tasks before reporting disturbances.")

    st.divider()
    st.subheader("Disturbance History")
    disturbances = get_all_disturbances()

    if disturbances:
        st.dataframe(
            display_dataframe(
                disturbances,
                hidden_columns=["disturbance_id"],
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No disturbances have been reported yet.")


# ============================================================
# DYNAMIC REALLOCATION
# ============================================================

elif page == "Dynamic Reallocation":
    st.title("Dynamic Task Reallocation")
    st.write(
        "Review tasks affected by employee unavailability or workload "
        "overload and approve suitable replacements."
    )
    st.info(
        "The system recommends replacements. The manager makes the final "
        "reassignment decision."
    )
    st.divider()

    affected_assignments = get_affected_assignments()
    st.subheader("Affected Assignments")

    if not affected_assignments:
        st.success("No affected active assignments were found.")
    else:
        st.dataframe(
            display_dataframe(
                affected_assignments,
                hidden_columns=["assignment_id", "task_id", "employee_id"],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Review and Reassign Tasks")

        assignment_options = {
            (
                f"Assignment {number} - {assignment['task_title']} "
                f"(Currently assigned to {assignment['employee_name']})"
            ): assignment
            for number, assignment in enumerate(
                affected_assignments, start=1
            )
        }

        selected_label = st.selectbox(
            "Select an affected assignment",
            list(assignment_options.keys()),
            key="affected_assignment",
        )
        selected_assignment = assignment_options[selected_label]

        task_id = selected_assignment["task_id"]
        old_employee_id = selected_assignment["employee_id"]

        st.write(
            f"**Affected Employee:** {selected_assignment['employee_name']}"
        )
        st.write(f"**Affected Task:** {selected_assignment['task_title']}")
        st.write(
            f"**Required Skills:** {selected_assignment['required_skills']}"
        )
        st.write(
            f"**Estimated Hours:** {selected_assignment['estimated_hours']}"
        )

        recommendation_key = f"reallocation_{task_id}_{old_employee_id}"

        if st.button("Find Replacement Employees"):
            st.session_state[recommendation_key] = (
                get_replacement_recommendations(task_id, old_employee_id)
            )

        if recommendation_key in st.session_state:
            recommendations = st.session_state[recommendation_key]
            st.subheader("Replacement Recommendations")

            if recommendations:
                st.dataframe(
                    recommendations,
                    use_container_width=True,
                    hide_index=True,
                )

                employee_options = {
                    f"{number} - {employee['name']} - Score: {employee['total_score']}":
                    employee["employee_id"]
                    for number, employee in enumerate(recommendations, start=1)
                }

                selected_employee = st.selectbox(
                    "Choose Replacement Employee",
                    list(employee_options.keys()),
                    key=f"replacement_{task_id}_{old_employee_id}",
                )

                employees_by_id = {
                    e["employee_id"]: e for e in get_all_employees()
                }

                st.subheader("Why these replacements?")
                explain_rows = explanation_rows(
                    recommendations, selected_assignment, employees_by_id
                )
                if explain_rows:
                    st.dataframe(
                        pd.DataFrame(explain_rows).drop(
                            columns=["_before", "_after"]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.plotly_chart(
                        workload_impact_figure(explain_rows),
                        use_container_width=True,
                    )

                replacement_employee = employees_by_id.get(
                    employee_options[selected_employee]
                )
                replacement_check = None
                if replacement_employee is not None:
                    replacement_check = allocation_problems(
                        replacement_employee, selected_assignment
                    )
                    st.markdown(
                        explanation_text(replacement_employee, selected_assignment)
                    )
                    for warning_text in replacement_check["warnings"]:
                        st.warning(warning_text)
                    for blocker_text in replacement_check["blockers"]:
                        st.error(blocker_text)

                reason = st.text_area(
                    "Reason for Reallocation",
                    value=(
                        "Original employee became unavailable or exceeded "
                        "workload capacity."
                    ),
                    key=f"reason_{task_id}_{old_employee_id}",
                )

                st.warning(
                    "The reassignment will only happen after approval."
                )

                if st.button(
                    "Approve and Reallocate Task",
                    key=f"approve_{task_id}_{old_employee_id}",
                ):
                    if replacement_check and replacement_check["blockers"]:
                        st.error(
                            "The reallocation was not made. Please choose a "
                            "suitable replacement."
                        )
                    else:
                        success, message = approve_reallocation(
                            task_id,
                            old_employee_id,
                            employee_options[selected_employee],
                            reason,
                        )

                        if success:
                            st.success(message)
                            st.session_state.pop(recommendation_key, None)
                            st.rerun()
                        else:
                            st.error(message)
            else:
                st.warning(
                    "No eligible replacement employees found. Check skills, "
                    "availability and capacity."
                )

    st.divider()
    st.subheader("Reallocation History")

    connection = get_connection()
    history = connection.execute(
        """
        SELECT
            h.history_id,
            t.title AS task_title,
            old_e.name AS previous_employee,
            new_e.name AS new_employee,
            h.reason,
            h.changed_at
        FROM reallocation_history h
        LEFT JOIN tasks t ON h.task_id = t.task_id
        LEFT JOIN employees old_e ON h.old_employee_id = old_e.employee_id
        LEFT JOIN employees new_e ON h.new_employee_id = new_e.employee_id
        ORDER BY h.history_id DESC
        """
    ).fetchall()
    connection.close()

    if history:
        st.dataframe(
            display_dataframe(history, hidden_columns=["history_id"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No tasks have been reallocated yet.")

    st.divider()
    st.subheader("Assignment History by Task")
    st.caption(
        "Every assignment ever made for each task: previous employees, "
        "the current one and when each assignment happened."
    )

    connection = get_connection()
    assignment_history = connection.execute(
        """
        SELECT
            t.title AS task,
            e.name AS employee,
            a.assigned_at,
            a.status
        FROM assignments a
        LEFT JOIN tasks t ON a.task_id = t.task_id
        LEFT JOIN employees e ON a.employee_id = e.employee_id
        ORDER BY t.title, a.assigned_at
        """
    ).fetchall()
    connection.close()

    if assignment_history:
        st.dataframe(
            display_dataframe(assignment_history),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No assignments have been recorded yet.")


# ============================================================
# COMPLETION-TIME PREDICTION
# ============================================================

elif page == "Completion-Time Prediction":
    st.title("ML-Based Completion-Time Prediction")
    st.write(
        "Estimate task completion time using the trained machine learning "
        "regression model."
    )
    st.info(
        """
        The upgraded model uses eight input features:

        1. Estimated task hours
        2. Task priority
        3. Employee workload ratio
        4. Number of required skills
        5. Task complexity
        6. Employee experience
        7. Employee skill-match ratio
        8. Historical performance factor
        """
    )
    st.warning(
        "The model was trained using synthetic data. Its predictions are "
        "experimental estimates and are not guaranteed real-world completion times."
    )
    st.divider()

    tasks = get_all_tasks()
    employees = get_all_employees()

    if not tasks:
        st.warning("Please add tasks before making predictions.")
    elif not employees:
        st.warning(
            "Please add at least one employee before making predictions. "
            "The upgraded model requires employee-specific information."
        )
    else:
        st.subheader("Select Task")

        task_options = task_record_display_options(tasks)
        selected_task_label = st.selectbox(
            "Choose a Task",
            list(task_options.keys()),
            key="prediction_task",
        )
        selected_task = task_options[selected_task_label]

        estimated_hours = float(selected_task["estimated_hours"] or 0)
        task_priority = selected_task["priority"]
        required_skills = skill_set(selected_task["required_skills"])
        required_skill_count = len(required_skills)
        task_complexity = float(selected_task["task_complexity"] or 3.0)

        st.write(f"**Task:** {selected_task['title']}")
        st.write(f"**Estimated Hours:** {estimated_hours}")
        st.write(f"**Priority:** {task_priority}")
        st.write(f"**Required Skills:** {', '.join(sorted(required_skills))}")
        st.write(f"**Task Complexity:** {task_complexity}/5")
        st.write(f"**Number of Required Skills:** {required_skill_count}")

        st.divider()
        st.subheader("Select Employee")

        employee_options = employee_display_options(employees)
        selected_employee_label = st.selectbox(
            "Choose an Employee",
            list(employee_options.keys()),
            key="prediction_employee",
        )
        selected_employee = employee_options[selected_employee_label]

        max_capacity = float(selected_employee["max_capacity"] or 0)
        current_workload = float(
            selected_employee["current_workload"] or 0
        )
        workload_ratio = (
            current_workload / max_capacity if max_capacity > 0 else 0.0
        )
        experience_years = float(
            selected_employee["experience_years"] or 0
        )
        historical_performance = float(
            selected_employee["historical_performance"] or 1.0
        )
        employee_skills = skill_set(selected_employee["skills"])

        if required_skills:
            skill_match_ratio = (
                len(employee_skills.intersection(required_skills))
                / len(required_skills)
            )
        else:
            skill_match_ratio = 0.0

        st.write(f"**Employee:** {selected_employee['name']}")
        st.write(f"**Employee Skills:** {selected_employee['skills']}")
        st.write(f"**Experience:** {experience_years} years")
        st.write(f"**Current Workload:** {current_workload} hours/week")
        st.write(f"**Maximum Capacity:** {max_capacity} hours/week")
        st.write(f"**Workload Ratio:** {workload_ratio:.2f}")
        st.write(f"**Skill Match Ratio:** {skill_match_ratio:.2f}")
        st.write(
            f"**Historical Performance Factor:** {historical_performance:.2f}"
        )

        if selected_employee["availability"] != "Available":
            st.warning(
                "This employee is currently marked unavailable. The prediction "
                "can still be generated for comparison, but this is not an "
                "allocation recommendation."
            )

        if skill_match_ratio < 1:
            st.warning(
                "The selected employee does not match all required skills."
            )

        st.divider()
        st.subheader("Generate Prediction")

        if st.button("Predict Completion Time", type="primary"):
            prediction_priority = task_priority

            predicted_hours = predict_completion_time(
                estimated_hours=estimated_hours,
                priority=prediction_priority,
                workload_ratio=workload_ratio,
                required_skill_count=required_skill_count,
                task_complexity=task_complexity,
                experience_years=experience_years,
                skill_match_ratio=skill_match_ratio,
                historical_performance=historical_performance,
            )

            if predicted_hours is None:
                st.error(
                    "Trained model not found. Run "
                    "python models/train_model.py from the project folder."
                )
            else:
                prediction_inputs = {
                    "estimated_hours": estimated_hours,
                    "priority": prediction_priority,
                    "workload_ratio": workload_ratio,
                    "required_skill_count": required_skill_count,
                    "task_complexity": task_complexity,
                    "experience_years": experience_years,
                    "skill_match_ratio": skill_match_ratio,
                    "historical_performance": historical_performance,
                }
                record_prediction(
                    selected_task["task_id"],
                    selected_employee["employee_id"],
                    model_version(MODEL_PATH) or "unknown",
                    predicted_hours,
                    prediction_inputs,
                )
                difference = predicted_hours - estimated_hours
                col1, col2 = st.columns(2)
                col1.metric(
                    "Original Estimated Time",
                    f"{estimated_hours:.2f} hours",
                )
                col2.metric(
                    "ML Predicted Completion Time",
                    f"{predicted_hours:.2f} hours",
                    delta=f"{difference:+.2f} hours",
                )

                st.success(
                    f"The model predicts approximately {predicted_hours:.2f} "
                    "hours for this task."
                )

                if difference > 0:
                    st.warning(
                        "The predicted completion time is higher than the "
                        "original estimate."
                    )
                elif difference < 0:
                    st.info(
                        "The predicted completion time is lower than the "
                        "original estimate."
                    )
                else:
                    st.info(
                        "The predicted completion time matches the original estimate."
                    )

                st.divider()
                st.subheader("What influenced this estimate?")

                base_inputs = dict(
                    estimated_hours=estimated_hours,
                    priority=prediction_priority,
                    workload_ratio=workload_ratio,
                    required_skill_count=required_skill_count,
                    task_complexity=task_complexity,
                    experience_years=experience_years,
                    skill_match_ratio=skill_match_ratio,
                    historical_performance=historical_performance,
                )

                factor_table = [
                    ("Task priority", "priority", "Medium", prediction_priority),
                    ("Employee workload ratio", "workload_ratio", 0.5, workload_ratio),
                    ("Number of required skills", "required_skill_count", 3, required_skill_count),
                    ("Task complexity", "task_complexity", 3.0, task_complexity),
                    ("Employee experience (years)", "experience_years", 3.0, experience_years),
                    ("Skill-match ratio", "skill_match_ratio", 1.0, skill_match_ratio),
                    ("Historical performance factor", "historical_performance", 1.0, historical_performance),
                ]

                factor_rows = []
                for label, argument, reference, current_value in factor_table:
                    test_inputs = dict(base_inputs)
                    test_inputs[argument] = reference
                    try:
                        reference_prediction = predict_completion_time(**test_inputs)
                    except Exception:
                        reference_prediction = None

                    if reference_prediction is None:
                        continue

                    factor_rows.append({
                        "Factor": label,
                        "Current value": (
                            f"{current_value:.2f}"
                            if isinstance(current_value, float)
                            else str(current_value)
                        ),
                        "Neutral reference": (
                            f"{reference:.2f}"
                            if isinstance(reference, float)
                            else str(reference)
                        ),
                        "Effect (hours)": round(
                            predicted_hours - reference_prediction, 2
                        ),
                    })

                if factor_rows:
                    factor_df = pd.DataFrame(factor_rows)
                    factor_df["Direction"] = factor_df["Effect (hours)"].apply(
                        lambda value: (
                            "Adds time" if value > 0
                            else "Saves time" if value < 0
                            else "No effect"
                        )
                    )
                    factor_df = factor_df.reindex(
                        factor_df["Effect (hours)"].abs()
                        .sort_values(ascending=False).index
                    )

                    fig = px.bar(
                        factor_df,
                        x="Effect (hours)",
                        y="Factor",
                        orientation="h",
                        color="Direction",
                        color_discrete_map={
                            "Adds time": CORAL,
                            "Saves time": BRAND,
                            "No effect": SLATE,
                        },
                        text="Effect (hours)",
                    )
                    apply_chart_theme(fig)
                    fig.update_layout(
                        height=max(280, 48 * len(factor_df) + 90),
                        legend_title_text="",
                        xaxis_title="Change in predicted hours",
                        yaxis_title=None,
                    )
                    fig.update_yaxes(autorange="reversed")
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig, use_container_width=True)

                    strongest = factor_df.iloc[0]
                    if strongest["Effect (hours)"] != 0:
                        st.write(
                            f"The biggest influence is **{strongest['Factor']}** "
                            f"({strongest['Current value']}), which "
                            f"{strongest['Direction'].lower()} "
                            f"({strongest['Effect (hours)']:+.2f} h) compared "
                            "with a neutral reference value."
                        )

                    st.dataframe(
                        factor_df.drop(columns=["Direction"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        "Each effect is found by replacing one input with a "
                        "neutral reference value while keeping the others "
                        "unchanged, then comparing the model's predictions. "
                        "It describes how this trained model behaves; it does "
                        "not prove cause and effect in real work. Estimated "
                        "hours is the baseline the other factors adjust."
                    )


# ============================================================
# ANALYTICS & PERFORMANCE EVALUATION
# ============================================================

elif page == "Analytics & Performance Evaluation":
    st.title("Analytics & Performance Evaluation")
    st.write(
        "View task progress, employee workload distribution, allocation "
        "activity and descriptive system indicators."
    )
    st.info(
        "These charts describe records currently stored in the prototype "
        "database. They do not, by themselves, prove improved productivity or fairness."
    )

    employees = get_all_employees()
    tasks = get_all_tasks()

    connection = get_connection()

    assignments = connection.execute(
        """
        SELECT
            a.assignment_id,
            a.task_id,
            t.title AS task_title,
            a.employee_id,
            e.name AS employee_name,
            a.assigned_at,
            a.status AS assignment_status,
            t.status AS task_status,
            t.priority,
            t.estimated_hours
        FROM assignments a
        LEFT JOIN tasks t ON a.task_id = t.task_id
        LEFT JOIN employees e ON a.employee_id = e.employee_id
        ORDER BY a.assignment_id DESC
        """
    ).fetchall()

    reallocations = connection.execute(
        """
        SELECT
            h.history_id,
            t.title AS task_title,
            old_e.name AS previous_employee,
            new_e.name AS new_employee,
            h.reason,
            h.changed_at
        FROM reallocation_history h
        LEFT JOIN tasks t ON h.task_id = t.task_id
        LEFT JOIN employees old_e ON h.old_employee_id = old_e.employee_id
        LEFT JOIN employees new_e ON h.new_employee_id = new_e.employee_id
        ORDER BY h.history_id DESC
        """
    ).fetchall()

    disturbances = connection.execute(
        """
        SELECT
            disturbance_id,
            disturbance_type,
            description,
            status,
            created_at
        FROM disturbances
        ORDER BY disturbance_id DESC
        """
    ).fetchall()

    connection.close()

    total_employees = len(employees)
    total_tasks = len(tasks)

    status_counts = {
        "Pending": 0,
        "In Progress": 0,
        "Completed": 0,
        "Delayed": 0,
    }

    for task in tasks:
        status_counts[task["status"]] = (
            status_counts.get(task["status"], 0) + 1
        )

    total_assignments = len(assignments)
    active_assignments = sum(
        assignment["assignment_status"] == "Active"
        for assignment in assignments
    )
    total_reallocations = len(reallocations)
    total_disturbances = len(disturbances)
    completed_count = status_counts["Completed"]

    completion_rate = (
        completed_count / total_tasks * 100 if total_tasks else 0
    )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Total Employees", total_employees)
    metric2.metric("Total Tasks", total_tasks)
    metric3.metric("Active Assignments", active_assignments)
    metric4.metric("Reallocations", total_reallocations)

    st.divider()
    st.subheader("Task Status Overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pending", status_counts["Pending"])
    c2.metric("In Progress", status_counts["In Progress"])
    c3.metric("Completed", completed_count)
    c4.metric("Delayed", status_counts["Delayed"])

    st.metric("Task Completion Rate", f"{completion_rate:.1f}%")

    status_df = pd.DataFrame({
        "Task Status": list(status_counts.keys()),
        "Number of Tasks": list(status_counts.values()),
    })

    if status_df["Number of Tasks"].sum() > 0:
        fig = px.pie(
            status_df,
            names="Task Status",
            values="Number of Tasks",
            title="Distribution of Tasks by Status",
            hole=0.35,
            color="Task Status",
            color_discrete_map=STATUS_COLORS,
        )
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Add tasks to view the task status chart.")

    st.divider()
    st.subheader("Employee Workload Distribution")

    if employees:
        workload_rows = []

        for employee in employees:
            current = float(employee["current_workload"] or 0)
            capacity = float(employee["max_capacity"] or 0)
            utilization = current / capacity * 100 if capacity > 0 else 0

            workload_rows.append({
                "Employee": employee["name"],
                "Availability": employee["availability"],
                "Current Workload (hours/week)": current,
                "Maximum Capacity (hours/week)": capacity,
                "Utilization (%)": round(utilization, 2),
                "Remaining Capacity (hours/week)": round(
                    capacity - current, 2
                ),
            })

        workload_df = pd.DataFrame(workload_rows)
        st.dataframe(
            workload_df,
            use_container_width=True,
            hide_index=True,
        )

        fig = px.bar(
            workload_df,
            x="Employee",
            y=[
                "Current Workload (hours/week)",
                "Remaining Capacity (hours/week)",
            ],
            title="Current Workload and Remaining Capacity",
            barmode="stack",
            color_discrete_sequence=[BRAND, "#BFE0DB"],
        )
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

        utilization_values = workload_df["Utilization (%)"]
        average_utilization = float(utilization_values.mean())
        utilization_range = float(
            utilization_values.max() - utilization_values.min()
        )
        utilization_std = float(utilization_values.std(ddof=0))

        overloaded_count = sum(
            float(employee["current_workload"] or 0)
            > float(employee["max_capacity"] or 0)
            for employee in employees
        )

        a, b, c = st.columns(3)
        a.metric(
            "Average Capacity Utilization",
            f"{average_utilization:.1f}%",
        )
        b.metric(
            "Utilization Range",
            f"{utilization_range:.1f} percentage points",
        )
        c.metric("Employees Over Capacity", overloaded_count)

        st.caption(
            f"Descriptive workload spread (population standard deviation): "
            f"{utilization_std:.1f} percentage points. A smaller spread "
            "indicates more similar utilization values in the current records; "
            "it is not a formal fairness guarantee."
        )
    else:
        st.info("Add employees to view workload distribution.")

    st.divider()
    st.subheader("Allocation Strategy Comparison")
    if employees and tasks:
        strategy_results = compare_strategies(
            [dict(employee) for employee in employees],
            [dict(task) for task in tasks if task["status"] != "Completed"],
            runs=50,
            levels_by_employee=get_all_skill_levels(),
        )
        strategy_rows = []
        for strategy, metrics in strategy_results.items():
            strategy_rows.append({
                "Strategy": strategy,
                "Average Skill Match (%)": round(metrics["avg_skill_match"], 1),
                "Utilization Spread (pp)": round(metrics["spread"], 1),
                "Maximum Utilization (%)": round(metrics["max_util"], 1),
                "Overloaded Employees": round(metrics["overloaded"], 1),
                "Unassigned Tasks": round(metrics["unassigned"], 1),
            })
        st.dataframe(
            pd.DataFrame(strategy_rows),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "This is a simulation using current records. Random and round-robin "
            "are comparison baselines; it is not a causal productivity study."
        )
    else:
        st.info("Add employees and tasks to compare allocation strategies.")

    st.divider()
    st.subheader("Assignment Records")

    if assignments:
        st.dataframe(
            display_dataframe(
                assignments,
                hidden_columns=[
                    "assignment_id",
                    "task_id",
                    "employee_id",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Total assignment records: {total_assignments}. "
            "Reassigned historical records are included."
        )
    else:
        st.info("No task assignments have been recorded yet.")

    st.divider()
    st.subheader("Dynamic Reallocation History")

    if reallocations:
        st.dataframe(
            display_dataframe(
                reallocations,
                hidden_columns=["history_id"],
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No reallocation history is available yet.")

    st.divider()
    st.subheader("Reported Disturbances")

    if disturbances:
        disturbance_df = display_dataframe(
            disturbances,
            hidden_columns=["disturbance_id"],
        )

        st.metric("Total Reported Disturbances", total_disturbances)

        raw_disturbance_df = pd.DataFrame([
            dict(disturbance) for disturbance in disturbances
        ])

        disturbance_type_counts = (
            raw_disturbance_df["disturbance_type"]
            .value_counts()
            .rename_axis("Disturbance Type")
            .reset_index(name="Count")
        )

        fig = px.bar(
            disturbance_type_counts,
            x="Disturbance Type",
            y="Count",
            title="Disturbances by Type",
            color_discrete_sequence=[BRAND],
        )
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            disturbance_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No disturbances have been reported yet.")

    st.divider()
    st.subheader("Prediction Evaluation")
    prediction_records = get_prediction_records()
    observed_predictions = [
        record for record in prediction_records
        if record.get("actual_hours") is not None
    ]
    if observed_predictions:
        model_mae = sum(
            abs(record["predicted_hours"] - record["actual_hours"])
            for record in observed_predictions
        ) / len(observed_predictions)
        estimate_mae = sum(
            abs(record["estimated_hours"] - record["actual_hours"])
            for record in observed_predictions
        ) / len(observed_predictions)
        p1, p2, p3 = st.columns(3)
        p1.metric("Observed Predictions", len(observed_predictions))
        p2.metric("Model MAE", f"{model_mae:.2f} hours")
        p3.metric("Original Estimate MAE", f"{estimate_mae:.2f} hours")
        st.caption(
            "These metrics use tasks with recorded actual hours. They measure "
            "prediction error for observed records and do not establish causation."
        )
    else:
        st.info(
            "Record actual hours in Task Management to compare model predictions "
            "with the original estimates."
        )

    st.divider()
    st.subheader("Performance Evaluation Notes")

    st.write(
        "- Task completion rate is calculated from current task statuses."
    )
    st.write(
        "- Capacity utilization is current workload divided by maximum "
        "capacity for each employee."
    )
    st.write(
        "- Utilization range and standard deviation describe workload "
        "distribution; they do not establish that allocation is fair."
    )
    st.write(
        "- Reallocation and disturbance counts are taken from stored database history."
    )

    st.warning(
        "A comparison against a baseline allocation method and evaluation "
        "using real observed task-completion data are still required before "
        "making claims about improved efficiency, reduced delays or prediction "
        "accuracy in real working conditions."
    )
