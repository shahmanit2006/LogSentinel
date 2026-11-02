from collections import Counter
import pandas as pd
from .analysis import build_timeline

SYSTEM_PROMPT = """You are a careful site reliability engineering assistant.
Use only the supplied log evidence. Separate observed facts from hypotheses.
Never claim a root cause is certain unless the evidence proves it.
If evidence is insufficient, say so. Give practical, safe diagnostic steps.
Do not invent log entries, metrics, services, or infrastructure details.
Use clear headings and concise language. State confidence once, at the end."""


def _fallback_report(question, evidence, anomalies, stats):
    error_rows = [e for e in evidence if str(e.get("level", "")).upper() in ("ERROR", "CRITICAL")]
    components = Counter(e.get("component", "unknown") for e in error_rows)
    likely = components.most_common(1)[0][0] if components else "undetermined"
    return (
        "## Incident summary\nAI model unavailable; this is a deterministic summary of the available evidence.\n\n"
        f"**Question:** {question}\n\n"
        f"**Observed statistics:** {stats.get('total_logs', 0)} events, {stats.get('errors', 0)} errors and "
        f"{stats.get('warnings', 0)} warnings across {stats.get('unique_error_patterns', 0)} distinct error patterns.\n\n"
        f"**Most represented error component in the evidence:** {likely}.\n\n"
        f"**Anomalous windows flagged:** {len(anomalies)}.\n\n"
        "## Possible interpretation\nThe component above has the largest number of supporting error events in the supplied evidence. "
        "This is an investigation lead, not proof of root cause. Review the timestamped evidence and check related dependencies.\n\n"
        "## Recommended checks\n1. Compare errors across components by timestamp or simulation time.\n"
        "2. Check dependency availability and connection timeouts where the logs indicate them.\n"
        "3. Verify retry behavior and service recovery events.\n\n"
        "## Confidence\nLow — the local language model was unavailable, so no causal conclusion is asserted."
    )


def _records(frame, limit=20):
    if frame is None or frame.empty:
        return []
    return frame.tail(limit).where(pd.notna(frame), None).to_dict("records")


def investigate(question, vector_store, ollama, anomaly_windows, df, top_k=8):
    """Investigate only against events belonging to the currently loaded DataFrame."""
    if df is None or df.empty:
        raise ValueError("There are no current log events to investigate.")

    # Build an allow-list from the current upload. This protects against stale
    # points in a persistent Qdrant collection or results from an earlier batch.
    current_ids = set(df["event_id"].astype(str)) if "event_id" in df.columns else set()
    current_keys = {
        (str(row.get("source", "")), int(row.get("line_no", -1)))
        for row in df.to_dict("records")
    }

    retrieved = vector_store.search(question, top_k=top_k)
    evidence = []
    seen = set()
    for item in retrieved:
        event_id = str(item.get("event_id", ""))
        source_key = (str(item.get("source", "")), int(item.get("line_no", -1)))
        belongs_to_current_upload = (
            event_id in current_ids if event_id and current_ids
            else source_key in current_keys
        )
        if not belongs_to_current_upload:
            continue
        key = event_id or source_key
        if key not in seen:
            evidence.append(item)
            seen.add(key)

    # Add severe events from the current DataFrame as deterministic supporting
    # evidence. These rows cannot come from an older Qdrant batch.
    levels = df["level"].astype(str).str.upper()
    severe = df[levels.isin(["ERROR", "CRITICAL", "WARNING"])].copy()
    if not severe.empty:
        sort_col = (
            "simulation_time"
            if "simulation_time" in severe and pd.to_numeric(severe["simulation_time"], errors="coerce").notna().any()
            else "timestamp"
        )
        if sort_col == "simulation_time":
            severe[sort_col] = pd.to_numeric(severe[sort_col], errors="coerce")
        else:
            severe[sort_col] = pd.to_datetime(severe[sort_col], errors="coerce")
        severe = severe.sort_values(sort_col, na_position="last")
        for row in severe.to_dict("records"):
            row_id = str(row.get("event_id", ""))
            if row_id not in seen and len(evidence) < max(int(top_k), 12):
                evidence.append(row)
                seen.add(row_id)

    error_mask = levels.isin(["ERROR", "CRITICAL"])
    stats = {
        "total_logs": int(len(df)),
        "errors": int(error_mask.sum()),
        "warnings": int(levels.eq("WARNING").sum()),
        "unique_error_patterns": (
            int(df.loc[error_mask, "error_category"].fillna("").astype(str).replace("", pd.NA).nunique())
            if "error_category" in df else 0
        ),
        "uvm_errors": (
            int(((df.get("event_format", pd.Series("", index=df.index)).astype(str) == "questa_uvm") & error_mask).sum())
            if "event_format" in df else 0
        ),
        "simulator_errors": (
            int(((df.get("event_format", pd.Series("", index=df.index)).astype(str) == "simulator_diagnostic") & error_mask).sum())
            if "event_format" in df else 0
        ),
        "components": int(df["component"].nunique()) if "component" in df else 0,
    }

    # anomaly_windows is the grouped window-level output from detect_anomalies.
    # anomaly_events contains individual log rows and must not be used here:
    # those rows do not have total_logs/errors/warnings/anomaly_score fields.
    if anomaly_windows is not None and not anomaly_windows.empty and "anomaly" in anomaly_windows:
        flagged = anomaly_windows[anomaly_windows["anomaly"].fillna(False).astype(bool)].copy()
    else:
        flagged = pd.DataFrame()
    anomaly_records = _records(flagged, limit=20)

    evidence_text = "\n".join(
        f"- [timestamp={e.get('timestamp', 'n/a')} simulation_time={e.get('simulation_time', 'n/a')}] "
        f"{e.get('level')} component={e.get('component')} uvm_id={e.get('uvm_id', '')} "
        f"error_category={e.get('error_category', '')} source={e.get('source')} "
        f"line={e.get('line_no')}: {e.get('message')}"
        for e in evidence[:20]
    ) or "No matching log evidence was retrieved from the current upload."

    anomaly_text = "\n".join(
        f"- [window={a.get('window_label', a.get('window', 'n/a'))}] "
        f"time_basis={a.get('time_basis', 'n/a')} component={a.get('component', 'unknown')} "
        f"total_logs={a.get('total_logs', 'n/a')} errors={a.get('errors', 'n/a')} "
        f"warnings={a.get('warnings', 'n/a')} unique_error_patterns={a.get('unique_error_patterns', 'n/a')} "
        f"anomaly_score={a.get('anomaly_score', 'n/a')}"
        for a in anomaly_records
    ) or "No component/time windows were flagged as anomalous."

    prompt = f"""Investigate this operational question: {question}

Observed statistics calculated from the CURRENT upload: {stats}

Retrieved log evidence from the CURRENT upload only (cite source and line number):
{evidence_text}

Flagged anomaly windows calculated from the CURRENT upload (these are investigation signals, not proof of root cause):
{anomaly_text}

Rules:
- Use only the statistics and evidence above.
- Do not refer to files, UVM events, components, or records that are not listed above.
- Do not treat an anomaly score as a probability.
- If no anomaly windows are flagged, state that clearly.
- Distinguish directly observed facts from possible explanations.
- Cite the supplied source filename and line number for log claims.
- Do not invent evidence or fill missing values with guesses.

Write a concise incident report with these headings:
## Incident summary
## Observed facts
## Possible root causes (ranked hypotheses with evidence)
## Impact assessment
## Recommended diagnostic/remediation steps
## Missing evidence
## Confidence

For UVM logs, use simulator time and cite source files, line numbers and UVM report IDs."""

    try:
        answer = ollama.generate(prompt, SYSTEM_PROMPT)
        if not answer or not answer.strip():
            raise RuntimeError("Ollama returned an empty response")
        ai_used = True
    except Exception:
        answer = _fallback_report(question, evidence, anomaly_records, stats)
        ai_used = False

    return {
        "question": question,
        "summary": answer,
        "ai_used": ai_used,
        "statistics": stats,
        "evidence": evidence[:20],
        "anomalies": anomaly_records,
        "timeline": build_timeline(df, limit=200),
    }
