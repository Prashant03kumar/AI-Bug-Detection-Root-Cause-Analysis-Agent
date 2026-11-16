"""Development launcher script for BugSleuth.

Starts both the FastAPI backend on port 8000 and the Streamlit frontend
on port 8501 concurrently, managing process lifecycles and graceful shutdown.
"""

import os
import signal
import subprocess
import sys
import time
from typing import List


def print_banner() -> None:
    """Display colorful startup status banner."""
    print("=" * 68)
    print("      🔍 BugSleuth: AI Bug Detection & RCA Agent Dev Server      ")
    print("=" * 68)
    print("  🚀 FastAPI Backend:    http://127.0.0.1:8000")
    print("  📖 API Documentation:  http://127.0.0.1:8000/docs")
    print("  🩺 Health Endpoint:    http://127.0.0.1:8000/health")
    print("  🖥️ Streamlit Frontend: http://127.0.0.1:8501")
    print("=" * 68)
    print("  Press Ctrl+C to terminate both servers cleanly.\n")


def main() -> None:
    """Launch FastAPI and Streamlit subprocesses and monitor their execution."""
    python_exe = sys.executable
    processes: List[subprocess.Popen] = []

    # Command line arguments for both servers
    api_cmd = [
        python_exe,
        "-m",
        "uvicorn",
        "app.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    ui_cmd = [
        python_exe,
        "-m",
        "streamlit",
        "run",
        "ui/streamlit_app.py",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        print_banner()

        print("[run_dev] Starting FastAPI backend on :8000...")
        api_proc = subprocess.Popen(api_cmd, env=env)
        processes.append(api_proc)

        # Brief pause to let API begin binding port before UI initializes
        time.sleep(1.5)

        print("[run_dev] Starting Streamlit frontend on :8501...")
        ui_proc = subprocess.Popen(ui_cmd, env=env)
        processes.append(ui_proc)

        # Monitor loop
        while True:
            for p in processes:
                ret = p.poll()
                if ret is not None:
                    print(f"\n[run_dev] A subprocess terminated with code {ret}. Shutting down...")
                    return
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[run_dev] Interrupted by user. Shutting down servers...")
    finally:
        for p in processes:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=3)
                except Exception:
                    p.kill()
        print("[run_dev] All servers stopped.")


if __name__ == "__main__":
    main()
