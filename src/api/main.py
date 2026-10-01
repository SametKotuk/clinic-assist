"""FastAPI Backend: ClinicAssist sohbet API'si ve statik dosya sunumu."""
from __future__ import annotations

import uuid
import traceback
import time
from pathlib import Path
from typing import Dict, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agent.agent import ClinicAgent

ROOT_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT_DIR / "web"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ajanları son erişim zamanlarıyla birlikte tutuyoruz
sessions: Dict[str, Tuple[ClinicAgent, float]] = {}
SESSION_TIMEOUT = 3600  # 1 saat (saniye)

def cleanup_sessions():
    """Süresi dolmuş oturumları bellekten temizler."""
    current_time = time.time()
    expired = [
        sid for sid, (_, last_access) in sessions.items() 
        if current_time - last_access > SESSION_TIMEOUT
    ]
    for sid in expired:
        del sessions[sid]

def get_agent(session_id: str) -> ClinicAgent:
    cleanup_sessions()
    if session_id not in sessions:
        sessions[session_id] = (ClinicAgent(), time.time())
    else:
        agent, _ = sessions[session_id]
        sessions[session_id] = (agent, time.time())
    return sessions[session_id][0]

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

class ToolCallResponse(BaseModel):
    name: str
    input: dict
    result: str
    is_error: bool

class CitationResponse(BaseModel):
    source: str
    section: str
    score: float

class ChatResponse(BaseModel):
    text: str
    session_id: str
    cited_sources: list[CitationResponse]
    tool_calls: list[ToolCallResponse]
    steps: int

class ResetRequest(BaseModel):
    session_id: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    try:
        agent = get_agent(session_id)
        reply = agent.chat(payload.message)
        
        return ChatResponse(
            text=reply.text,
            session_id=session_id,
            cited_sources=[CitationResponse(source=h.source, section=h.section, score=round(h.score, 3)) for h in reply.cited],
            tool_calls=[ToolCallResponse(name=c.name, input=c.input, result=c.result, is_error=c.is_error) for c in reply.tool_calls],
            steps=reply.steps,
        )
    except Exception as exc:
        error_trace = traceback.format_exc()
        print(error_trace) 
        
        return ChatResponse(
            text=f"⚠️ SİSTEM HATASI:\n\n{error_trace}",
            session_id=session_id,
            cited_sources=[],
            tool_calls=[],
            steps=0
        )

@app.post("/api/reset")
async def reset_endpoint(payload: ResetRequest):
    if payload.session_id in sessions:
        sessions[payload.session_id][0].reset()
    return {"status": "ok"}

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

@app.get("/")
async def root():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "API çalışıyor."}