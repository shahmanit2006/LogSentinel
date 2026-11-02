from pathlib import Path
import pandas as pd

from .config import load_config
from .parser import parse_text
from .anomaly import detect_anomalies
from .vector_store import LocalLogVectorStore
from .ollama_client import OllamaClient
from .investigator import investigate
from .database import IncidentDB
from .analysis import summarize_logs


class LogAnalysisPipeline:
    def __init__(self):
        self.config = load_config()
        self.df = None
        self.raw_line_count = 0
        self.ignored_line_count = 0
        self.window_df = None
        self.anomaly_events = None
        self.vector_store = None
        self.ollama = OllamaClient(self.config["ollama_base_url"], self.config["ollama_model"])
        self.db = IncidentDB(self.config["sqlite_path"])

    def load_logs(self, named_texts):
        self.raw_line_count = sum(len(text.splitlines()) for _, text in named_texts)
        frames = [parse_text(text, name) for name, text in named_texts]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            raise ValueError("No log entries were found in the uploaded files. Check the file contents and format.")
        self.df = pd.concat(frames, ignore_index=True)
        # Remove exact duplicate source-line events but preserve same messages from different files.
        self.df = self.df.drop_duplicates(subset=["event_id"]).reset_index(drop=True)
        self.ignored_line_count = max(self.raw_line_count - len(self.df), 0)
        return self.df

    def analyze(self):
        if self.df is None or self.df.empty:
            raise ValueError("Upload and parse log files first.")
        cfg = self.config
        self.window_df, self.anomaly_events = detect_anomalies(
            self.df,
            contamination=cfg["anomaly_contamination"],
            bin_minutes=cfg["time_bin_minutes"],
            simulation_bin=cfg.get("simulation_time_bin", 25000),
        )
        # Use a fresh local collection for each upload so old log batches cannot
        # leak into a new investigation or produce stale retrieval results.
        if self.vector_store is not None:
            try:
                self.vector_store.close()
            except Exception:
                pass
            self.vector_store = None
        self.vector_store = LocalLogVectorStore(
            cfg["qdrant_path"], cfg["collection_name"], cfg["embedding_model"], reset=True
        )
        indexed = self.vector_store.index_dataframe(self.df)
        return {
            "statistics": summarize_logs(self.df),
            "windows": self.window_df,
            "anomaly_events": self.anomaly_events,
            "indexed": indexed,
        }

    def ask(self, question):
        if self.df is None or self.vector_store is None:
            raise ValueError("Analyze uploaded logs before starting an investigation.")
        report = investigate(
            question, self.vector_store, self.ollama, self.window_df,
            self.df, top_k=self.config["top_k"]
        )
        self.db.save(question, report)
        return report
