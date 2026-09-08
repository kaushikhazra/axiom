"""Drive axiom from a pipe, on a real clock, and timestamp every byte it says.

**Not a test, and it must not become one.** Nothing here asserts. It types lines
at a running axiom and writes down what came back and when, which is the half of
a manual pass a person cannot do accurately - the eye is fine at "did that read
correctly" and hopeless at "did that arrive before or after the other thing".

## Why a pipe works at all

A piped run normally cannot fire a schedule. `_next_line` only consults the clock
when the timed read returns `WAITING`, and a pipe fed from a file is never empty
- every `input()` returns at once until EOF, so `due()` is never reached and the
session leaves before a job's minute arrives.

Holding the pipe open and writing into it *slowly* is what fixes that. Between
writes the reader thread is genuinely blocked in `input()`, `Queue.get` times out
after `SCHEDULE_TICK`, and the loop looks at a real `datetime.now()` exactly as it
does for a person sitting still. Real croniter, real minute boundary, real turn.

## What it cannot see

The drawing. No tty means no composer, no accent, no `take_back_prompt`. Anything
about how a line *looks* stays a person's row at a real console - which is where
#80's ctrl+enter defect was found and is not a thing to be clever about.

## The step file

One step a line, blank lines and `#` ignored:

    send: every minute, tell me the time
    wait: 20
    at-second: 55          wait for the next real :55
    mark: the essay should still be streaming when the minute turns
    idle: 90               send nothing, just keep listening
    send: /exit
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SANDBOX = Path("C:/Projects/.tmp/axiom-manual")

# Anything the child buffers is a timestamp we have made up. Python block-buffers
# stdout the moment it is not a terminal, which would land a whole turn on one
# instant and make the only thing this script measures worthless.
#
# `PYTHONIOENCODING` for a different reason: a pipe on Windows gets the locale
# encoding, so an em-dash left axiom as one cp1252 byte and arrived here as a
# replacement character. That is this script mis-decoding axiom, not axiom
# mis-writing, and a transcript full of `?` is one nobody can quote from.
CHILD_ENV = {
    **os.environ,
    "PYTHONUNBUFFERED": "1",
    "PYTHONIOENCODING": "utf-8",
}


class Log:
    """Everything the child said, each line stamped when its first byte arrived.

    The stamp is taken at the *first* byte rather than at the newline, because a
    streamed reply arrives a token at a time and the question this whole script
    exists to answer is when a line started, not when it finished.
    """

    def __init__(self, path: Path) -> None:
        self._started = time.monotonic()
        self._lines: list[str] = []
        self._path = path
        self._lock = threading.Lock()

    def write(self, text: str, began: float | None = None) -> None:
        at = self._started if began is None else began
        stamp = f"{at - self._started:7.2f}"
        wall = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            row = f"{stamp}  {wall}  {text}"
            self._lines.append(row)
            print(row, flush=True)

    def save(self) -> None:
        self._path.write_text("\n".join(self._lines) + "\n", encoding="utf-8")


def _pump(stream, log: Log) -> None:
    """Read the child a character at a time and hand `Log` whole lines."""
    pending = ""
    began: float | None = None
    while True:
        char = stream.read(1)
        if not char:
            break
        if began is None:
            began = time.monotonic()
        if char == "\n":
            log.write(pending, began)
            pending, began = "", None
            continue
        pending += char
    if pending:
        log.write(pending, began)


def _steps(path: Path) -> list[tuple[str, str]]:
    steps = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        verb, _, rest = line.partition(":")
        steps.append((verb.strip(), rest.strip()))
    return steps


def main() -> None:
    script = Path(sys.argv[1])
    log_path = script.with_suffix(".log")
    log = Log(log_path)

    # The project interpreter directly, not `uv run`. `uv` sits between us and
    # axiom and has to relay a pipe it never has to relay at a console, and the
    # first run of this script died there: the banner arrived, the line we typed
    # did not, ollama never spawned a runner, and the child hung with nothing to
    # read. Resolved from this file rather than written down, so the tree can
    # still be renamed.
    argv = [
        str(REPO / ".venv" / "Scripts" / "python.exe"),
        "-c",
        "import axiom; axiom.main()",
        "--no-mcp",
    ]
    # An optional second argument, because some rows are about the *scheduler*
    # and a thinking model buries them. qwen3.5:9b takes two to five minutes a
    # turn, which is fine for AC 10 - a long turn is the point there - and fatal
    # for AC 11, where two jobs have to come due, run and finish inside one
    # minute for the ordering to be visible at all. Swapping to a model without
    # a thinking phase removes a confound rather than dodging the row: what is
    # under test is which job `due()` hands over first, not how the model writes.
    if len(sys.argv) > 2:
        argv += ["--model", sys.argv[2]]
    log.write(f"$ {' '.join(argv)}   (cwd {SANDBOX})")
    child = subprocess.Popen(
        argv,
        cwd=str(SANDBOX),
        env=CHILD_ENV,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=0,
    )
    reader = threading.Thread(target=_pump, args=(child.stdout, log), daemon=True)
    reader.start()

    try:
        for verb, value in _steps(script):
            if verb == "send":
                log.write(f"|| typed: {value}", time.monotonic())
                child.stdin.write(value + "\n")
                child.stdin.flush()
            elif verb == "wait":
                time.sleep(float(value))
            elif verb == "idle":
                time.sleep(float(value))
            elif verb == "at-second":
                target = int(value)
                while datetime.now().second != target:
                    time.sleep(0.05)
            elif verb == "mark":
                log.write(f"|| {value}", time.monotonic())
            else:
                raise SystemExit(f"unknown step {verb!r}")
    finally:
        try:
            child.stdin.close()
        except OSError:
            pass
        # Generous, because closing stdin does not stop a turn that is already
        # running - it only tells the reader thread to leave once the loop comes
        # back round. A `/exit` typed mid-turn waits for the turn, which is AC 10
        # working rather than a hang, and 30s was short enough to look like one.
        #
        # And saving comes after it whatever happens. The first AC 10 run lost a
        # seven minute log because this raised: a run that ends badly is the one
        # whose transcript is worth most, so nothing here may throw past `save`.
        try:
            child.wait(timeout=180)
        except subprocess.TimeoutExpired:
            log.write("|| child still running - killed", time.monotonic())
            child.kill()
        reader.join(timeout=5)
        log.write(f"|| exit status {child.returncode}", time.monotonic())
        log.save()


if __name__ == "__main__":
    main()
