from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "data" / "logs"
DEFAULT_STARTUP_TIMEOUT = 30.0
HEALTH_POLL_INTERVAL = 0.5


def can_bind(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def healthcheck_host(host: str) -> str:
    if host in {"0.0.0.0", "::", ""}:
        return "127.0.0.1"
    return host


def wait_until_ready(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    connect_host = healthcheck_host(host)

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((connect_host, port), timeout=2):
                return True
        except OSError:
            pass

        time.sleep(HEALTH_POLL_INTERVAL)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start the backend safely on Windows with file-backed stdout/stderr."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT)
    args = parser.parse_args()

    if args.startup_timeout <= 0:
        raise SystemExit("[ERROR] --startup-timeout must be greater than 0.")

    if not can_bind(args.host, args.port):
        raise SystemExit(f"[ERROR] Cannot start backend: {args.host}:{args.port} is already in use.")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = LOG_DIR / "backend.stdout.log"
    stderr_path = LOG_DIR / "backend.stderr.log"

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.api:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        command.append("--reload")

    with stdout_path.open("a", encoding="utf-8") as stdout, stderr_path.open(
        "a", encoding="utf-8"
    ) as stderr:
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

        process = subprocess.Popen(
            command,
            cwd=BASE_DIR,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=creationflags,
        )

    if process.poll() is not None:
        raise SystemExit(
            f"[ERROR] Backend exited immediately with code {process.returncode}. See logs:\n"
            f"stdout: {stdout_path}\n"
            f"stderr: {stderr_path}"
        )

    if not wait_until_ready(args.host, args.port, args.startup_timeout):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        raise SystemExit(
            f"[ERROR] Backend did not become ready within {args.startup_timeout:.1f}s. See logs:\n"
            f"stdout: {stdout_path}\n"
            f"stderr: {stderr_path}"
        )

    print(f"Started backend PID {process.pid}")
    print(f"Health: http://{healthcheck_host(args.host)}:{args.port}/health")
    print(f"stdout: {stdout_path}")
    print(f"stderr: {stderr_path}")


if __name__ == "__main__":
    main()
