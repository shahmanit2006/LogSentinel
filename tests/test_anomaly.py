import pandas as pd
from log_agent.anomaly import detect_anomalies

def test_anomaly_module_handles_empty_data():
    windows, events = detect_anomalies(pd.DataFrame())
    assert windows.empty
    assert events.empty


def test_anomaly_detector_supports_mixed_wall_clock_and_simulation_time():
    import pandas as pd
    from log_agent.anomaly import detect_anomalies
    rows = []
    for i in range(12):
        rows.append({
            "event_id": f"wall-{i}", "timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=i),
            "simulation_time": None, "level": "ERROR" if i == 11 else "INFO",
            "component": "api", "error_category": "timeout" if i == 11 else "", "message": "wall event",
        })
        rows.append({
            "event_id": f"sim-{i}", "timestamp": pd.NaT, "simulation_time": i * 10000,
            "level": "ERROR" if i == 11 else "INFO", "component": "uvm_monitor",
            "error_category": "ecc" if i == 11 else "", "message": "simulation event",
        })
    windows, events = detect_anomalies(pd.DataFrame(rows))
    assert set(windows["time_basis"]) == {"simulation", "wall_clock"}
    assert set(events["time_basis"]).issubset({"simulation", "wall_clock"})
