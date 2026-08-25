"""A server that starts and then never speaks.

For #43 AC 22 - "a server still not ready at the startup bound is given up on".
Ours, per CLAUDE.md: a test never fetches a server, and a criterion that needs
a real process gets a script this repo owns.
"""

import time

if __name__ == "__main__":
    # Long enough that the bound decides the outcome, never the sleep.
    time.sleep(600)
