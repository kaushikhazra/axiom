"""What this console reports for a key, as prompt_toolkit sees it.

**Not a test - an instrument.** It is here because it is the thing that found
#80's ctrl+enter defect, and because the next person to doubt a key binding
should not have to write it again.

    cd C:/Projects/.tmp/axiom-manual
    uv run --project C:/Projects/axiom python C:/Projects/axiom/tests/whatkey.py

Press enter, then ctrl+enter, then ctrl+j. Press q to leave.

The first two lines are the answer. `Win32Input.__init__` chooses between two
readers on `_is_win_vt100_input_enabled()`, and they report ctrl+enter
differently:

    ConsoleInputReader        escape, c-j    the ctrl state is set, so Escape
                                             is prefixed
    Vt100ConsoleInputReader   c-j            a bare line feed; the modifier is
                                             not encoded in a VT stream

`compose_keys` binds both. It bound only the first until 2026-09-03, and since
`_is_win_vt100_input_enabled()` is true on every modern Windows console - it
asks whether the console *accepts* ENABLE_VIRTUAL_TERMINAL_INPUT, and they all
do - the bare key matched nothing, fell through to prompt_toolkit's own `c-j`
default, and sent the message.

**No PromptSession, no Application, no run_in_terminal.** The three things that
took the machine down under pytest are all absent, which is what makes this safe
to run at a real terminal. It is still not a test and must not become one:
`tests/test_multiline.py` reads the binding table instead.
"""

import sys


def main() -> None:
    from prompt_toolkit.input.win32 import Win32Input, _is_win_vt100_input_enabled

    source = Win32Input(sys.stdin)

    print()
    print(f"  VT input enabled : {_is_win_vt100_input_enabled()}")
    print(f"  reader in use    : {type(source.console_input_reader).__name__}")
    print()
    print("  ConsoleInputReader      - ctrl+enter is escape, c-j")
    print("  Vt100ConsoleInputReader - ctrl+enter is a bare c-j")
    print()
    print("  Press enter, then ctrl+enter, then ctrl+j. Press q to leave.")
    print()

    with source.raw_mode():
        while True:
            pressed = source.read_keys()
            for key in pressed:
                print(f"    {key.key!s:<24} data={key.data!r}")
            if any(key.data == "q" for key in pressed):
                break


if __name__ == "__main__":
    main()
