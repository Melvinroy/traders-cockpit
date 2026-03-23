from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
OUTPUT_DIR = FRONTEND_DIR / "output" / "playwright"
BACKEND_PORT = int(os.getenv("QC_BACKEND_PORT", "8010"))
FRONTEND_PORT = int(os.getenv("QC_FRONTEND_PORT", "3010"))
HOST = os.getenv("QC_HOST", "127.0.0.1")
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
QC_SYMBOL = os.getenv("QC_SYMBOL", "MSFT").strip().upper() or "MSFT"
AUTH_ADMIN_USERNAME = os.getenv("QC_AUTH_USERNAME", "admin")
AUTH_ADMIN_PASSWORD = os.getenv("QC_AUTH_PASSWORD", "change-me-admin")


def _script_command_name(base: str) -> str:
    if os.name == "nt":
        return f"{base}.cmd"
    return base


def _wait_for_http(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 500:
                    return
        except urllib.error.HTTPError as exc:
            if 200 <= exc.code < 500:
                return
            last_error = f"{exc.code} {exc.reason}"
        except Exception as exc:  # pragma: no cover - exercised by local/CI runtime
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for {url}. Last error: {last_error or 'none'}"
    )


def _assert_port_available(host: str, port: int, purpose: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((host, port)) == 0:
            raise RuntimeError(
                f"{purpose} cannot start because {host}:{port} is already in use. "
                "Set QC_FRONTEND_PORT/QC_BACKEND_PORT to free ports."
            )


def _start_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> subprocess.Popen[str]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": env,
        "stdout": stdout_handle,
        "stderr": stderr_handle,
        "text": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    process._stdout_handle = stdout_handle  # type: ignore[attr-defined]
    process._stderr_handle = stderr_handle  # type: ignore[attr-defined]
    return process


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for handle_name in ("_stdout_handle", "_stderr_handle"):
        handle = getattr(process, handle_name, None)
        if handle is not None:
            handle.close()


def _run_command(
    command: list[str], *, cwd: Path, env: dict[str, str], description: str
) -> None:
    result = subprocess.run(command, cwd=str(cwd), env=env, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{description} failed with exit code {result.returncode}")


def _remove_old_artifacts() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _assert_artifacts_exist(names: list[str]) -> None:
    missing = [name for name in names if not (OUTPUT_DIR / name).exists()]
    if missing:
        raise RuntimeError(
            f"Expected browser QC artifacts are missing: {', '.join(missing)}"
        )


def main() -> None:
    _remove_old_artifacts()
    _assert_port_available(HOST, BACKEND_PORT, "Backend")
    _assert_port_available(HOST, FRONTEND_PORT, "Frontend")

    backend_env = os.environ.copy()
    backend_env.update(
        {
            "APP_ENV": "development",
            "ALLOW_SQLITE_FALLBACK": "true",
            "DATABASE_URL": "sqlite:///./data/ci-browser-qc.db",
            "AUTH_STORAGE_MODE": "file",
            "AUTH_DB_PATH": "./data/ci-auth.db",
            "AUTH_REQUIRE_LOGIN": "true",
            "AUTH_ADMIN_USERNAME": AUTH_ADMIN_USERNAME,
            "AUTH_ADMIN_PASSWORD": AUTH_ADMIN_PASSWORD,
            "BROKER_MODE": "paper",
            "ALLOW_LIVE_TRADING": "false",
            "ALLOW_CONTROLLER_MOCK": "true",
            "CORS_ORIGINS": ",".join(
                [
                    FRONTEND_URL,
                    f"http://localhost:{FRONTEND_PORT}",
                ]
            ),
        }
    )

    frontend_env = os.environ.copy()
    frontend_env.update(
        {
            "NEXT_PUBLIC_API_BASE_URL": BACKEND_URL,
            "NEXT_PUBLIC_WS_URL": f"ws://{HOST}:{BACKEND_PORT}/ws/cockpit",
        }
    )

    browser_env = frontend_env.copy()
    browser_env.update(
        {
            "FRONTEND_URL": FRONTEND_URL,
            "BACKEND_URL": BACKEND_URL,
            "QC_AUTH_USERNAME": AUTH_ADMIN_USERNAME,
            "QC_AUTH_PASSWORD": AUTH_ADMIN_PASSWORD,
            "QC_SYMBOL": QC_SYMBOL,
            "BROWSER_SMOKE_LABEL": "ci-browser-smoke",
        }
    )

    backend_process: subprocess.Popen[str] | None = None
    frontend_process: subprocess.Popen[str] | None = None
    try:
        backend_process = _start_process(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                HOST,
                "--port",
                str(BACKEND_PORT),
            ],
            cwd=BACKEND_DIR,
            env=backend_env,
            stdout_path=OUTPUT_DIR / "backend.stdout.log",
            stderr_path=OUTPUT_DIR / "backend.stderr.log",
        )
        _wait_for_http(f"{BACKEND_URL}/health")

        frontend_process = _start_process(
            [
                _script_command_name("npm"),
                "run",
                "dev",
                "--",
                "--hostname",
                HOST,
                "--port",
                str(FRONTEND_PORT),
            ],
            cwd=FRONTEND_DIR,
            env=frontend_env,
            stdout_path=OUTPUT_DIR / "frontend.stdout.log",
            stderr_path=OUTPUT_DIR / "frontend.stderr.log",
        )
        _wait_for_http(FRONTEND_URL)

        _run_command(
            [
                "node",
                (
                    "..\\scripts\\dev\\browser-smoke.mjs"
                    if os.name == "nt"
                    else "../scripts/dev/browser-smoke.mjs"
                ),
            ],
            cwd=FRONTEND_DIR,
            env=browser_env,
            description="Browser smoke",
        )
        _run_command(
            [
                "node",
                (
                    "..\\scripts\\dev\\pending-cancel-qc.mjs"
                    if os.name == "nt"
                    else "../scripts/dev/pending-cancel-qc.mjs"
                ),
            ],
            cwd=FRONTEND_DIR,
            env=browser_env,
            description="Pending cancel QC",
        )
        _run_command(
            [
                "node",
                (
                    "..\\scripts\\dev\\fidelity-baselines.mjs"
                    if os.name == "nt"
                    else "../scripts/dev/fidelity-baselines.mjs"
                ),
            ],
            cwd=FRONTEND_DIR,
            env=browser_env,
            description="Fidelity baselines",
        )
        _run_command(
            [
                "node",
                (
                    "..\\scripts\\dev\\trade-flow-qc.mjs"
                    if os.name == "nt"
                    else "../scripts/dev/trade-flow-qc.mjs"
                ),
            ],
            cwd=FRONTEND_DIR,
            env=browser_env,
            description="Trade flow QC",
        )

        _assert_artifacts_exist(
            [
                "ci-browser-smoke.png",
                "ci-browser-smoke.console.txt",
                "ci-browser-smoke.network.txt",
                "pending-cancel-flow.png",
                "baseline-idle.png",
                "baseline-setup-loaded.png",
                "baseline-trade-entered.png",
                "baseline-protected.png",
                "baseline-profit-flow.png",
                "backend.stdout.log",
                "backend.stderr.log",
                "frontend.stdout.log",
                "frontend.stderr.log",
            ]
        )
        print(f"Browser QC passed: artifacts available under {OUTPUT_DIR}")
    finally:
        _stop_process(frontend_process)
        _stop_process(backend_process)


if __name__ == "__main__":
    main()
