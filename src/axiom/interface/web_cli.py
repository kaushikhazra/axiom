"""
axiom-web entry point — M10 (design.md §9, D11).

Single-process, single-worker ONLY (design.md §2 -- approval_bridge.py's
pending-approval registry is in-process memory; a second uvicorn worker
would have a disjoint registry). Never pass --workers > 1 to uvicorn here.
"""

from __future__ import annotations

import argparse

import uvicorn

from axiom.interface.web.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="axiom-web", description="Axiom -- web UI server"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address. LAN exposure (e.g. 0.0.0.0) is an explicit opt-in.",
    )
    parser.add_argument("--port", type=int, default=8420, help="axiom-web's own port.")
    parser.add_argument(
        "--provider",
        choices=["claude", "local", "committee"],
        default=None,
        help="Same semantics as axiom-cli's --provider (M6/M7).",
    )
    parser.add_argument("--ollama-host", default=None)
    parser.add_argument("--working-dir", default=None)
    parser.add_argument(
        "--auto-approve-tools",
        action="store_true",
        default=False,
        help="Same semantics as axiom-cli's flag -- off by default.",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        default=False,
        help=(
            "Disable the M2 WebSocket trace bridge (US-04). On by default "
            "-- unlike axiom-cli, where --observe defaults off -- since a "
            "UI with an always-available-but-empty trace toggle is a worse "
            "experience than always running the (non-blocking) trace sink "
            "(design.md §6)."
        ),
    )
    parser.add_argument(
        "--trace-ws-port",
        type=int,
        default=8421,
        help="Port for the M2 WebSocket trace bridge (default 8421).",
    )
    args = parser.parse_args()

    agent_kwargs = {
        "provider": args.provider,
        "ollama_host": args.ollama_host,
        "working_dir": args.working_dir,
        "auto_approve_tools": args.auto_approve_tools,
    }
    if not args.no_trace:
        agent_kwargs["observe"] = True
        agent_kwargs["ws_port"] = args.trace_ws_port

    app = create_app(agent_kwargs)
    uvicorn.run(app, host=args.host, port=args.port)  # single-process, no --workers


if __name__ == "__main__":
    main()
