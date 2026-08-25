# Action

Add the rest of the file tools, then the command tool. The mechanism is tested; what remains
is tools riding on it.

## First: finish the file tools

`write_file`, `edit_file`, `delete_file` into `tools.py`, joining `read_file`.

- **AC 9** - creating a file names the path it wrote.
- **AC 11** - changing part of a file leaves the rest **byte-identical**. Test it by writing
  three lines, changing the middle one, and asserting the other two are unchanged including
  their line endings. An edit that rewrites the whole file would pass a looser test.
- **AC 12** - deleting. **Settled with a stub, inside `tmp_path`, never by asking a live
  model.** The tool is called directly by the test; the model's judgement is not what is
  under test.

Every one of these tests writes only inside `tmp_path`.

## Then: the command tool

This is the one with teeth. `run_command`, using `subprocess` from the standard library -
prefer it over a dependency for something this well covered.

- **AC 14** - no fixed list of permitted programs. Assert the absence of an allowlist, so a
  future one has to delete a test rather than quietly appear.
- **AC 15** - stdout *and* stderr both come back, neither silently dropped.
- **AC 16** - a non-zero exit is reported as a failure, with its status, and never described
  as success. Test with a command that exits 1 and prints to both streams.
- **AC 26** - no output is reported as no output, not as failure.
- **AC 27** - a command that does not finish is stopped at the time limit and the user is told
  it was stopped. Test with a short limit and a sleep; `subprocess.TimeoutExpired` is the
  mechanism, and the process must actually be killed rather than left running.

**Safety, binding:** every test here uses harmless commands - `echo`, `python -c "print(...)"`,
a sleep for the timeout case. No deletes, no `git`, no network. Nothing outside `tmp_path`.
Live models are not part of this cycle at all.

## Watch for

**Windows.** `subprocess` behaves differently here than the examples in most documentation:
`shell=True` changes quoting, and a timeout may leave a child alive unless the process is
killed explicitly. Whatever is chosen, test the timeout case and assert the process is gone.

**The transcript.** Adding tools does not change existing behaviour, so the thirteen original
scenarios plus cycle 3's three must stay byte-identical. If they move, that is a regression,
not a legitimate change. Do not regenerate this cycle.

## Record

Full suite and the hermeticity check. `wc -l` and the test count against 656 and 87. Status
token for all 35. Say which AC each new test closes, and name anything the criteria demand
that `subprocess` makes awkward - that is worth knowing before the startup-line cycle rather
than after.
