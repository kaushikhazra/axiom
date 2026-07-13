"""Throwaway probe: does smolagents' LiteLLMModel surface token counts on a
real Ollama call, or are they genuinely absent? Resolves whether null tokens
in the KIND-A trace are an access bug or Ollama-doesn't-return-usage."""

from smolagents import LiteLLMModel

m = LiteLLMModel(model_id="ollama_chat/qwen2.5:7b")

msgs = [
    {"role": "user", "content": [{"type": "text", "text": "Say hi in three words."}]}
]

print("=== calling model ===")
resp = m(msgs)
print("response type:", type(resp).__name__)
print("response repr (truncated):", repr(resp)[:300])

print("\n=== token-related attrs on the model ===")
for a in dir(m):
    if "token" in a.lower() or "usage" in a.lower():
        try:
            print(f"  m.{a} = {getattr(m, a)!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  m.{a} -> error {e}")

print("\n=== token/usage on the response object ===")
for a in dir(resp):
    if "token" in a.lower() or "usage" in a.lower():
        try:
            print(f"  resp.{a} = {getattr(resp, a)!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  resp.{a} -> error {e}")

# smolagents ChatMessage often carries raw provider response under .raw
raw = getattr(resp, "raw", None)
print("\n=== resp.raw usage ===")
print("  raw type:", type(raw).__name__ if raw is not None else None)
if raw is not None:
    print("  raw.usage:", getattr(raw, "usage", "NO .usage attr"))
    if isinstance(raw, dict):
        print("  raw['usage']:", raw.get("usage", "NO 'usage' key"))
