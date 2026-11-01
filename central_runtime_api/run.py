"""CLI launcher for Central AI Runtime & API."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time

from central_runtime_api.config import APIConfig
from central_runtime_api.server import create_server
from central_runtime_api.workers.feedback_worker import ContinuousLearningWorker


def run_worker_thread(config: APIConfig, stop_event: threading.Event):
    """Background worker loop aggregating candidate datasets."""
    worker = ContinuousLearningWorker(config.data_dir)
    print(f"[Worker] Background learning worker started (interval: {config.worker_interval_seconds}s)")
    while not stop_event.is_set():
        try:
            worker.process_cycle("v0.1.0-candidates")
        except Exception as e:
            print(f"[Worker Error] Failed learning cycle: {e}")
        stop_event.wait(config.worker_interval_seconds)
    print("[Worker] Background learning worker stopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Central Arabic AI Runtime & API Server")
    parser.add_argument("--host", type=str, default=os.environ.get("CENTRAL_AI_HOST", "127.0.0.1"), help="Host IP")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CENTRAL_AI_PORT", "8000")), help="Port")
    parser.add_argument(
        "--server",
        type=str,
        default=os.environ.get("CENTRAL_AI_SERVER_ENGINE", "http"),
        choices=["http", "asgi"],
        help="Server engine: standard 'http' or production 'asgi' (uvicorn)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=os.environ.get("CENTRAL_AI_PROVIDER", "mock"),
        choices=["mock", "ollama", "mlx_jais", "hosted"],
        help="Inference provider (default: mock)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("CENTRAL_AI_MODEL", "qwen3:4b"),
        help="Model name or tag",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("CENTRAL_AI_TIMEOUT", "120.0")),
        help="Inference timeout in seconds",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        default=os.environ.get("CENTRAL_AI_WORKER_AUTO_START", "false").lower() == "true",
        help="Auto-start background learning worker daemon",
    )

    args = parser.parse_args()

    config = APIConfig(
        host=args.host,
        port=args.port,
        provider=args.provider,
        model=args.model,
        timeout_seconds=args.timeout,
        worker_auto_start=args.worker,
    )

    # Launch ASGI server via uvicorn if requested and available
    if args.server == "asgi":
        try:
            import uvicorn
            from central_runtime_api.asgi import CentralAIASGIApp

            app = CentralAIASGIApp(config)
            print("================================================================")
            print("  Central Arabic AI Runtime & API (ASGI / Uvicorn) — Beta V-001")
            print(f"  Listening on: http://{config.host}:{config.port}")
            print(f"  Active Provider: {config.provider.upper()} | Model: {config.model}")
            print(f"  CORS Allowed Origins: {config.cors_origins}")
            print("================================================================")
            uvicorn.run(app, host=config.host, port=config.port, log_level="info")
            return 0
        except ImportError:
            print("[Warning] 'uvicorn' not found in environment; falling back to built-in HTTP server.")

    # Standard built-in HTTP server
    server = create_server(config)
    stop_event = threading.Event()
    worker_thread = None

    if config.worker_auto_start:
        worker_thread = threading.Thread(target=run_worker_thread, args=(config, stop_event), daemon=True)
        worker_thread.start()

    def shutdown_signal_handler(signum, frame):
        print(f"\nReceived signal {signum}. Initiating graceful shutdown...")
        stop_event.set()
        threading.Thread(target=server.shutdown).start()

    signal.signal(signal.SIGINT, shutdown_signal_handler)
    signal.signal(signal.SIGTERM, shutdown_signal_handler)

    print("================================================================")
    print("  Central Arabic AI Runtime & API — Beta V-001")
    print(f"  Listening on: http://{config.host}:{config.port}")
    print(f"  Active Provider: {config.provider.upper()}")
    print(f"  Active Model:    {config.model}")
    print(f"  CORS Allowed Origins: {config.cors_origins}")
    print("  Endpoints:")
    print("    GET  /health")
    print("    GET  /ready")
    print("    POST /api/v1/chat")
    print("    POST /api/v1/tutor/explain")
    print("    POST /api/v1/speaking/respond")
    print("    POST /api/v1/exams/explain")
    print("    POST /api/v1/feedback")
    print("    POST /api/v1/feedback/consent/withdraw")
    print("================================================================")

    try:
        server.serve_forever()
    finally:
        stop_event.set()
        server.server_close()
        print("Server shutdown complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
