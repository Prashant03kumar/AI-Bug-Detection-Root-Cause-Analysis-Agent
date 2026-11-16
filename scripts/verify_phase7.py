"""Verification script for Phase 7: FastAPI and Streamlit boots and endpoints."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import uvicorn

from app.api.main import app


def main():
    print("==================================================================")
    print("           VERIFYING PHASE 7: FASTAPI BACKEND & STREAMLIT UI      ")
    print("==================================================================")

    # 1. Start FastAPI server in a background thread
    print("\n[1/6] Launching FastAPI backend on http://127.0.0.1:8000...")
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Client configured to bypass external sandbox proxy for 127.0.0.1
    client = httpx.Client(trust_env=False, timeout=60.0)

    try:
        # Wait for API to respond
        api_ready = False
        health_data = None
        for _ in range(15):
            time.sleep(0.5)
            try:
                r = client.get("http://127.0.0.1:8000/health", timeout=2.0)
                if r.status_code == 200:
                    api_ready = True
                    health_data = r.json()
                    break
            except Exception:
                pass

        if not api_ready:
            print("ERROR: FastAPI did not become ready.")
            server.should_exit = True
            return 1

        print("FastAPI is online!")

        # 2. Call /health and show JSON
        print("\n[2/6] Calling GET /health:")
        print(json.dumps(health_data, indent=2))

        # 3. Call /bugs and show available scenarios
        print("\n[3/6] Calling GET /bugs:")
        bugs_res = client.get("http://127.0.0.1:8000/bugs", timeout=5.0)
        bugs_data = bugs_res.json()
        print(f"Discovered {len(bugs_data.get('bugs', []))} sample bug scenarios:")
        for b in bugs_data.get("bugs", [])[:3]:
            print(f"  - {b['id']}: {b['title']}")

        # 4. Test /investigate/stream endpoint and show streaming events
        sample_error = (
            "2026-11-16 19:41:03 [ERROR] [shopapp.scenarios] BUG-01 reproduced: 'NoneType' object is not subscriptable\n"
            "Traceback (most recent call last):\n"
            '  File "demo_repo/shopapp/notifications.py", line 37, in send_order_confirmation\n'
            '    if get_user_notification_preference(user_id, "email"):\n'
            '  File "demo_repo/shopapp/users.py", line 38, in get_user_notification_preference\n'
            '    return bool(user["preferences"][channel])\n'
            "TypeError: 'NoneType' object is not subscriptable\n"
        )

        print("\n[4/6] Testing GET /investigate/stream?bug_text=... (capturing first 4 SSE events):")
        with client.stream(
            "GET",
            "http://127.0.0.1:8000/investigate/stream",
            params={"bug_text": sample_error, "max_steps": 4},
            timeout=120.0,
        ) as stream_resp:
            print(f"SSE HTTP Status: {stream_resp.status_code}")
            print(f"Content-Type: {stream_resp.headers.get('content-type')}")
            event_count = 0
            for line in stream_resp.iter_lines():
                if line.startswith("data: "):
                    event_data = line[len("data: ") :]
                    print(f"  Event #{event_count + 1}: {event_data[:120]}...")
                    event_count += 1
                    if event_count >= 4:
                        break

        # 5. Call POST /investigate on sample bug and display output JSON
        print("\n[5/6] Calling POST /investigate on sample bug:")
        investigate_res = client.post(
            "http://127.0.0.1:8000/investigate",
            json={"bug_text": sample_error, "options": {"max_steps": 5}},
            timeout=180.0,
        )
        print(f"POST /investigate Status: {investigate_res.status_code}")
        if investigate_res.status_code == 200:
            report = investigate_res.json()
            print("Investigation Report JSON Summary:")
            print(
                json.dumps(
                    {
                        "summary": report.get("summary"),
                        "root_cause": report.get("root_cause")[:180] + "...",
                        "bug_type": report.get("bug_type"),
                        "file": report.get("file"),
                        "function": report.get("function"),
                        "line_start": report.get("line_start"),
                        "line_end": report.get("line_end"),
                        "introducing_commit": report.get("introducing_commit"),
                        "confidence": report.get("confidence"),
                        "grounded": report.get("grounded"),
                        "validation_notes": report.get("validation_notes"),
                    },
                    indent=2,
                )
            )
        else:
            print(f"Error: {investigate_res.text}")

        # 6. Test Streamlit boot
        print("\n[6/6] Testing Streamlit app startup...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["NO_PROXY"] = "localhost,127.0.0.1"

        ui_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "ui/streamlit_app.py",
                "--server.headless",
                "true",
                "--server.port",
                "8501",
                "--browser.gatherUsageStats",
                "false",
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ui_ready = False
            for _ in range(15):
                time.sleep(1.0)
                try:
                    ui_res = client.get("http://127.0.0.1:8501", timeout=2.0)
                    if ui_res.status_code == 200:
                        ui_ready = True
                        break
                except Exception:
                    pass

            if ui_ready:
                print("Streamlit UI booted successfully and responded with HTTP 200!")
            else:
                print("WARNING: Streamlit did not respond within 15s.")
        finally:
            if ui_proc.poll() is None:
                ui_proc.terminate()
                ui_proc.wait(timeout=3)
            print("Streamlit process stopped.")

    finally:
        server.should_exit = True
        print("FastAPI server stopped.")

    print("\n==================================================================")
    print("           PHASE 7 VERIFICATION SUCCESSFUL!                       ")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
