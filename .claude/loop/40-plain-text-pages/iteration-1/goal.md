# Goal

Let a user read a page served as plain text - a raw source file, a README, a licence,
robots.txt - the same way they read an HTML one, meeting every one of the 12 acceptance
criteria on GitHub issue #40.

#35 gave axiom `fetch_page`, and it reads HTML well. It reads nothing else at all.
`trafilatura.extract` is an HTML extractor: handed a `text/plain` body it returns None, and
the user is told the page "has no readable text". The page said plenty.

The failure that matters is not the message. It is what happens next: the model, told the
page was empty, answers from memory instead - confidently, about a page that was right
there and readable. #35 AC 12 was replaced for this same reason, because a 7B model asked
to be candid about what it did not know was not candid. Axiom has to be the one that tells
the truth about what it retrieved.

Done when: all 12 criteria of #40 are met, each with evidence recorded in a cycle log; the
criteria about content types are evidenced against responses that were really served rather
than only hand-built ones; and the existing HTML behaviour is provably unchanged.
