"""
FastAPI app — M10 (design.md §3-§7): the axiom-web backend. Routes:

  POST /api/agent/run           -- one turn, SSE stream of AG-UI events
  POST /api/approval/{id}       -- resolve a pending tool-approval request
  POST /api/provider            -- switch a session's provider at runtime
  GET  /api/trace-endpoint      -- M2 WS trace bridge connection info

Sessions (WebSession, one per browser "thread") are created lazily, keyed
by threadId, and kept alive for the process lifetime -- consistent with
this project's single-user, local-first scope (design.md §2). All live
sessions are torn down cleanly on server shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from ag_ui.core import RunAgentInput
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from axiom.interface.web import approval_bridge
from axiom.interface.web.agui_bridge import stream_turn
from axiom.interface.web.session_manager import WebSession

logger = logging.getLogger("axiom.interface.web")

# threadId -> WebSession. Single-process only (see approval_bridge.py's
# own docstring for the same constraint, which this shares).
_sessions: dict[str, WebSession] = {}


class ApprovalDecision(BaseModel):
    approved: bool


class ProviderRequest(BaseModel):
    threadId: str
    provider: str | None = None


def _latest_user_text(body: RunAgentInput) -> str:
    """D19 -- pull the newest UserMessage's content out of RunAgentInput's
    full messages list. HttpAgent (the JS client, @ag-ui/client) resends
    the whole thread's messages on every run; axiom's own turn-based Agent
    only needs the newest one, since run_turn() carries its own memory."""
    for message in reversed(body.messages):
        if message.role == "user":
            return message.content or ""
    return ""


def create_app(agent_kwargs: dict) -> FastAPI:
    """agent_kwargs: passed through to every WebSession's Agent() (provider,
    working_dir, ollama_host, auto_approve_tools, ws_port, ...) -- the same
    construction surface axiom-cli's Agent already has, minus approval_fn
    (WebSession supplies its own, session_manager.py)."""

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        yield
        for session in _sessions.values():
            try:
                session.close()
            except Exception as exc:
                logger.warning("session close failed during shutdown: %s", exc)

    app = FastAPI(title="axiom-web", lifespan=_lifespan)

    def _get_or_create_session(thread_id: str) -> WebSession:
        """Every session is constructed with the SAME agent_kwargs, including
        the same fixed ws_port when observability is enabled. For the
        realistic single-browser-tab target usage this is exactly right --
        one session, one WS bridge, no conflict. A second concurrent
        session (a second tab) would attempt to bind the same port again;
        ObservabilityFaculty already catches that construction failure and
        logs it rather than raising (observability/faculty.py), so the
        second session's Agent still works -- it just won't have a live
        trace pane. Not engineered further: no AC in this milestone
        requires simultaneous multi-tab trace support."""
        session = _sessions.get(thread_id)
        if session is None:
            session = WebSession(**agent_kwargs)
            _sessions[thread_id] = session
        return session

    @app.post("/api/agent/run")
    async def run_turn(body: RunAgentInput):
        user_input = _latest_user_text(body)
        if not user_input.strip():
            raise HTTPException(400, "empty input")
        session = _get_or_create_session(body.thread_id)
        return StreamingResponse(
            stream_turn(session, user_input, body.thread_id),
            media_type="text/event-stream",
        )

    @app.post("/api/approval/{approval_id}")
    async def resolve_approval(approval_id: str, body: ApprovalDecision):
        try:
            resolved = approval_bridge.resolve(approval_id, body.approved)
        except ValueError as exc:
            # dryrun-design-2 W1: already-resolved -- 409, not an unhandled 500.
            raise HTTPException(409, str(exc)) from exc
        if not resolved:
            raise HTTPException(
                404, "no such pending approval (already resolved or expired)"
            )
        return {"ok": True}

    @app.post("/api/provider")
    async def set_provider(body: ProviderRequest):
        session = _get_or_create_session(body.threadId)
        try:
            session.set_provider(body.provider)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"provider": body.provider}

    @app.get("/api/trace-endpoint")
    async def trace_endpoint(threadId: str):
        # design.md D21: lazily create/reuse threadId's own session (same
        # helper every other route uses) instead of scanning _sessions for
        # any live one -- TracePane fetches on MOUNT, before any turn has
        # run, so without this the route always 503'd in that exact flow.
        session = _get_or_create_session(threadId)
        config = session._agent.observability_config
        if config is None or config.ws_port is None:
            raise HTTPException(503, "observability not enabled")
        return {
            "ws_url": f"ws://{config.ws_host}:{config.ws_port}",
            "ws_token": config.ws_token,
        }

    return app
