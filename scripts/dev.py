"""Run local services in one terminal. Ctrl+C stops only processes we started."""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-ai", action="store_true", help="Start ONNX and RTSP services too"
    )
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--inference-port", type=int, default=8001)
    parser.add_argument("--frontend-port", type=int, default=5173)
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env.local")
    except ImportError:
        pass
    for key, name in [
        ("DETECTOR_MODEL", "person"),
        ("PPE_MODEL", "ppe"),
        ("POSE_MODEL", "pose"),
        ("BEHAVIOR_MODEL", "behavior"),
    ]:
        os.environ.setdefault(key, str(ROOT / "models" / f"{name}.onnx"))
    os.environ["API_URL"] = f"http://127.0.0.1:{args.backend_port}"
    os.environ["BACKEND_URL"] = os.environ["API_URL"]
    os.environ["INFERENCE_URL"] = f"http://127.0.0.1:{args.inference_port}"
    for port in [args.backend_port, args.frontend_port] + (
        [args.inference_port] if args.with_ai else []
    ):
        with socket.socket() as check:
            try:
                check.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(
                    f"Port {port} is already in use. Stop the existing local service first."
                )
    commands = [
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.backend_port),
        ],
        [
            "node",
            str(ROOT / "node_modules/vite/bin/vite.js"),
            "--host",
            "127.0.0.1",
            "--port",
            str(args.frontend_port),
            "--strictPort",
        ],
    ]
    if args.with_ai:
        commands.extend(
            [
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "inference.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.inference_port),
                ],
                [sys.executable, "-m", "ingestion.main"],
            ]
        )
    processes = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for command in commands:
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=ROOT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
            )
        print(
            f"HSE AI-Video: http://127.0.0.1:{args.frontend_port}; API: http://127.0.0.1:{args.backend_port}/api/docs",
            flush=True,
        )
        while all(p.poll() is None for p in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
