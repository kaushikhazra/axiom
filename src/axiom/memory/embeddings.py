"""EmbeddingService — wraps sentence-transformers all-MiniLM-L6-v2."""

from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EmbeddingService:
    MODEL_NAME = "all-MiniLM-L6-v2"
    DIMENSIONS = 384

    def __init__(self) -> None:
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed")

    def warmup(self) -> None:
        """Load model eagerly; subsequent embed() calls do not incur model-load latency."""
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("EmbeddingService: loading %s ...", self.MODEL_NAME)
        self._model = SentenceTransformer(self.MODEL_NAME)
        logger.info("EmbeddingService: model ready (dim=%d)", self.DIMENSIONS)

    def _encode_sync(self, text: str) -> list[float]:
        """Sync encode; called in executor thread."""
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def _encode_batch_sync(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    async def embed(self, text: str) -> list[float]:
        """Encode text; offloads to executor to avoid blocking event loop."""
        loop = (
            asyncio.get_running_loop()
        )  # W1 fix: get_event_loop() deprecated in 3.10+
        return await loop.run_in_executor(self._executor, self._encode_sync, text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor, self._encode_batch_sync, texts
        )

    def shutdown(self) -> None:
        """G2 fix: shut down the ThreadPoolExecutor cleanly.

        Called by CognitiveMemoryAdapter.close() at session end.
        wait=False: don't block if an embed is in flight (it will be abandoned,
        which is acceptable at shutdown — no user turn is pending).
        """
        self._executor.shutdown(wait=False)
