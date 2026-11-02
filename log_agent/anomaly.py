import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest


def _fit_flags(grouped, feature_cols, contamination):
    X = grouped[feature_cols].replace([np.inf, -np.inf], 0).fillna(0)
    if len(grouped) < 5 or (X.nunique() <= 1).all():
        grouped["anomaly"] = False
        grouped["anomaly_score"] = 0.0
        return grouped
    model = IsolationForest(
        n_estimators=200,
        contamination=min(max(float(contamination), 0.01), 0.20),
        random_state=42,
    )
    grouped["anomaly"] = model.fit_predict(X) == -1
    grouped["anomaly_score"] = -model.score_samples(X)
    return grouped


def detect_anomalies(df, contamination=0.08, bin_minutes=5, simulation_bin=25000):
    """Detect unusual activity in wall-clock or simulator-time windows.

    UVM records often have no calendar timestamp; their integer simulation time is
    used directly. The returned window column is numeric for simulation logs and
    datetime for conventional service logs.
    """
    empty = pd.DataFrame()
    if df is None or df.empty:
        return empty, empty
    work = df.copy()
    if "simulation_time" not in work:
        work["simulation_time"] = np.nan
    work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work["simulation_time"] = pd.to_numeric(work["simulation_time"], errors="coerce")
    has_sim = work["simulation_time"].notna().any()
    has_wall = work["timestamp"].notna().any()
    if has_sim and has_wall:
        sim_windows, sim_events = detect_anomalies(work[work["simulation_time"].notna()].copy(), contamination, bin_minutes, simulation_bin)
        wall_windows, wall_events = detect_anomalies(work[work["timestamp"].notna()].copy(), contamination, bin_minutes, simulation_bin)
        if not sim_windows.empty:
            sim_windows["time_basis"] = "simulation"
        if not wall_windows.empty:
            wall_windows["time_basis"] = "wall_clock"
        if not sim_events.empty:
            sim_events["time_basis"] = "simulation"
        if not wall_events.empty:
            wall_events["time_basis"] = "wall_clock"
        return pd.concat([sim_windows, wall_windows], ignore_index=True, sort=False), pd.concat([sim_events, wall_events], ignore_index=True, sort=False)
    is_sim = has_sim

    work["is_error"] = work["level"].isin(["ERROR", "CRITICAL"]).astype(int)
    work["is_warning"] = work["level"].isin(["WARNING"]).astype(int)

    if is_sim:
        valid = work.dropna(subset=["simulation_time"]).copy()
        if valid.empty:
            return empty, empty
        width = max(int(simulation_bin), 1)
        valid["window"] = (valid["simulation_time"] // width * width).astype("int64")
        valid["window_label"] = valid["window"].map(lambda x: f"{int(x):,}–{int(x)+width:,}")
        group_cols = ["component", "window"]
        grouped = valid.groupby(group_cols, dropna=False).agg(
            total_logs=("event_id", "count"), errors=("is_error", "sum"),
            warnings=("is_warning", "sum"),
            unique_error_patterns=("error_category", lambda s: s[s.astype(str).ne("")].nunique()),
        ).reset_index()
        grouped["window_label"] = grouped["window"].map(lambda x: f"{int(x):,}–{int(x)+width:,}")
        grouped["time_basis"] = "simulation"
        grouped["error_rate"] = grouped["errors"] / grouped["total_logs"].clip(lower=1)
        grouped["warning_rate"] = grouped["warnings"] / grouped["total_logs"].clip(lower=1)
        grouped = _fit_flags(grouped, ["total_logs", "errors", "warnings", "error_rate", "warning_rate", "unique_error_patterns"], contamination)
        bad = grouped[grouped["anomaly"]][["component", "window"]]
        events = valid.merge(bad, on=["component", "window"], how="inner") if not bad.empty else valid.iloc[0:0].copy()
        return grouped.sort_values(["window", "component"]), events.sort_values("simulation_time")

    valid = work.dropna(subset=["timestamp"]).copy()
    if valid.empty:
        return empty, empty
    valid["window"] = valid["timestamp"].dt.floor(f"{max(int(bin_minutes), 1)}min")
    grouped = valid.groupby(["component", "window"], dropna=False).agg(
        total_logs=("event_id", "count"), errors=("is_error", "sum"),
        warnings=("is_warning", "sum"),
        unique_error_patterns=("error_category", lambda s: s[s.astype(str).ne("")].nunique()),
    ).reset_index()
    grouped["error_rate"] = grouped["errors"] / grouped["total_logs"].clip(lower=1)
    grouped["warning_rate"] = grouped["warnings"] / grouped["total_logs"].clip(lower=1)
    grouped["time_basis"] = "wall_clock"
    grouped = _fit_flags(grouped, ["total_logs", "errors", "warnings", "error_rate", "warning_rate", "unique_error_patterns"], contamination)
    bad = grouped[grouped["anomaly"]][["component", "window"]]
    events = valid.merge(bad, on=["component", "window"], how="inner") if not bad.empty else valid.iloc[0:0].copy()
    return grouped.sort_values("window"), events.sort_values("timestamp")
