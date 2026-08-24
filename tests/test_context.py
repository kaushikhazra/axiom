"""The context arithmetic, directly.

test_context_window.py drives these through main() to prove the startup line
is right. These pin the functions themselves, including the KV-cache fallback
that only fires for architectures which do not report a key_length.
"""

from axiom import context

QWEN = {
    "qwen2.context_length": 32768,
    "qwen2.block_count": 28,
    "qwen2.attention.head_count": 28,
    "qwen2.attention.head_count_kv": 4,
    "qwen2.embedding_length": 3584,
}


def test_the_context_length_is_found_whatever_the_architecture_prefix():
    assert context.model_max_context({"llama.context_length": 8192}) == 8192
    assert context.model_max_context({"gemma4.context_length": 131072}) == 131072


def test_a_model_that_reports_no_context_length_yields_none():
    assert context.model_max_context({"qwen2.block_count": 28}) is None


def test_a_reported_key_length_is_preferred_over_the_derived_one():
    """gemma4 reports key_length=512 where embedding/head_count gives 192 -
    using the derived value would under-count the cache by more than half.
    """
    reported = context.kv_cache_bytes_per_token(
        {
            "gemma4.block_count": 2,
            "gemma4.attention.head_count_kv": 1,
            "gemma4.attention.key_length": 512,
            "gemma4.embedding_length": 192,
            "gemma4.attention.head_count": 1,
        }
    )
    assert reported == 2 * 2 * 1 * 512 * 2


def test_head_dim_falls_back_to_embedding_over_head_count():
    assert context.kv_cache_bytes_per_token(QWEN) == int(2 * 28 * 4 * (3584 / 28) * 2)


def test_kv_cache_cost_is_unknown_without_layers_or_kv_heads():
    assert context.kv_cache_bytes_per_token({"m.context_length": 100}) is None


def test_memory_budget_is_unknown_when_memory_is_unknown():
    assert context.memory_safe_context(QWEN, None) is None


def test_memory_budget_uses_the_safe_fraction():
    per_token = context.kv_cache_bytes_per_token(QWEN)
    available = 10**10
    expected = int(available * context.SAFE_MEMORY_FRACTION) // per_token
    assert context.memory_safe_context(QWEN, available) == expected


def test_effective_context_takes_the_smaller_of_the_two(monkeypatch):
    """A model may allow more than the machine can hold - the machine wins."""
    monkeypatch.setattr(context, "available_memory", lambda: 10**8)
    assert context.effective_context(QWEN) == context.memory_safe_context(QWEN, 10**8)


def test_effective_context_falls_back_to_the_model_when_memory_is_unknown(monkeypatch):
    monkeypatch.setattr(context, "available_memory", lambda: None)
    assert context.effective_context(QWEN) == 32768


def test_effective_context_is_none_when_the_model_could_not_be_asked():
    assert context.effective_context(None) is None
