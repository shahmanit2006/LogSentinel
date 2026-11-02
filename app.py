from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

from log_agent.pipeline import LogAnalysisPipeline
from log_agent.reporting import build_report_files, save_report_files

st.set_page_config(
    page_title="LogSentinel | AI Log Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Visual system ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#17243b; --muted:#68778e; --line:#e5ebf3; --panel:#ffffff; --blue:#3267d6; --teal:#0e9f91; --red:#dc3545; --amber:#f0a323; --gold:#f4c542; --violet:#7c3aed; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
.stApp { background:linear-gradient(180deg,#f5f8fd 0%,#f8faff 45%,#f4f7fb 100%); color:var(--ink); }
.block-container { padding-top:1.7rem; padding-bottom:3rem; max-width:1500px; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; color:var(--ink); letter-spacing:-.025em; }
.hero { padding:1.45rem 1.7rem; border-radius:22px; color:white; background:linear-gradient(115deg,#142642 0%,#1d4278 58%,#3267d6 100%); box-shadow:0 14px 35px rgba(28,58,105,.16); margin-bottom:1.2rem; }
.hero h1 { color:white !important; font-size:2rem; margin:0 0 .3rem 0; }
.hero p { color:#dce8fb; margin:0; font-size:.98rem; }
.eyebrow { color:#9dc2ff; font-weight:700; letter-spacing:.12em; font-size:.72rem; text-transform:uppercase; margin-bottom:.55rem; }
.metric-card { position:relative; overflow:hidden; background:white; border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem 1rem 1.25rem; box-shadow:0 5px 18px rgba(26,49,83,.045); min-height:112px; transition:transform .18s ease,box-shadow .18s ease; }
.metric-card:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(26,49,83,.09); }
.metric-card:before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--accent); }
.metric-card.events { --accent:#3267d6; } .metric-card.errors { --accent:#dc3545; } .metric-card.warnings { --accent:#f0a323; } .metric-card.anomalies { --accent:#7c3aed; }
.metric-card.errors .metric-value { color:#c92a3a; } .metric-card.warnings .metric-value { color:#bd7900; } .metric-card.anomalies .metric-value { color:#6d35c7; }
.metric-label { color:var(--muted); font-size:.82rem; font-weight:600; }
.metric-value { color:var(--ink); font-family:'Manrope',sans-serif; font-size:2rem; font-weight:800; line-height:1.35; }
.metric-note { color:#8995a8; font-size:.75rem; }
.section-card { background:white; border:1px solid var(--line); border-radius:18px; padding:1.1rem 1.2rem; }
div[data-testid="stSidebar"] { background:#edf2f9; border-right:1px solid #e1e8f1; }
div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] h3 { color:#1d304d; }
.stButton>button, .stDownloadButton>button { border-radius:10px; font-weight:700; min-height:2.7rem; }
.stButton>button[kind="primary"] { background:linear-gradient(90deg,#3267d6,#2554b5); border:0; }
.stDownloadButton>button { border:1px solid #d6e0ee; background:#f8fbff; color:#24436f; }
.stTabs [data-baseweb="tab-list"] { gap:1.1rem; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight:700; color:#60708a; padding: .75rem .2rem; }
.stTabs [aria-selected="true"] { color:#285fc6 !important; }
div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
.small-muted { color:#748198; font-size:.84rem; }
.status-pill { display:inline-block; padding:.25rem .65rem; border-radius:99px; background:#e6f7f2; color:#087d67; font-weight:700; font-size:.78rem; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_pipeline():
    return LogAnalysisPipeline()

pipeline = get_pipeline()

if "report" not in st.session_state:
    st.session_state.report = None
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None

with st.sidebar:
    st.markdown("## 🛡️ LogSentinel")
    st.caption("AI-powered log intelligence")
    ollama_ok, ollama_status = pipeline.ollama.health()
    st.markdown("### System health")
    st.markdown(f"<span class='status-pill'>{'● Ollama connected' if ollama_ok else '● Ollama offline'}</span>", unsafe_allow_html=True)
    st.caption(f"Model: `{pipeline.config['ollama_model']}`")
    if ollama_ok:
        st.caption("Available: " + ", ".join(ollama_status[:4]))
    else:
        st.warning("AI investigation needs Ollama running. Parsing and analytics remain available.")
    st.divider()
    st.markdown("### 01 · Upload log files")
    uploads = st.file_uploader("Select .log or .txt files", type=["log", "txt"], accept_multiple_files=True, help="You can upload multiple application, database or service logs.")
    analyze_clicked = st.button("Analyze uploaded logs", type="primary", use_container_width=True)
    st.divider()
    st.caption("Local processing · Ollama · Qdrant · SQLite")

st.markdown("""
<div class="hero">
  <div class="eyebrow">OPERATIONS INTELLIGENCE PLATFORM</div>
  <h1>🛡️ AI-Powered Intelligent Log Analysis</h1>
  <p>Turn raw system logs into searchable evidence, anomaly signals and clear incident investigations.</p>
</div>
""", unsafe_allow_html=True)

if analyze_clicked:
    if not uploads:
        st.error("Choose at least one log file before starting analysis.")
    else:
        try:
            named_texts = [(f.name, f.getvalue().decode("utf-8", errors="replace")) for f in uploads]
            with st.spinner("Parsing events · detecting unusual activity · building the searchable log index…"):
                parsed = pipeline.load_logs(named_texts)
                result = pipeline.analyze()
            st.session_state.last_analysis = result
            st.session_state.report = None
            st.success(f"Analysis complete — {len(parsed):,} log events processed and {result['indexed']:,} indexed.")
        except Exception as exc:
            st.error("Analysis could not be completed. Check the error details below.")
            st.exception(exc)

# Welcome / empty state
if pipeline.df is None or pipeline.df.empty:
    left, right = st.columns([1.25, .75])
    with left:
        st.markdown("## Start with your logs")
        st.write("Upload application, database, service or QuestaSim/UVM log files. LogSentinel extracts structured events, identifies unusual activity and makes relevant evidence searchable for AI-assisted investigation.")
        st.markdown("**What you get**")
        st.markdown("- Structured log explorer with severity and component filters\n- Machine-learning anomaly detection\n- Evidence-grounded AI root-cause investigation\n- Downloadable JSON, Markdown and PDF incident reports")
    with right:
        st.markdown("<div class='section-card'><h3>Quick start</h3><p>1. Start Ollama<br>2. Upload logs from the sidebar<br>3. Select <b>Analyze uploaded logs</b><br>4. Open <b>AI Investigation</b> to ask a question</p><p class='small-muted'>Sample files are included in <code>sample_logs/</code>.</p></div>", unsafe_allow_html=True)
    st.stop()

df = pipeline.df.copy()
errors = int(df["level"].isin(["ERROR", "CRITICAL"]).sum())
warnings = int((df["level"] == "WARNING").sum())
uvm_errors = int(((df["event_format"] == "questa_uvm") & df["level"].isin(["ERROR", "CRITICAL"])).sum()) if "event_format" in df else errors
simulator_errors = int(((df["event_format"] == "simulator_diagnostic") & df["level"].isin(["ERROR", "CRITICAL"])).sum()) if "event_format" in df else 0
unique_error_patterns = int(df.loc[df["level"].isin(["ERROR", "CRITICAL"]), "error_category"].replace("", pd.NA).nunique()) if "error_category" in df else 0
has_simulation_time = "simulation_time" in df and df["simulation_time"].notna().any()
has_wall_clock_time = "timestamp" in df and df["timestamp"].notna().any()
is_simulation_log = has_simulation_time and not has_wall_clock_time
anomaly_count = len(pipeline.anomaly_events) if pipeline.anomaly_events is not None else 0

# Metric cards
metric_data = [
    ("LOG EVENTS", f"{len(df):,}", "Structured events", "events"),
    ("ERRORS", f"{errors:,}", "Error events", "errors"),
    ("WARNINGS", f"{warnings:,}", "Warning events", "warnings"),
    ("ANOMALOUS EVENTS", f"{anomaly_count:,}", "Events in flagged windows", "anomalies"),
]
cols = st.columns(4)
for col, (label, value, note, tone) in zip(cols, metric_data):
    with col:
        st.markdown(f"<div class='metric-card {tone}'><div class='metric-label'>{label}</div><div class='metric-value'>{value}</div><div class='metric-note'>{note}</div></div>", unsafe_allow_html=True)

st.write("")
tabs = st.tabs(["Overview", "Log Explorer", "Anomalies", "AI Investigation", "History & Reports"])

with tabs[0]:
    st.markdown("## Operational overview")
    c1, c2 = st.columns(2)
    with c1:
        counts = df["level"].value_counts().rename_axis("Severity").reset_index(name="Events")
        severity_colors = {"ERROR": "#dc3545", "CRITICAL": "#a61e2d", "WARNING": "#f0a323", "INFO": "#3B82F6", "DEBUG": "#0e9f91", "TRACE": "#64748b", "UNKNOWN": "#7c3aed"}
        fig = px.pie(counts, names="Severity", values="Events", hole=.58, color="Severity", color_discrete_map=severity_colors)
        fig.update_layout(title="Severity mix", margin=dict(l=10,r=10,t=50,b=10), height=330, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        by_component = df.groupby("component").size().reset_index(name="Events").sort_values("Events", ascending=True)
        fig = px.bar(by_component, x="Events", y="component", orientation="h", text="Events", color_discrete_sequence=["#6476d9"])
        fig.update_layout(title="Events by component", margin=dict(l=10,r=10,t=50,b=10), height=330, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title="", xaxis_title="Events")
        st.plotly_chart(fig, use_container_width=True)
    if pipeline.window_df is not None and not pipeline.window_df.empty:
        st.markdown("### Error activity over time")
        chart_all = pipeline.window_df.copy()
        chart_groups = []
        if "time_basis" in chart_all:
            if (chart_all["time_basis"] == "simulation").any():
                chart_groups.append(("simulation", "Simulation time (units)"))
            if (chart_all["time_basis"] == "wall_clock").any():
                chart_groups.append(("wall_clock", "Wall-clock time"))
        else:
            chart_groups.append(("simulation" if is_simulation_log else "wall_clock", "Simulation time (units)" if is_simulation_log else "Wall-clock time"))
        for basis, x_title in chart_groups:
            chart = chart_all[chart_all["time_basis"] == basis].copy() if "time_basis" in chart_all else chart_all.copy()
            if basis == "simulation":
                chart["window"] = pd.to_numeric(chart["window"], errors="coerce")
            else:
                chart["window"] = pd.to_datetime(chart["window"], errors="coerce")
            fig = px.line(chart, x="window", y="errors", color="component", markers=True, color_discrete_sequence=["#3267d6", "#10a58f", "#e59b35", "#d94d61"])
            fig.update_layout(height=300, margin=dict(l=10,r=10,t=20,b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title=x_title, yaxis_title="Error count")
            st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Sources analyzed: {df['source'].nunique()} · Components detected: {df['component'].nunique()} · Distinct error patterns: {unique_error_patterns}")
    if getattr(pipeline, "raw_line_count", 0):
        st.caption(f"{pipeline.raw_line_count:,} physical lines scanned · {len(df):,} structured events extracted · {pipeline.ignored_line_count:,} non-event / metadata lines safely ignored.")
    if has_simulation_time:
        st.info(f"QuestaSim/UVM records detected · {int((df['event_format'] == 'questa_uvm').sum()):,} UVM records · {uvm_errors:,} UVM errors · simulation-time analysis enabled.")
    if has_simulation_time and has_wall_clock_time:
        st.caption("Mixed log formats detected. Wall-clock and simulator-time anomaly windows are analyzed separately.")
    error_rows = df[df["level"].isin(["ERROR", "CRITICAL"])].copy()
    if not error_rows.empty and "error_category" in error_rows:
        pattern_table = error_rows.groupby("error_category", dropna=False).agg(occurrences=("event_id", "count"), affected_components=("component", "nunique")).reset_index().sort_values("occurrences", ascending=False)
        pattern_table["error_category"] = pattern_table["error_category"].str.replace("_", " ").str.title()
        pattern_table = pattern_table.rename(columns={"error_category": "Error pattern", "occurrences": "Occurrences", "affected_components": "Affected components"})
        st.markdown("### Error pattern breakdown")
        st.dataframe(pattern_table, use_container_width=True, hide_index=True)

with tabs[1]:
    st.markdown("## Search and explore events")
    f1, f2, f3 = st.columns([1,1,1.3])
    levels = ["All"] + sorted(df["level"].dropna().unique().tolist())
    components = ["All"] + sorted(df["component"].dropna().unique().tolist())
    chosen_level = f1.selectbox("Severity", levels)
    chosen_component = f2.selectbox("Component", components)
    term = f3.text_input("Search message", placeholder="e.g. timeout, retry, HTTP 500")
    view = df.copy()
    if chosen_level != "All":
        view = view[view["level"] == chosen_level]
    if chosen_component != "All":
        view = view[view["component"] == chosen_component]
    if term:
        view = view[view["message"].str.contains(term, case=False, na=False)]
    st.caption(f"Showing {len(view):,} of {len(df):,} events")
    display_view = view.drop(columns=["raw"], errors="ignore").copy()
    if "timestamp" in display_view and display_view["timestamp"].isna().all():
        display_view = display_view.drop(columns=["timestamp"])
    st.dataframe(display_view, use_container_width=True, height=420, hide_index=True)
    st.download_button("⬇ Download filtered logs (CSV)", view.to_csv(index=False).encode("utf-8-sig"), "filtered_logs.csv", "text/csv", key="filtered_csv")

with tabs[2]:
    st.markdown("## Machine-learning anomaly detection")
    st.write("Isolation Forest evaluates component activity in fixed windows using event volume, error count, warning/error rates and distinct error patterns. QuestaSim/UVM files use simulation-time windows; application logs use wall-clock windows.")
    if pipeline.window_df is not None and not pipeline.window_df.empty:
        windows = pipeline.window_df.copy()
        st.dataframe(windows, use_container_width=True, hide_index=True)
        flagged = windows[windows["anomaly"] == True]
        if not flagged.empty:
            st.warning(f"{len(flagged)} unusual component/time windows were flagged. These are investigation signals, not proof of an incident.")
            if pipeline.anomaly_events is not None and not pipeline.anomaly_events.empty:
                st.markdown("### Events inside flagged windows")
                anomaly_display = pipeline.anomaly_events.drop(columns=["raw"], errors="ignore").copy()
                if "timestamp" in anomaly_display and anomaly_display["timestamp"].isna().all():
                    anomaly_display = anomaly_display.drop(columns=["timestamp"])
                st.dataframe(anomaly_display, use_container_width=True, hide_index=True)
        else:
            st.success("No unusual windows were flagged by the current model settings.")
    else:
        st.info("No valid wall-clock timestamps or simulator-time values were found, so time-window anomaly detection is unavailable for these logs.")

with tabs[3]:
    st.markdown("## Investigate an incident")
    st.write("Ask a question in plain language. The agent retrieves relevant log evidence and asks the local Ollama model to explain what the evidence supports.")
    question_hint = "Which UVM error patterns occur, which components are affected, and what does the evidence suggest?" if has_simulation_time else "Why did the service fail? Identify the likely cause and supporting log events."
    question = st.text_area("Investigation question", placeholder=question_hint, height=105)
    if st.button("Run AI investigation", type="primary", key="run_investigation"):
        if not question.strip():
            st.warning("Enter an investigation question first.")
        else:
            try:
                with st.spinner("Retrieving evidence and generating the incident analysis…"):
                    st.session_state.report = pipeline.ask(question.strip())
            except Exception as exc:
                st.error("The investigation could not be completed.")
                st.exception(exc)
    report = st.session_state.report
    if report:
        st.divider()
        st.markdown("### Investigation report")
        st.markdown(f"<span class='status-pill'>{'AI-generated analysis' if report['ai_used'] else 'Evidence-based fallback'}</span>", unsafe_allow_html=True)
        st.markdown(report["summary"])
        st.markdown("### Retrieved evidence")
        if report.get("evidence"):
            evidence_df = pd.DataFrame(report["evidence"])
            st.dataframe(evidence_df.drop(columns=["raw","text"], errors="ignore"), use_container_width=True, hide_index=True)
        else:
            st.info("No relevant log evidence was retrieved for this question.")
        st.markdown("### Incident timeline")
        if report.get("timeline"):
            st.dataframe(pd.DataFrame(report["timeline"]), use_container_width=True, hide_index=True)
        # Downloads are generated directly from report data, avoiding file-handle/path issues.
        try:
            files = build_report_files(report)
            save_report_files(report)  # also retain a local copy under output_report/
            st.markdown("### Export investigation")
            d1, d2, d3 = st.columns(3)
            d1.download_button("⬇ JSON report", files["json"], files["json_name"], "application/json", use_container_width=True)
            d2.download_button("⬇ Markdown report", files["markdown"], files["markdown_name"], "text/markdown", use_container_width=True)
            d3.download_button("⬇ PDF report", files["pdf"], files["pdf_name"], "application/pdf", use_container_width=True)
            st.caption("A copy is also saved in the project's output_report folder.")
        except Exception as exc:
            st.error(f"Report export could not be prepared: {exc}")

with tabs[4]:
    st.markdown("## Investigation history")
    history = pipeline.db.history()
    if history:
        history_df = pd.DataFrame(history, columns=["ID", "Created at", "Question", "Summary"])
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        st.caption("Investigation history is stored locally in SQLite.")
    else:
        st.info("No investigations have been saved yet. Run an AI investigation to create the first history entry.")

st.markdown("<div style='text-align:center;color:#8b97aa;font-size:.78rem;padding:2rem 0 0'>LogSentinel · Local AI log analysis · Built with Streamlit, Qdrant, Sentence Transformers and Ollama</div>", unsafe_allow_html=True)
