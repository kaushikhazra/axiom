"""One screen of #85's drawing, with no model and no waiting.

**Run this in a real terminal.** It calls the same two functions a turn calls -
`note_tool` and `show_tool_result` - with results shaped like the ones real tools
return, so what appears is what #85 actually draws rather than a mock-up of it.

    uv run --project C:/Projects/axiom python .claude/loop/85-tool-lines/sample.py

It exists because most of #85 was already settled by 2026-09-08's transcripts -
thirty-six captured calls across five tools - and what those could not show is the
part that only exists at a terminal: the marks, the grey, and the two cuts. Those
are one screen, not fifteen rows of typing at a model.

Resize the window and run it again. The schedule row is the one that changes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from axiom import terminal  # noqa: E402

terminal.use_rendering(True)


def turn(name, arguments, result):
    """Exactly the pair a real turn calls, in the order it calls them.

    `show_tool_result` takes the transient working line back itself, so nothing
    here does it - anything extra would be this script drawing rather than #85.
    """
    terminal.note_tool(name, arguments)
    terminal.show_tool_result(result)


print(f"\n  terminal width: {terminal._width()} columns\n")

# AC 5 - a call with no arguments still gets its line.
turn("list_schedules", {}, "nothing is scheduled")

# AC 18, AC 19 - the identifier and the next run time. This is the row that loses
# its tail first, because the prompt text sits inside it.
turn(
    "schedule_prompt",
    {"cron": "*/1 * * * *", "prompt": "say TICK", "repeating": True},
    "scheduled 0e03cdcd: 'say TICK' on */1 * * * * (repeating), "
    "next at 2026-09-08 22:27 local\n"
    "schedules last only as long as this session\n"
    "a repeating job stops after 7 days",
)

# AC 6 - a call line too wide for the window, cut to one row.
turn(
    "run_command",
    {"command": "echo " + "the quick brown fox jumps over the lazy dog " * 8},
    "the quick brown fox jumps over the lazy dog",
)

# AC 8 - a result too large, cut to three rows and a count.
turn(
    "run_command",
    {"command": "dir C:\\Windows\\System32"},
    "\n".join(
        f"09/08/2026  10:{n:02d}    <DIR>          folder-{n}" for n in range(24)
    ),
)

# AC 9 - a tool that returned nothing still gets its line.
turn("run_command", {"command": "cd ."}, "(finished with no output)")

# AC 10 - a failure, drawn differently from a success. Judgement A is whether the
# mark on the row below catches your eye without being looked for.
turn("read_file", {"path": "ai-news-today.md"}, "# AI news, 2 September 2026")
turn(
    "read_file",
    {"path": "nope.txt"},
    "error: No such file or directory: C:\\Projects\\.tmp\\axiom-manual\\nope.txt",
)

# AC 21, AC 23 - the model's answer, for contrast. Everything above this line is
# axiom saying what happened; this line is the model talking.
print("\nI read the news file and could not find nope.txt. Here is what it said.\n")
