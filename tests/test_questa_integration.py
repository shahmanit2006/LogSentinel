from pathlib import Path
from log_agent.parser import parse_text
from log_agent.analysis import summarize_logs
from log_agent.anomaly import detect_anomalies


def test_real_questa_log_counts_and_simulation_time_anomalies():
    log_path = Path(__file__).parent.parent / "sample_logs" / "main_testing_logs.log"
    if not log_path.exists():
        return
    df = parse_text(log_path.read_text(encoding="utf-8", errors="replace"), log_path.name)
    stats = summarize_logs(df)
    assert stats["levels"].get("INFO") == 3534
    assert stats["levels"].get("ERROR") == 124  # 110 UVM + 14 explicit Questa diagnostics
    assert stats["warnings"] == 0
    assert stats["unique_error_patterns"] == 5
    assert df["simulation_time"].notna().any()
    assert df["component"].ne("unknown").all()
    windows, anomalous_events = detect_anomalies(df)
    assert not windows.empty
    assert windows["anomaly"].any()
    assert not anomalous_events.empty
