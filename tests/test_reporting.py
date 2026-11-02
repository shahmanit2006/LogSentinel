import json
from log_agent.reporting import build_report_files, save_report_files


def sample_report():
    return {
        "question": "Why did the payment service fail?",
        "summary": "## Incident summary\nThe logs indicate a database timeout before the payment failure.\n\n## Confidence\nMedium — multiple related events support this hypothesis.",
        "ai_used": True,
        "statistics": {"total_logs": 3, "errors": 2, "warnings": 1},
        "evidence": [{"timestamp": "2026-10-31 10:00:05", "level": "ERROR", "component": "database", "message": "Connection timeout", "source": "database.log", "line_no": 2}],
        "timeline": [],
        "anomalies": [],
    }


def test_report_files_are_created_in_memory():
    files = build_report_files(sample_report())
    assert files["json"].startswith(b"{")
    assert b"payment service fail" in files["markdown"]
    assert files["pdf"].startswith(b"%PDF")
    json.loads(files["json"].decode("utf-8"))


def test_report_files_are_saved(tmp_path):
    paths = save_report_files(sample_report(), tmp_path)
    assert len(paths) == 3
    assert all(path.exists() and path.stat().st_size > 100 for path in paths)
