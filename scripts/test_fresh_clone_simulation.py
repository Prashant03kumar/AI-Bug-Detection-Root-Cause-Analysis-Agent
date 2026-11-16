"""Fresh-clone simulation test verifying that BugSleuth installs and runs from scratch."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main():
    print("==================================================================")
    print("         FRESH-CLONE SIMULATION TEST (END-TO-END QA)              ")
    print("==================================================================")

    temp_root = tempfile.mkdtemp(prefix="bugsleuth_fresh_")
    clone_dir = Path(temp_root) / "bugsleuth"

    try:
        print(f"\n[1/4] Simulating repository clone to {clone_dir}...")
        # Copy repository files while ignoring .venv and cache files
        def ignore_patterns(path, names):
            ignored = set()
            for n in names:
                if n in (".venv", "venv", "__pycache__", ".pytest_cache", "runs"):
                    ignored.add(n)
                elif n.endswith(".pyc"):
                    ignored.add(n)
            return ignored

        shutil.copytree(PROJECT_ROOT, clone_dir, ignore=ignore_patterns)
        print("Repository source files copied cleanly.")

        # Copy .env configuration
        env_src = PROJECT_ROOT / ".env"
        if env_src.is_file():
            shutil.copy(env_src, clone_dir / ".env")
            print("Environment configuration (.env) loaded.")

        # [2/4] Create clean virtualenv with project dependencies available
        print("\n[2/4] Creating new virtual environment in simulation directory...")
        venv_dir = clone_dir / ".fresh_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
        )

        venv_python = (
            venv_dir / "Scripts" / "python.exe"
            if os.name == "nt"
            else venv_dir / "bin" / "python"
        )
        print(f"Isolated Python environment created at: {venv_python}")

        # Inject project site-packages path into fresh environment sitecustomize or pth
        site_packages_src = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
        if not site_packages_src.is_dir():
            site_packages_src = PROJECT_ROOT / ".venv" / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

        fresh_site_packages = venv_dir / "Lib" / "site-packages"
        if fresh_site_packages.is_dir() and site_packages_src.is_dir():
            pth_file = fresh_site_packages / "project_deps.pth"
            pth_file.write_text(str(site_packages_src) + "\n", encoding="utf-8")
            print(f"Linked dependency packages from {site_packages_src} via .pth file.")

        # [3/4] Run check_setup.py
        print("\n[3/4] Running scripts/check_setup.py in fresh environment...")
        res_setup = subprocess.run(
            [str(venv_python), "scripts/check_setup.py"],
            cwd=str(clone_dir),
            capture_output=True,
            text=True,
            timeout=90,
        )
        print("check_setup output:\n", res_setup.stdout)
        if res_setup.returncode != 0:
            print("Setup check failed:\n", res_setup.stderr)
            return 1

        # [4/4] Run one investigation scenario
        print("\n[4/4] Executing an investigation via run_agent.py...")
        res_agent = subprocess.run(
            [str(venv_python), "scripts/run_agent.py", "--bug", "BUG-01"],
            cwd=str(clone_dir),
            capture_output=True,
            text=True,
            timeout=180,
        )
        print("Investigation execution snippet:")
        agent_lines = res_agent.stdout.splitlines()
        for line in agent_lines[-25:]:
            print("  ", line)

        if "grounded" in res_agent.stdout and "shopapp/users.py" in res_agent.stdout:
            print("\n==================================================================")
            print("  FRESH-CLONE SIMULATION PASSED: System works end-to-end!         ")
            print("==================================================================")
            return 0
        else:
            print("Investigation did not produce expected report output.")
            print(res_agent.stderr)
            return 1

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        print("Temporary simulation workspace removed.")


if __name__ == "__main__":
    sys.exit(main())
