# Action

Twenty-eight of thirty-three. The five that are left are all **failure and whole-session**
criteria, and none can be settled by calling a function - they need a turn that goes wrong,
or a session that runs more than one.

1. **AC 30, 31, 32 - a job whose run fails.** A stub backend that raises on the scheduled
   turn. Prove three things separately: the failure is *said*; the session is still usable
   afterwards (the next typed line still gets an answer); and a repeating job still runs at
   its next time rather than being dropped for having failed once. AC 32 is the one that will
   be got wrong - a job that produces an empty reply is **not** a failure, and the code path
   that reports failure is the same one.
2. **AC 19 and AC 20 through a whole session.** Both hold in the store and neither has been
   driven end to end. `terminal.use_input` exists for exactly this now.
3. **AC 24 - a `/model` switch leaves jobs alone.** Neither cancelled nor duplicated. The
   schedule lives in `_chat`'s locals and a switch rebinds `run`, not `jobs`, so this should
   hold structurally - **prove it rather than reasoning it**, because "it is in a different
   variable" is the kind of argument that is true right up until someone moves the variable.
4. **AC 1 - a run with nothing scheduled says nothing about schedules.** Cheap, and it is the
   guard against a future cycle adding a startup line for a feature most sessions never use.
5. **Re-establish green between every revert and the next break.** Cycle 4 lost a
   measurement to a stripped import; this cycle lost one to a break that removed the readable
   half of a condition and left the working half behind. Both were caught by re-running.
6. `uv run pytest` - 695, green, and **watch the wall clock**. This cycle found a spinning
   thread because 14 fast tests took five seconds; the number is worth reading every time.

First thing to tackle: **AC 32, the empty reply that is not a failure.** It shares a code
path with AC 30, it is the one a reasonable implementation gets wrong, and getting it wrong
means every quiet scheduled job reports itself as broken.
