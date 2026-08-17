"""python3 -m agentic_tutor.ui  —  start the local tutor interface.

    --db         where the session's sqlite lives   (default: .tutor/session.db)
    --workspace  where uploaded zips are extracted  (default: .tutor/workspace)
    --port       default 8765
"""
from __future__ import annotations

import argparse
from pathlib import Path

from tutor.db import DB
from .server import App, serve


def main() -> None:
    ap = argparse.ArgumentParser(prog="agentic_tutor.ui")
    ap.add_argument("--db", default=".tutor/session.db")
    ap.add_argument("--workspace", default=".tutor/workspace")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--model", default="",
                    help="model for agent turns; empty uses survey.DEFAULT_MODEL")
    args = ap.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.workspace).mkdir(parents=True, exist_ok=True)
    serve(App(DB(args.db), args.workspace, model=args.model), port=args.port)


if __name__ == "__main__":
    main()
