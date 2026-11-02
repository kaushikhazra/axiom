# Action — cycle 2

Read `gh issue view 95` first, then `logs/cycle-1.md`. The constraint it ended on: 15 of 22,
and the seven owed rows are 4, 7, 8, 10, 14, 20, 21.

Cycle 1 ended with code written and not run for the rows below (a hold on heavy work came
from the orchestrator). So first, once the hold is lifted:

1. Run `tests/test_memory.py`, then the suite (`PYTHONPATH=src`; the checkout's venv does
   not import `axiom`). Expect the 9 baseline colour/rendering failures and nothing new.
   Rows these tests are meant to move: 4 (`memory: unavailable` wording), 14, 20. README
   section (row 8) is already written.
2. Row 21: drive a real server being killed mid-session with the fake server (a process
   this repo owns). Show the next reply says memory is unavailable and the chat goes on.
3. Row 7 is not a code question. It needs the owner: uv's own package cache and, if no
   Python 3.12 is present, a Python download, both land outside the project folder. Either
   the criterion names them or the install runs with `--no-cache`. Do not pick.
4. Rows 10 and 11 need the live pair again after the recall fix: set up is done in
   `C:/Projects/.tmp/axiom-synaptra-live/project` (HF_HOME there too). **Check the GPU and
   RAM first, tell Velasari before the run, unload and tell her after.** Session 1 stores,
   session 2 asks, and the Synaptra store is read to show the memory is there.

Then stop. Cycle 3 is whatever this cycle's log names, and the release blocker (Synaptra on
mcp 2.x before any axiom release) stays on #95.
