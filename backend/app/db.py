import json
import os
from pathlib import Path
from datetime import datetime, timezone

DB_DIR = Path(__file__).resolve().parent
EMPLOYEES_PATH = DB_DIR / "employees.json"
RECORDS_PATH = DB_DIR / "records.json"

DEFAULT_EMPLOYEES = [
    {
        "id": "asha-devi-id",
        "name": "Asha Devi",
        "facility_name": "Kotra Village Clinic",
        "photo_url": "",
        "work_hours": "09:00 - 17:00"
    },
    {
        "id": "meena-kumari-id",
        "name": "Meena Kumari",
        "facility_name": "Ward 7 Outreach Point",
        "photo_url": "",
        "work_hours": "08:00 - 16:00"
    }
]

def init_db():
    if not EMPLOYEES_PATH.exists():
        with open(EMPLOYEES_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_EMPLOYEES, f, indent=2, ensure_ascii=False)
            
    if not RECORDS_PATH.exists():
        today = datetime.now(timezone.utc)
        default_records = [
            {
                "id": "seed-record-1",
                "worker_name": "Asha Devi",
                "facility_name": "Kotra Village Clinic",
                "event_type": "check_in",
                "event_time": today.replace(hour=3, minute=20, second=0, microsecond=0).isoformat(),
                "latitude": 23.2599,
                "longitude": 77.4126,
                "photo_uploaded": False,
                "verification_status": "verified",
                "confidence": 0.95,
                "risk_score": 11,
                "ai_result": "Face visibility, clinic backdrop, location, and arrival time align with a normal start-of-shift check-in.",
                "roster_suggestion": "No action required.",
                "note": "On duty",
                "translated_note": "On duty",
                "alert": None,
                "raw_signals": {"provider": "demo"}
            },
            {
                "id": "seed-record-2",
                "worker_name": "Meena Kumari",
                "facility_name": "Ward 7 Outreach Point",
                "event_type": "check_out",
                "event_time": today.replace(hour=11, minute=35, second=0, microsecond=0).isoformat(),
                "latitude": 23.2722,
                "longitude": 77.4331,
                "photo_uploaded": False,
                "verification_status": "review",
                "confidence": 0.68,
                "risk_score": 42,
                "ai_result": "The photo and location are plausible, but the late check-out pattern needs supervisor confirmation.",
                "roster_suggestion": "Review field completion before closing the shift.",
                "note": "Done with shift",
                "translated_note": "Done with shift",
                "alert": None,
                "raw_signals": {"provider": "demo"}
            }
        ]
        with open(RECORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(default_records, f, indent=2, ensure_ascii=False)

def load_employees():
    init_db()
    try:
        with open(EMPLOYEES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_EMPLOYEES

def save_employees(employees):
    with open(EMPLOYEES_PATH, "w", encoding="utf-8") as f:
        json.dump(employees, f, indent=2, ensure_ascii=False)

def load_records():
    init_db()
    try:
        with open(RECORDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_records(records):
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

init_db()
