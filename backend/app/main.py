from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import db


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


def load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_dotenv()


@dataclass
class AgentAlert:
    level: str
    title: str
    detail: str
    recommendation: str
    created_at: str


@dataclass
class AttendanceRecord:
    id: str
    worker_name: str
    facility_name: str
    event_type: str
    event_time: str
    latitude: float | None
    longitude: float | None
    photo_uploaded: bool
    verification_status: str
    confidence: float
    risk_score: int
    ai_result: str
    roster_suggestion: str
    note: str = ""
    translated_note: str = ""
    alert: AgentAlert | None = None
    raw_signals: dict[str, Any] = field(default_factory=dict)


# DemoStore has been replaced by db.py persistence.


class GeminiVerifier:
    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.enabled = bool(self.api_key)

    async def analyze(
        self,
        *,
        worker_name: str,
        facility_name: str,
        event_type: str,
        event_time: str,
        latitude: float | None,
        longitude: float | None,
        note: str,
        photo: UploadFile | None,
    ) -> dict[str, Any]:
        # Look up employee
        employees = db.load_employees()
        employee = next(
            (emp for emp in employees if emp["name"].strip().lower() == worker_name.strip().lower()),
            None
        )
        
        profile_photo_bytes = None
        profile_photo_mime = "image/jpeg"
        
        if employee and employee.get("photo_url"):
            filename = os.path.basename(employee["photo_url"])
            photo_path = STATIC_DIR / "profiles" / filename
            if photo_path.exists():
                try:
                    with open(photo_path, "rb") as f:
                        profile_photo_bytes = f.read()
                    if filename.endswith(".png"):
                        profile_photo_mime = "image/png"
                except Exception as e:
                    print("Error reading profile photo:", e)

        if not self.enabled:
            return self._demo_analysis(
                worker_name=worker_name,
                facility_name=facility_name,
                event_type=event_type,
                event_time=event_time,
                latitude=latitude,
                longitude=longitude,
                note=note,
                photo=photo,
                has_profile_photo=(profile_photo_bytes is not None)
            )

        try:
            return await self._gemini_analysis(
                worker_name=worker_name,
                facility_name=facility_name,
                event_type=event_type,
                event_time=event_time,
                latitude=latitude,
                longitude=longitude,
                note=note,
                photo=photo,
                profile_photo_bytes=profile_photo_bytes,
                profile_photo_mime=profile_photo_mime
            )
        except Exception as e:
            print("Error in Gemini analysis:", e)
            return self._demo_analysis(
                worker_name=worker_name,
                facility_name=facility_name,
                event_type=event_type,
                event_time=event_time,
                latitude=latitude,
                longitude=longitude,
                note=note,
                photo=photo,
                has_profile_photo=(profile_photo_bytes is not None)
            )

    async def _gemini_analysis(
        self,
        *,
        worker_name: str,
        facility_name: str,
        event_type: str,
        event_time: str,
        latitude: float | None,
        longitude: float | None,
        note: str,
        photo: UploadFile | None,
        profile_photo_bytes: bytes | None = None,
        profile_photo_mime: str = "image/jpeg"
    ) -> dict[str, Any]:
        import urllib.request

        prompt = (
            "You verify attendance for rural health workers. Return only JSON with keys: "
            "verification_status, confidence, risk_score, ai_result, roster_suggestion, "
            "alert_level, alert_title, alert_detail, translated_note.\n\n"
            "Constraints for keys:\n"
            "1. 'verification_status': Must be exactly one of: 'verified', 'review', or 'flagged'. "
            "(Use 'flagged' for clear mismatches, identity errors, or suspicious events; 'review' for minor discrepancies; 'verified' for normal approvals).\n"
            "2. 'confidence': A float between 0.0 and 1.0 representing how confident you are in your verification.\n"
            "3. 'risk_score': An integer between 0 and 100. Clear mismatches, missing proof, or spoofing should have high risk (e.g., 75-100). Verified events should have low risk (e.g., 0-15).\n"
            "4. 'roster_suggestion': Suggest a concrete action (e.g., 'Escalate to supervisor', 'Require manual approval', 'No action needed'). Must not be empty.\n"
            "5. 'translated_note': If the worker note is not in English, translate it to English. If in English, keep as-is. If empty, set to ''.\n\n"
        )
        
        if profile_photo_bytes is not None:
            prompt += (
                "IMPORTANT: You are provided with two images. "
                "Image 1 (first image) is the worker's registered profile photo. "
                "Image 2 (second image) is the newly captured check-in photo. "
                "Compare the face in Image 2 with the face in Image 1. If they do not show the exact same person, "
                "set 'verification_status' to 'flagged', 'risk_score' to 95, 'ai_result' to 'face_mismatch', "
                "and populate 'alert_level' as 'high', 'alert_title' as 'Identity Mismatch', "
                "and 'alert_detail' explaining that the face in the check-in does not match their profile.\n\n"
            )
        else:
            prompt += (
                "Note: No registered profile photo exists for this worker yet. Verify the check-in photo "
                "based on context (e.g. backdrop, face visibility, location details).\n\n"
            )

        prompt += (
            f"Worker: {worker_name}. Facility: {facility_name}. Event: {event_type}. "
            f"Event time: {event_time}. Latitude: {latitude}. Longitude: {longitude}. "
            f"Optional note: {note}."
        )

        payload_parts: list[dict[str, Any]] = [
            {"text": prompt}
        ]

        if profile_photo_bytes is not None:
            payload_parts.append(
                {
                    "inlineData": {
                        "mimeType": profile_photo_mime,
                        "data": base64.b64encode(profile_photo_bytes).decode("utf-8"),
                    }
                }
            )

        if photo is not None:
            photo_bytes = await photo.read()
            if photo_bytes:
                payload_parts.append(
                    {
                        "inlineData": {
                            "mimeType": photo.content_type or "image/jpeg",
                            "data": base64.b64encode(photo_bytes).decode("utf-8"),
                        }
                    }
                )

        request_body = {
            "contents": [{"role": "user", "parts": payload_parts}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        request = urllib.request.Request(
            url=(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent"
                f"?key={self.api_key}"
            ),
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=90) as response:
            response_body = json.loads(response.read().decode("utf-8"))

        raw_text = (
            response_body["candidates"][0]["content"]["parts"][0]["text"]
            if response_body.get("candidates")
            else "{}"
        )
        parsed = json.loads(raw_text)
        
        status = parsed.get("verification_status", "review").lower()
        if status not in ["verified", "review", "flagged"]:
            status = "flagged" if status in ["rejected", "failed", "invalid", "spoof"] else "review"
            
        alert_needed = status != "verified"

        return {
            "verification_status": status,
            "confidence": float(parsed.get("confidence", 0.7)),
            "risk_score": int(parsed.get("risk_score", 35)),
            "ai_result": parsed.get("ai_result", "Gemini returned an incomplete result."),
            "roster_suggestion": parsed.get(
                "roster_suggestion",
                "Hold for supervisor review.",
            ),
            "translated_note": parsed.get("translated_note", note),
            "alert": (
                {
                    "level": parsed.get("alert_level", "medium"),
                    "title": parsed.get("alert_title", "Attendance needs review"),
                    "detail": parsed.get(
                        "alert_detail",
                        "The evidence is not strong enough for automatic approval.",
                    ),
                    "recommendation": parsed.get(
                        "roster_suggestion",
                        "Hold for supervisor review.",
                    ),
                }
                if alert_needed
                else None
            ),
            "raw_signals": {"provider": "gemini", "used_photo": photo is not None},
        }

    def _demo_analysis(
        self,
        *,
        worker_name: str,
        facility_name: str,
        event_type: str,
        event_time: str,
        latitude: float | None,
        longitude: float | None,
        note: str,
        photo: UploadFile | None,
        has_profile_photo: bool = False
    ) -> dict[str, Any]:
        photo_uploaded = photo is not None and bool(photo.filename)
        note_lower = note.lower()
        spoof_words = any(word in note_lower for word in ["home", "fake", "proxy", "spoof"])
        face_mismatch = "mismatch" in note_lower or "mismatch" in worker_name.lower()
        parsed_time = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        local_hour = parsed_time.hour

        confidence = 0.56
        risk_score = 48
        status = "review"
        ai_result = "The attendance event needs another trust signal before auto-approval."
        roster_suggestion = "Ask the worker for a clearer attendance photo."
        alert: dict[str, Any] | None = {
            "level": "medium",
            "title": "Attendance under review",
            "detail": "The current evidence is plausible but not strong enough for auto-approval.",
            "recommendation": roster_suggestion,
        }

        if photo_uploaded:
            confidence += 0.18
            risk_score -= 15
        if latitude is not None and longitude is not None:
            confidence += 0.09
            risk_score -= 9
        if event_type == "check_in" and 2 <= local_hour <= 7:
            confidence += 0.08
            risk_score -= 8
        if event_type == "check_out" and 8 <= local_hour <= 15:
            confidence += 0.07
            risk_score -= 6
        if spoof_words:
            confidence -= 0.28
            risk_score += 34

        if face_mismatch:
            status = "flagged"
            confidence = 0.99
            risk_score = 95
            ai_result = "face_mismatch"
            roster_suggestion = "Hold shift payout and escalate to supervisor."
            alert = {
                "level": "high",
                "title": "Verification Failed: Identity Mismatch",
                "detail": f"The person in the check-in photo does not match the registered profile of {worker_name}.",
                "recommendation": roster_suggestion,
            }
        elif photo_uploaded and not spoof_words and confidence >= 0.82:
            status = "verified"
            alert = None
            ai_result = (
                f"The {event_type.replace('_', ' ')} photo, timestamp, and geolocation align with a "
                f"routine attendance event for {facility_name}."
            )
            roster_suggestion = "No action required."
        elif spoof_words or risk_score >= 72:
            status = "flagged"
            ai_result = (
                "The event has a suspicious timing or note pattern, or the photo evidence is too weak "
                "for trusted attendance."
            )
            roster_suggestion = "Escalate to the supervisor and hold shift settlement."
            alert = {
                "level": "high",
                "title": "Suspicious attendance event",
                "detail": "The submitted evidence conflicts with normal field attendance patterns.",
                "recommendation": roster_suggestion,
            }
        else:
            ai_result = (
                "The photo and location look plausible, but the event still needs supervisor confirmation."
            )
            roster_suggestion = "Review this event with the worker before final approval."

        translated_note = note
        if any(ord(char) > 127 for char in note):
            if "रास्ता" in note or "road" in note_lower or "kharab" in note_lower:
                translated_note = "The road is bad/blocked (Demo Translation)"
            elif "tabiyat" in note_lower or "bimar" in note_lower or "ill" in note_lower:
                translated_note = "I am feeling unwell / medical issue (Demo Translation)"
            else:
                translated_note = f"[Translated from regional language]: {note}"

        return {
            "verification_status": status,
            "confidence": round(max(min(confidence, 0.99), 0.05), 2),
            "risk_score": max(min(risk_score, 100), 0),
            "ai_result": ai_result,
            "roster_suggestion": roster_suggestion,
            "translated_note": translated_note,
            "alert": alert,
            "raw_signals": {
                "provider": "demo",
                "photo_uploaded": photo_uploaded,
                "has_geotag": latitude is not None and longitude is not None,
                "event_type": event_type,
            },
        }

    async def transcribe_and_translate(self, audio_file: UploadFile) -> dict[str, str]:
        if not self.enabled:
            return self._demo_transcribe()

        try:
            audio_bytes = await audio_file.read()
            if not audio_bytes:
                return {"transcription": "", "translation": ""}

            payload_parts = [
                {
                    "text": (
                        "Transcribe the following audio. If the speaker is speaking in a regional or foreign language "
                        "(like Hindi, Spanish, Bengali, etc.), transcribe what they said verbatim, and also translate it to English. "
                        "Return only JSON with keys: transcription, translation."
                    )
                },
                {
                    "inlineData": {
                        "mimeType": audio_file.content_type or "audio/webm",
                        "data": base64.b64encode(audio_bytes).decode("utf-8"),
                    }
                }
            ]

            request_body = {
                "contents": [{"role": "user", "parts": payload_parts}],
                "generationConfig": {"responseMimeType": "application/json"},
            }

            import urllib.request
            request = urllib.request.Request(
                url=(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    "gemini-2.5-flash:generateContent"
                    f"?key={self.api_key}"
                ),
                data=json.dumps(request_body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=90) as response:
                response_body = json.loads(response.read().decode("utf-8"))

            raw_text = (
                response_body["candidates"][0]["content"]["parts"][0]["text"]
                if response_body.get("candidates")
                else "{}"
            )
            parsed = json.loads(raw_text)
            return {
                "transcription": parsed.get("transcription", ""),
                "translation": parsed.get("translation", ""),
            }
        except Exception as e:
            print("Error in Gemini transcription:", e)
            return self._demo_transcribe()

    def _demo_transcribe(self) -> dict[str, str]:
        return {
            "transcription": "रास्ता बंद है",
            "translation": "The road is blocked"
        }


verifier = GeminiVerifier()


app = FastAPI(title="Rural Attendance Mission Control")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def landing() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health-worker")
async def health_worker() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "health-worker.html")


@app.get("/supervisor")
async def supervisor() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "supervisor.html")


@app.get("/api/dashboard")
async def dashboard() -> JSONResponse:
    records = db.load_records()
    alerts = [record["alert"] for record in records if record["alert"]]
    metrics = {
        "total_events": len(records),
        "verified_count": sum(1 for item in records if item["verification_status"] == "verified"),
        "review_count": sum(1 for item in records if item["verification_status"] == "review"),
        "flagged_count": sum(1 for item in records if item["verification_status"] == "flagged"),
    }
    return JSONResponse({"metrics": metrics, "records": records, "alerts": alerts})


@app.post("/api/check-in")
async def create_check_in(
    worker_name: str = Form(...),
    facility_name: str = Form(...),
    event_type: str = Form(...),
    event_time: str = Form(...),
    note: str = Form(default=""),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
) -> JSONResponse:
    analysis = await verifier.analyze(
        worker_name=worker_name,
        facility_name=facility_name,
        event_type=event_type,
        event_time=event_time,
        latitude=latitude,
        longitude=longitude,
        note=note,
        photo=photo,
    )

    alert = analysis.get("alert")
    record = AttendanceRecord(
        id=str(uuid4()),
        worker_name=worker_name,
        facility_name=facility_name,
        event_type=event_type,
        event_time=event_time,
        latitude=latitude,
        longitude=longitude,
        photo_uploaded=photo is not None and bool(photo.filename),
        verification_status=analysis["verification_status"],
        confidence=analysis["confidence"],
        risk_score=analysis["risk_score"],
        ai_result=analysis["ai_result"],
        roster_suggestion=analysis["roster_suggestion"],
        note=note,
        translated_note=analysis.get("translated_note", note),
        alert=(
            AgentAlert(
                level=alert["level"],
                title=alert["title"],
                detail=alert["detail"],
                recommendation=alert["recommendation"],
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            if alert
            else None
        ),
        raw_signals=analysis.get("raw_signals", {}),
    )
    
    # Save to JSON persistent store
    records = db.load_records()
    records.insert(0, asdict(record))
    db.save_records(records)
    
    return JSONResponse({"record": asdict(record)})


@app.post("/api/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
) -> JSONResponse:
    result = await verifier.transcribe_and_translate(audio)
    return JSONResponse(result)


@app.get("/api/employees")
async def get_employees() -> JSONResponse:
    employees = db.load_employees()
    return JSONResponse({"employees": employees})


@app.post("/api/employees")
async def create_employee(
    name: str = Form(...),
    facility_name: str = Form(...),
    work_hours: str = Form(...),
    photo: UploadFile = File(...),
) -> JSONResponse:
    employees = db.load_employees()
    
    employee_id = str(uuid4())
    photo_filename = f"{employee_id}.jpg"
    
    profiles_dir = STATIC_DIR / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    
    photo_path = profiles_dir / photo_filename
    photo_bytes = await photo.read()
    with open(photo_path, "wb") as f:
        f.write(photo_bytes)
        
    photo_url = f"/static/profiles/{photo_filename}"
    
    new_employee = {
        "id": employee_id,
        "name": name,
        "facility_name": facility_name,
        "photo_url": photo_url,
        "work_hours": work_hours
    }
    
    employees.insert(0, new_employee)
    db.save_employees(employees)
    
    return JSONResponse({"employee": new_employee})


@app.post("/api/demo/spoof")
async def seed_spoof_demo() -> JSONResponse:
    timestamp = datetime.now(timezone.utc).replace(minute=14, second=0, microsecond=0).isoformat()
    alert = AgentAlert(
        level="high",
        title="Suspicious check-out",
        detail="The event timing and evidence quality do not match a normal field exit pattern.",
        recommendation="Hold payout approval and ask for supervisor confirmation.",
        created_at=timestamp,
    )
    record = AttendanceRecord(
        id=str(uuid4()),
        worker_name="Demo Spoof Attempt",
        facility_name="Bhilpur Hamlet Visit",
        event_type="check_out",
        event_time=timestamp,
        latitude=23.2854,
        longitude=77.3952,
        photo_uploaded=False,
        verification_status="flagged",
        confidence=0.24,
        risk_score=89,
        ai_result="No trustworthy attendance photo was supplied for the exit event.",
        roster_suggestion=alert.recommendation,
        note="Marked from outside the field site.",
        alert=alert,
        raw_signals={"provider": "demo", "seeded": True},
    )
    
    # Save to persistent store
    records = db.load_records()
    records.insert(0, asdict(record))
    db.save_records(records)
    
    return JSONResponse({"record": asdict(record)})
