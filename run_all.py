"""
run_all.py — Start all StockLLM services from a single command.
Reads DOC_OUTPUT_DIR from .env (written by split_pdf) to auto-start docs_analysis.
"""

import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(ROOT, "baseknowledge")
PY = os.path.join(ROOT, "python")
BK_UTILS = os.path.join(PY, "baseknowledge_utils")


def _start(label: str, script_path: str, extra_args: list[str] = []) -> subprocess.Popen:
    cmd = [sys.executable, script_path] + extra_args
    existing_pypath = os.environ.get("PYTHONPATH", "")
    pypath_parts = [ROOT, PY] + ([existing_pypath] if existing_pypath else [])
    env = {
        **os.environ,
        "STOCKLLM_ROOT": ROOT,
        "PYTHONPATH": os.pathsep.join(pypath_parts),
    }
    print(f"  Starting {label} ...")
    return subprocess.Popen(cmd, cwd=ROOT, env=env)


def main():
    processes: list[tuple[str, subprocess.Popen]] = []

    print("\nStarting StockLLM services...\n")

    services = [
        ("ollama_model      [8008]", os.path.join(PY, "ollama_model.py")),
        ("control_plane     [8000]", os.path.join(PY, "control_plane.py")),
        ("storing           [8002]", os.path.join(BK_UTILS, "storing.py")),
        ("chunking          [8004]", os.path.join(BK_UTILS, "chunking.py")),
        ("local_graph       [8005]", os.path.join(BK, "local", "local_graph.py")),
        ("cache_maintenance       ", os.path.join(PY, "cache_maintenance.py")),
    ]

    services.append(("docs_analysis      [8001]", os.path.join(BK_UTILS, "docs_analysis.py")))

    for label, path in services:
        proc = _start(label, path)
        processes.append((label, proc))

    pid_summary = ", ".join(f"{label.split()[0]}={p.pid}" for label, p in processes)
    print(f"\nAll services running — PIDs: {pid_summary}")
    print("Press Ctrl+C to stop all.\n")

    def shutdown(sig, frame):
        print("\nShutting down all services...")
        for _, p in processes:
            p.terminate()
        for label, p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"  Force-killing {label.split()[0]} (PID {p.pid})")
                p.kill()
        print("All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(3)
        for label, p in processes:
            if p.poll() is not None:
                print(f"WARNING: {label.split()[0]} (PID {p.pid}) exited with code {p.returncode}.")


if __name__ == "__main__":
    main()
