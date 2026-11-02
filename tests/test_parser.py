from log_agent.parser import parse_text

def test_parser_extracts_fields():
    text = "2026-10-31 10:00:00 ERROR [database] connection timeout"
    df = parse_text(text, "database.log")
    assert len(df) == 1
    assert df.iloc[0]["level"] == "ERROR"
    assert df.iloc[0]["component"] == "database"
    assert "timeout" in df.iloc[0]["message"]

def test_parser_ignores_unstructured_noise():
    df = parse_text("some unusual line without timestamp", "misc.log")
    assert df.empty


def test_questa_uvm_parser_recognizes_severity_component_and_sim_time():
    from log_agent.parser import parse_text
    sample = """# UVM_ERROR /sim/monitor.sv(451) @ 295000: uvm_test_top.env.rx_mon [rx_monitor - LLP-HDR ERROR] SINGLE BIT ERROR IN LLP-HDR DETECTED
# UVM_INFO @ 0: reporter [RNTST] Running test demo...
# UVM_WARNING :    0
"""
    df = parse_text(sample, "questa.log")
    assert len(df) == 2  # report summary is metadata, not an event
    assert df.iloc[0]["level"] == "ERROR"
    assert df.iloc[0]["simulation_time"] == 295000
    assert df.iloc[0]["component"] == "monitor"
    assert df.iloc[0]["error_category"] == "single_bit_llp_header"
    assert df.iloc[1]["level"] == "INFO"
    assert df.iloc[1]["component"] == "reporter"


def test_parser_ignores_unstructured_simulator_banner_lines():
    from log_agent.parser import parse_text
    sample = """# Questa Sim-64
# Start time: 17:14:03 on Jun 08, 2026
# UVM Report Summary
# UVM_INFO : 12
"""
    assert parse_text(sample, "questa.log").empty
