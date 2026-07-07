# Rural Attendance

Photo-first attendance platform for rural health teams.

- `Portal A`: mobile worker app for check-in and check-out photo uploads
- `Portal B`: supervisor console for AI results, map locations, and flagged attendance events

## How It Works

Workers submit one attendance event at a time:

- event type: `check_in` or `check_out`
- photo evidence from the browser camera
- captured event time
- browser geolocation
- optional note

The backend sends the photo, time, and location context to Gemini for verification. The supervisor dashboard shows each AI result with confidence, risk score, map marker, and alert status.

## Project Structure

```text
backend/
  app/
    main.py
  requirements.txt
frontend/
  index.html
  health-worker.html
  supervisor.html
  static/
    app.js
    health-worker.js
    supervisor.js
    styles.css
    sw.js
    manifest.webmanifest
    icon.svg
```

## Local Run

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Gemini

Set `GOOGLE_API_KEY` before starting the server.

```bash
GOOGLE_API_KEY=your_key_here
```

If no key is configured, the app uses deterministic demo analysis so the full workflow still works for judging.

## Demo Flow

1. Open `/health-worker`.
2. Choose `Check in` or `Check out`.
3. Enable camera and capture a photo.
4. Submit attendance.
5. Open `/supervisor` to see the AI result, location, and alert status.
