"""Gmail mock HTTP service."""

import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Fixture data
FIXTURES_PATH = os.environ.get("GMAIL_FIXTURES", "/opt/mock_service/gmail/data/inbox.json")
_inbox = []
_sent = []
_drafts = []
_audit_log = []


def _load_fixtures():
    global _inbox, _sent, _drafts, _audit_log
    try:
        with open(FIXTURES_PATH) as f:
            _inbox = json.load(f)
    except Exception:
        _inbox = []
    _sent = []
    _drafts = []
    _audit_log = []


def _log_call(tool_name: str, request_body: dict, response_body: dict):
    _audit_log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "request_body": request_body,
        "response_body": response_body,
    })


_load_fixtures()


# --- Models ---

class ListMessagesRequest(BaseModel):
    days_back: int = 7
    max_results: int = 20

class GetMessageRequest(BaseModel):
    message_id: str

class SendMessageRequest(BaseModel):
    to: str
    subject: str
    body: str

class SaveDraftRequest(BaseModel):
    to: str
    subject: str
    body: str
    reply_to_message_id: Optional[str] = None


# --- Endpoints ---

@app.post("/gmail/messages")
def list_messages(req: ListMessagesRequest):
    messages = _inbox[:req.max_results]
    result = [{"message_id": m.get("message_id"), "from": m.get("from"),
               "subject": m.get("subject"), "date": m.get("date"),
               "labels": m.get("labels", [])}
              for m in messages]
    resp = {"messages": result, "total": len(_inbox)}
    _log_call("gmail_list_messages", req.model_dump(), resp)
    return resp


@app.post("/gmail/messages/get")
def get_message(req: GetMessageRequest):
    for msg in _inbox:
        if msg.get("message_id") == req.message_id:
            resp = {"message": msg}
            _log_call("gmail_get_message", req.model_dump(), resp)
            return resp
    resp = {"error": f"Message {req.message_id} not found"}
    _log_call("gmail_get_message", req.model_dump(), resp)
    return JSONResponse(status_code=404, content=resp)


@app.post("/gmail/send")
def send_message(req: SendMessageRequest):
    sent_msg = {
        "message_id": f"sent_{len(_sent) + 1}",
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "date": datetime.utcnow().isoformat(),
        "status": "sent",
    }
    _sent.append(sent_msg)
    resp = {"status": "sent", "message_id": sent_msg["message_id"]}
    _log_call("gmail_send_message", req.model_dump(), resp)
    return resp


@app.post("/gmail/drafts/save")
def save_draft(req: SaveDraftRequest):
    draft_msg = {
        "draft_id": f"draft_{len(_drafts) + 1}",
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "reply_to_message_id": req.reply_to_message_id,
        "date": datetime.utcnow().isoformat(),
        "status": "draft",
    }
    _drafts.append(draft_msg)
    resp = {"status": "draft_saved", "draft_id": draft_msg["draft_id"]}
    _log_call("gmail_save_draft", req.model_dump(), resp)
    return resp


@app.get("/gmail/health")
def health():
    return {"status": "ok"}


@app.get("/gmail/audit")
def audit():
    return {"calls": _audit_log, "sent": _sent, "drafts": _drafts}


@app.post("/gmail/reset")
def reset():
    _load_fixtures()
    return {"status": "reset"}


# Error injection
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _base import add_error_injection
add_error_injection(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9100))
    uvicorn.run(app, host="0.0.0.0", port=port)