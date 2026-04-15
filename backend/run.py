"""
Windows-friendly dev runner for FastAPI + Playwright.

Uvicorn's built-in ``--reload`` uses a selector event loop on Windows when it
spawns its reload worker. Playwright launches a browser subprocess, and that
combination fails with ``NotImplementedError``. This runner keeps hot reload by
watching files outside Uvicorn while the actual server process stays on the
Proactor loop that Playwright needs.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import uvicorn

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000


def configure_environment() -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.chdir(BASE_DIR)

    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def serve() -> None:
    configure_environment()
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)


def on_reload(changes) -> None:
    changed_files = []
    for _, changed_path in changes:
        path = Path(changed_path)
        try:
            changed_files.append(path.resolve().relative_to(BASE_DIR).as_posix())
        except ValueError:
            changed_files.append(path.name)

    changed_files = sorted(set(changed_files))
    preview = ", ".join(changed_files[:5])
    suffix = "..." if len(changed_files) > 5 else ""
    print(f"Reloading after changes: {preview}{suffix}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the FastAPI app with a Playwright-safe reload loop."
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Start the server once without watching for file changes.",
    )
    args = parser.parse_args()

    configure_environment()

    if args.no_reload:
        serve()
        return

    try:
        from watchfiles import run_process
    except ImportError:
        print("watchfiles is not installed; starting without auto-reload.")
        serve()
        return

    print(f"Watching {BASE_DIR} for changes...")
    run_process(
        str(BASE_DIR),
        target=serve,
        callback=on_reload,
        debounce=1200,
        step=100,
    )


if __name__ == "__main__":
    main()
