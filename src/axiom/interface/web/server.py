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
    (WebSession supplies its own, session_manager.py).

    Copied, not used directly: _lifespan adds the shared memory_adapter to the
    copy, and mutating the caller's own dict to do that would be a surprising
    side effect."""
    session_kwargs = dict(agent_kwargs)
    # Popped HERE, not inside _lifespan: _lifespan runs AFTER create_app returns,
    # so leaving these in session_kwargs would let any session constructed before
    # startup finishes build its own faculty -- reintroducing the per-session
    # faculty bug on a startup race. Removing them up front makes that
    # unreachable: a pre-startup session simply gets no observability (faculty
    # absent, observe defaulting False) instead of a second, port-conflicting one.
    observe_enabled = session_kwargs.pop("observe", False)
    trace_ws_port = session_kwargs.pop("ws_port", None)

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):
        # Constructing CognitiveMemoryAdapter loads the sentence-transformers
        # embedding model -- measured at ~22s. Built ONCE here, at server
        # startup, and injected into every WebSession's Agent. Previously each
        # session built its own, inline inside POST /api/agent/run, so the
        # first message of every new browser thread blocked ~22s before its
        # SSE stream even opened. Startup is the right place to pay it: uvicorn
        # simply isn't accepting requests yet.
        #
        # Shared, not just cached: this is a single-user local-first second
        # brain -- one memory store, not one per browser tab. It also removes
        # the hazard of two sessions opening the same SurrealKV file.
        from axiom.memory.adapter import CognitiveMemoryAdapter  # noqa: PLC0415
        from axiom.memory.config import MemoryConfig  # noqa: PLC0415

        mem_cfg = session_kwargs.get("memory_config") or MemoryConfig()
        logger.info("axiom-web: loading shared memory adapter ...")
        memory_adapter = CognitiveMemoryAdapter(mem_cfg)
        session_kwargs["memory_adapter"] = memory_adapter
        logger.info("axiom-web: shared memory adapter ready")

        # One faculty for the whole process, for the same reason: everything it
        # owns is process-global. Its WsBridgeSink binds a single TCP port, and
        # OTel's TracerProvider is a global singleton that silently ignores a
        # second set_tracer_provider(). Building one per session meant only the
        # FIRST session ever bound :ws_port -- every later session's sink failed
        # to bind, yet /api/trace-endpoint still handed that session's browser
        # its own dead token, which the live server then closed with 4001
        # Unauthorized. Net effect: the trace pane and PRAO phase indicator
        # worked in the first browser tab only, and failed silently everywhere
        # else (a page refresh re-rolls threadId, so it counts as a new tab).
        faculty = None
        if observe_enabled:
            from axiom.observability.config import ObservabilityConfig  # noqa: PLC0415
            from axiom.observability.faculty import ObservabilityFaculty  # noqa: PLC0415

            obs_config = ObservabilityConfig(tui_enabled=False, ws_port=trace_ws_port)
            faculty = ObservabilityFaculty(config=obs_config)
            # Called exactly ONCE, here. Sessions borrow this run_id; a session
            # calling new_run() would unregister these sinks and rebuild a
            # WsBridgeSink that cannot bind the port this one already holds.
            run_id = faculty.new_run()
            session_kwargs["faculty"] = faculty
            logger.info(
                "axiom-web: shared observability faculty ready (run=%s)", run_id
            )

        yield

        for session in _sessions.values():
            try:
                session.close()
            except Exception as exc:
                logger.warning("session close failed during shutdown: %s", exc)

        # The sessions above all BORROW memory_adapter (Agent._owns_memory is
        # False for them), so none of them consolidated or closed it. As its
        # owner, do it exactly once, after every session has finished with it.
        try:
            await memory_adapter.consolidate()
        except Exception as exc:
            logger.warning("shared memory consolidation failed: %s", exc)
        try:
            memory_adapter.close()
        except Exception as exc:
            logger.warning("shared memory close failed: %s", exc)

        # Same ownership rule: sessions borrowed the faculty (Agent._owns_faculty
        # is False for them), so none of them shut it down. Flush and close the
        # shared sinks once, here. Idempotent -- the faculty's own atexit handler
        # becomes a no-op after this.
        if faculty is not None:
            try:
                faculty.shutdown()
            except Exception as exc:
                logger.warning("shared faculty shutdown failed: %s", exc)

    app = FastAPI(title="axiom-web", lifespan=_lifespan)

    def _get_or_create_session(thread_id: str) -> WebSession:
        """Every session is constructed with the SAME session_kwargs, which
        carry the process-wide memory_adapter and faculty built in _lifespan.

        Multi-tab trace support now works, because no session builds its own
        faculty any more. It previously did NOT: each session constructed one,
        so the second tab onward failed to bind the already-held ws_port, and
        /api/trace-endpoint then handed that browser its own dead session's
        token -- which the live server closed with 4001 Unauthorized. The trace
        pane and PRAO phase indicator worked in the first tab only and failed
        silently in every other (a refresh re-rolls threadId, so it counted as
        a new tab). Verified after the change: three tabs, one shared token,
        phase indicator live in all three, zero bind errors."""
        session = _sessions.get(thread_id)
        if session is None:
            session = WebSession(**session_kwargs)
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
