"""How much context a run can afford: the model's limit and the machine's."""

import psutil

SAFE_MEMORY_FRACTION = 0.70
KV_CACHE_BYTES_PER_VALUE = 2  # Ollama's default KV cache precision (f16)


def _find(info: dict, suffix: str):
    for key, value in info.items():
        if key.endswith(suffix):
            return value
    return None


def model_max_context(info: dict) -> int | None:
    """The model's own reported max context length, or None if it doesn't say."""
    value = _find(info, ".context_length")
    return int(value) if value is not None else None


def kv_cache_bytes_per_token(info: dict) -> int | None:
    """Bytes of KV cache one token of context costs, at Ollama's default f16 cache.

    2 (K+V) x layers x kv_heads x head_dim x bytes_per_value. Prefers the model's
    own reported key_length for head_dim over embedding_length / head_count - they
    differ for architectures with shared or sliding-window attention (e.g. gemma4,
    where key_length=512 but embedding_length/head_count=192). Overestimating this
    only makes the resulting token budget more conservative, never less safe.
    """
    num_layers = _find(info, ".block_count")
    num_kv_heads = _find(info, ".attention.head_count_kv")
    head_dim = _find(info, ".attention.key_length")
    if head_dim is None:
        embedding_length = _find(info, ".embedding_length")
        head_count = _find(info, ".attention.head_count")
        if not embedding_length or not head_count:
            return None
        head_dim = embedding_length / head_count
    if not num_layers or not num_kv_heads:
        return None
    return int(2 * num_layers * num_kv_heads * head_dim * KV_CACHE_BYTES_PER_VALUE)


def available_memory() -> int | None:
    """Bytes of memory currently free on this machine, or None if unknown."""
    try:
        return psutil.virtual_memory().available
    except Exception:
        return None


def memory_safe_context(info: dict, available_bytes: int | None) -> int | None:
    """How many tokens of context fit in SAFE_MEMORY_FRACTION of available memory."""
    if available_bytes is None:
        return None
    bytes_per_token = kv_cache_bytes_per_token(info)
    if not bytes_per_token:
        return None
    budget_bytes = int(available_bytes * SAFE_MEMORY_FRACTION)
    return budget_bytes // bytes_per_token


def effective_context(info: dict | None) -> int | None:
    """The smaller of what the model allows and what memory affords.

    None when neither can be established - the caller then lets Ollama pick.
    """
    if info is None:
        return None
    candidates = [
        limit
        for limit in (
            model_max_context(info),
            memory_safe_context(info, available_memory()),
        )
        if limit is not None
    ]
    return min(candidates) if candidates else None
