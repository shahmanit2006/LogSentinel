from collections import Counter
import pandas as pd


def summarize_logs(df):
    if df is None or df.empty:
        return {"total_logs": 0, "errors": 0, "warnings": 0, "components": 0, "levels": {}, "unique_error_patterns": 0, "event_formats": {}}
    counts = Counter(df["level"].astype(str).str.upper())
    errors = df[df["level"].isin(["ERROR", "CRITICAL"])]
    patterns = errors.get("error_category", pd.Series(dtype=str)).astype(str)
    patterns = patterns[patterns.ne("")]
    formats = Counter(df.get("event_format", pd.Series(["standard"] * len(df))).astype(str))
    uvm_errors = int(((df.get("event_format", pd.Series(index=df.index, dtype=str)) == "questa_uvm") & df["level"].isin(["ERROR", "CRITICAL"])).sum())
    simulator_errors = int(((df.get("event_format", pd.Series(index=df.index, dtype=str)) == "simulator_diagnostic") & df["level"].isin(["ERROR", "CRITICAL"])).sum())
    return {
        "total_logs": int(len(df)),
        "errors": int(counts.get("ERROR", 0) + counts.get("CRITICAL", 0)),
        "warnings": int(counts.get("WARNING", 0)),
        "components": int(df["component"].nunique()),
        "levels": dict(counts),
        "unique_error_patterns": int(patterns.nunique()),
        "uvm_errors": uvm_errors,
        "simulator_errors": simulator_errors,
        "event_formats": dict(formats),
    }


def build_timeline(df, limit=200):
    if df is None or df.empty:
        return []
    data = df.copy()
    if "simulation_time" not in data:
        data["simulation_time"] = pd.NA
    if "timestamp" not in data:
        data["timestamp"] = pd.NaT
    data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")
    data["simulation_time"] = pd.to_numeric(data["simulation_time"], errors="coerce")
    records = []
    sim = data.dropna(subset=["simulation_time"]).sort_values("simulation_time").tail(limit)
    for r in sim.itertuples():
        records.append({
            "simulation_time": int(r.simulation_time), "time_basis": "simulation units",
            "level": str(r.level), "component": str(r.component), "message": str(r.message),
            "source": str(r.source), "line_no": int(r.line_no),
        })
    wall = data.dropna(subset=["timestamp"]).sort_values("timestamp").tail(limit)
    for r in wall.itertuples():
        records.append({
            "timestamp": str(r.timestamp), "time_basis": "wall clock",
            "level": str(r.level), "component": str(r.component), "message": str(r.message),
            "source": str(r.source), "line_no": int(r.line_no),
        })
    return records[-limit:]
