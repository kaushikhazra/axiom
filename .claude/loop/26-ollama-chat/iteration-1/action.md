# Action

Stand up the round trip: a program that starts, takes a typed line, sends it to Ollama, and prints the reply.

First thing to tackle: **one message in, one real reply out.** Everything else in the issue hangs off this — multi-turn needs a turn, error handling needs a call that can fail, configuration needs something to configure. Get `uv` set up, the `ollama` package installed, and a single exchange working against `qwen2.5:7b` on localhost.

Do not attempt the other criteria this cycle. Prove the round trip, run it, paste the transcript into the cycle log, then let Observe decide what comes next.
