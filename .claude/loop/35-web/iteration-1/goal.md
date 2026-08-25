# Goal

Let a user ask axiom about things beyond what its model was trained on, and have it search
the web and read the pages it finds - meeting every one of the 30 acceptance criteria on
GitHub issue #35.

Two capabilities, deliberately independent: searching and reading. Either must keep working
while the other is failing, because DuckDuckGo throttling is routine rather than rare, and a
throttled search must not take away the ability to read an address the user hands over.

Done when: all 30 criteria of #35 are met, each with evidence recorded in a cycle log, and
the ones about real network behaviour - throttling, unreachable addresses, error statuses -
are evidenced by real runs rather than only by stubs.
