"""Optional FastAPI interface. The Streamlit app works independently."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from log_agent.pipeline import LogAnalysisPipeline

app = FastAPI(title="AI Log Analysis Agent API", version="1.0.0")
pipeline = LogAnalysisPipeline()

class InvestigationRequest(BaseModel):
    question: str

@app.get("/health")
def health():
    ok, details = pipeline.ollama.health()
    return {"status": "ok", "ollama_connected": ok, "ollama_details": details}

@app.post("/investigate")
def investigate_endpoint(request: InvestigationRequest):
    if pipeline.df is None or pipeline.vector_store is None:
        raise HTTPException(status_code=400, detail="No logs analyzed. Use the Streamlit interface to upload and analyze logs first.")
    try:
        return pipeline.ask(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
