import re
import hashlib
from pathlib import PurePosixPath, Path
import pandas as pd

# Strict parsers: only structured log records become events. This prevents simulator
# banners, source comments, blank lines and report-summary rows being counted as logs.
STANDARD_PATTERNS = [
    re.compile(r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z)?)\s+(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\s+(?:\[(?P<component>[^\]]+)\]\s*)?(?P<message>.*)$', re.I),
    re.compile(r'^\[(?P<timestamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\]\s+(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\s+(?P<message>.*)$', re.I),
    re.compile(r'^(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})[, ]+(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)[, ]+(?P<message>.*)$', re.I),
    re.compile(r'^\[(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL)\]\s*(?:\[(?P<component>[^\]]+)\])?\s*(?P<message>.*)$', re.I),
]
UVM_RE = re.compile(
    r'^#?\s*(?P<uvm_level>UVM_INFO|UVM_WARNING|UVM_ERROR|UVM_FATAL)\s+'
    r'(?:(?P<file>\S+?)\((?P<source_line>\d+)\)\s+)?'
    r'@\s*(?P<sim_time>\d+)\s*:\s*(?P<hierarchy>\S+)\s+'
    r'\[(?P<uvm_id>[^\]]+)\]\s*(?P<message>.*)$', re.I
)
# UVM's short reporter form: # UVM_INFO @ 0: reporter [RNTST] ...
UVM_SHORT_RE = re.compile(
    r'^#?\s*(?P<uvm_level>UVM_INFO|UVM_WARNING|UVM_ERROR|UVM_FATAL)\s+'
    r'@\s*(?P<sim_time>\d+)\s*:\s*(?P<hierarchy>\S+)\s+'
    r'\[(?P<uvm_id>[^\]]+)\]\s*(?P<message>.*)$', re.I
)
SIM_RE = re.compile(r'^#?\s*\*\*\s*(?P<level>Error|Warning|Fatal):\s*(?P<message>.*)$', re.I)
LEVEL_MAP = {"WARN": "WARNING", "FATAL": "CRITICAL", "UVM_INFO": "INFO", "UVM_WARNING": "WARNING", "UVM_ERROR": "ERROR", "UVM_FATAL": "CRITICAL"}


def _error_category(message, uvm_id=""):
    text = f"{uvm_id} {message}".lower()
    if "packet is not-found" in text or "packet not found" in text:
        return "scoreboard_packet_not_found"
    if "double bit error in llp-hdr" in text or "double bit error in llp header" in text:
        return "double_bit_llp_header"
    if "single bit error in llp-hdr" in text or "single bit corrected error" in text:
        return "single_bit_llp_header"
    if "double bit error detected in the data" in text or "decoder" in uvm_id.lower() and "dbl" in uvm_id.lower():
        return "double_bit_decoder"
    if "illegal state bin" in text or "illegal bin" in text:
        return "coverage_illegal_bin"
    if "timeout" in text:
        return "timeout"
    return "other_error" if text.strip() else ""


def _record(source, line_no, raw, level, message, component="unknown", timestamp=pd.NaT,
            simulation_time=None, hierarchy="", uvm_id="", event_format="standard", error_category=""):
    event_id = hashlib.sha1(f"{source}|{line_no}|{raw}".encode("utf-8", errors="ignore")).hexdigest()
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "simulation_time": int(simulation_time) if simulation_time is not None else None,
        "level": level,
        "component": component or "unknown",
        "hierarchy": hierarchy,
        "uvm_id": uvm_id,
        "error_category": error_category,
        "event_format": event_format,
        "message": message.strip() if message else raw,
        "raw": raw,
        "source": str(source),
        "line_no": int(line_no),
    }


def _parse_line(line, source, line_no):
    raw = line.strip()
    if not raw:
        return None

    # UVM structured report record (QuestaSim / SystemVerilog UVM).
    match = UVM_RE.match(raw) or UVM_SHORT_RE.match(raw)
    if match:
        data = match.groupdict()
        uvm_level = data["uvm_level"].upper()
        level = LEVEL_MAP[uvm_level]
        hierarchy = data.get("hierarchy") or "reporter"
        source_file = data.get("file") or ""
        component = Path(source_file).stem if source_file else (hierarchy.split(".")[-1].strip() or "reporter")
        message = data.get("message") or ""
        uvm_id = data.get("uvm_id") or ""
        sim_time = int(data["sim_time"])
        return _record(
            source, line_no, raw, level, message, component=component,
            simulation_time=sim_time, hierarchy=hierarchy, uvm_id=uvm_id,
            event_format="questa_uvm", error_category=_error_category(message, uvm_id) if level in ("ERROR", "CRITICAL") else "",
        )

    # Conventional application/service formats.
    for pattern in STANDARD_PATTERNS:
        match = pattern.match(raw)
        if match:
            data = match.groupdict()
            ts_text = (data.get("timestamp") or "").replace(",", ".")
            try:
                timestamp = pd.to_datetime(ts_text.rstrip("Z"), errors="coerce") if ts_text else pd.NaT
            except Exception:
                timestamp = pd.NaT
            level = (data.get("level") or "UNKNOWN").upper()
            level = LEVEL_MAP.get(level, level)
            component = data.get("component") or _infer_component(source)
            message = data.get("message") or raw
            return _record(source, line_no, raw, level, message, component, timestamp,
                           event_format="standard", error_category=_error_category(message) if level in ("ERROR", "CRITICAL") else "")

    # Explicit Questa simulator diagnostics are separate from UVM report counts.
    sim_match = SIM_RE.match(raw)
    if sim_match:
        level = LEVEL_MAP.get(sim_match.group("level").upper(), sim_match.group("level").upper())
        message = sim_match.group("message")
        return _record(source, line_no, raw, level, message, component="QuestaSim",
                       event_format="simulator_diagnostic", error_category=_error_category(message) if level in ("ERROR", "CRITICAL") else "")

    return None


def _infer_component(source):
    s = str(source).lower()
    for name in ("database", "payment", "auth", "application", "app", "api", "server", "network"):
        if name in s:
            return name
    return "unknown"


def parse_text(text, source="uploaded.log"):
    rows = []
    for i, line in enumerate(text.splitlines(), start=1):
        row = _parse_line(line, source, i)
        if row is not None:
            rows.append(row)
    columns = ["event_id", "timestamp", "simulation_time", "level", "component", "hierarchy",
               "uvm_id", "error_category", "event_format", "message", "raw", "source", "line_no"]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["simulation_time"] = pd.to_numeric(df["simulation_time"], errors="coerce")
    for col in ("level", "component", "message", "source", "event_format"):
        df[col] = df[col].fillna("UNKNOWN" if col == "level" else "").astype(str)
    return df


def parse_files(uploaded_files):
    frames = []
    for uploaded in uploaded_files:
        data = uploaded.getvalue()
        text = data.decode("utf-8", errors="replace")
        frames.append(parse_text(text, uploaded.name))
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
