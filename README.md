# AI-Powered Intelligent Log Analysis Agent

A local, student-friendly minor project that combines structured log parsing, machine-learning anomaly detection, semantic retrieval (RAG), and Ollama-powered incident investigation.

## Main features

- Upload multiple `.log` and `.txt` files.
- Parse conventional application logs and QuestaSim/SystemVerilog UVM records, including severity, source file, source line, UVM component hierarchy, report ID and simulation time.
- Ignore unstructured simulator banners, blank lines and UVM summary-count rows instead of incorrectly counting them as events.
- Group repeated error occurrences into normalized error patterns while preserving each individual event.
- Explore logs with severity/component filters and keyword search.
- Detect unusual component/time-window activity using Isolation Forest. Conventional logs use wall-clock windows; UVM logs use simulation-time windows.
- Embed log events with `sentence-transformers/all-MiniLM-L6-v2` and index them in local Qdrant.
- Ask incident questions using retrieved log evidence and a local Ollama model (default: `llama3.2`).
- Save investigation history in SQLite.
- Download investigation reports as JSON, Markdown and PDF; local copies are saved in `output_report/`.

## Requirements

- Windows 10/11, 64-bit
- Python 3.11 (recommended; tested target)
- Ollama for local LLM investigation
- Internet for the first download of the embedding model (afterward it is cached)

## Setup (PowerShell in VS Code)

Open this project folder (the folder containing `app.py` and `requirements.txt`) in VS Code.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, either use a Command Prompt terminal and run `.venv\Scripts\activate.bat`, or allow local scripts for your Windows user with `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` (subject to device policy).

Install Ollama from https://ollama.com/download, then run:

```powershell
ollama pull llama3.2
ollama list
```

Ollama normally runs as a background service on `http://localhost:11434`.

## Run the dashboard

```powershell
streamlit run app.py
```

Upload the three service samples from `sample_logs/` to try conventional application logs, or upload `sample_logs/main_testing_logs.log` to try the included QuestaSim/UVM example. Click **Analyze uploaded logs**. Open **AI Investigation**, ask a question about the error patterns or affected components, and click **Run AI investigation**. Download the JSON, Markdown or PDF report from the result section.

## Run tests

```powershell
pytest -v
```

The automated tests cover conventional log parsing, UVM parsing, noise filtering, simulation-time anomaly detection and report generation/export. The full live RAG workflow additionally requires the embedding model to be downloaded and Ollama running.

## Project structure

```text
AI_Log_Analysis_Agent/
├── app.py
├── api.py
├── config.json
├── requirements.txt
├── log_agent/
│   ├── parser.py
│   ├── anomaly.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── investigator.py
│   ├── pipeline.py
│   ├── reporting.py
│   ├── database.py
│   └── ...
├── sample_logs/
├── tests/
├── storage/          # created automatically
└── output_report/    # created when reports are exported
```

## QuestaSim / UVM parsing notes

The included internship-style simulation log has 17,591 physical lines. The parser extracts structured records rather than treating every physical line as an event. For this fixture, validation produces:

- 3,534 UVM_INFO records
- 110 UVM_ERROR records
- 0 UVM_WARNING and 0 UVM_FATAL records
- 14 separate explicit QuestaSim diagnostic lines
- 3,658 structured events total (3,644 UVM records plus 14 simulator diagnostics)

The 110 UVM errors are grouped into four recurring UVM error categories: scoreboard packet-not-found, single-bit LLP header, double-bit LLP header and double-bit decoder. The 14 QuestaSim diagnostics form a separate coverage/illegal-bin category, so the combined dashboard shows 124 error-severity occurrences across five normalized patterns. Occurrences are not the same as unique error patterns.

Simulation timestamps such as `@ 947000` are kept as simulator time units; they are not converted into calendar dates. Isolation Forest analyzes component activity in fixed simulation-time windows. A flagged window is a statistical signal, not proof of a defect. The included fixture is used by an automated parser/anomaly regression test.

## Notes and limitations

- Anomaly flags are statistical signals, not proof that a real incident occurred. Small datasets can produce unstable anomaly scores; interpret them with the underlying events.
- The AI's root-cause suggestions are hypotheses supported by retrieved logs, not guaranteed diagnoses. Verify them against the actual system.
- The app runs locally. Log files, the vector index and incident history remain on the machine unless the user exports them.
- If Ollama is unavailable, the app still parses and analyzes logs and provides a deterministic fallback summary; AI-generated investigation requires Ollama.
