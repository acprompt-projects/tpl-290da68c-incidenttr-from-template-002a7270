from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional
from contextlib import asynccontextmanager

from models import IncidentCreate, IncidentRead, TriageUpdate, Severity, IncidentStatus
from classify import classify_severity

_db: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = _db
    yield


app = FastAPI(title="Incident Triage Service", lifespan=lifespan)


@app.post("/incidents", response_model=IncidentRead, status_code=201)
def create_incident(payload: IncidentCreate):
    severity = classify_severity(payload.title, payload.description, payload.labels)
    now = datetime.now(timezone.utc)
    incident = {
        "id": str(uuid4()),
        "title": payload.title,
        "description": payload.description,
        "source": payload.source,
        "labels": payload.labels,
        "severity": severity,
        "status": IncidentStatus.NEW,
        "assignee": None,
        "notes": None,
        "created_at": now,
        "updated_at": now,
    }
    _db[incident["id"]] = incident
    return incident


@app.get("/incidents/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str):
    incident = _db.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.patch("/incidents/{incident_id}/triage", response_model=IncidentRead)
def update_triage(incident_id: str, payload: TriageUpdate):
    incident = _db.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident["status"] == IncidentStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Cannot triage a resolved incident")
    if payload.severity is not None:
        incident["severity"] = payload.severity
    if payload.status is not None:
        incident["status"] = payload.status
    if payload.assignee is not None:
        incident["assignee"] = payload.assignee
    if payload.notes is not None:
        incident["notes"] = payload.notes
    incident["updated_at"] = datetime.now(timezone.utc)
    return incident


@app.get("/health")
def health():
    return {"status": "ok", "incidents_tracked": len(_db)}