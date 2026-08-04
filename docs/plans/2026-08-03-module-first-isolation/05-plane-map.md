# Plane map

**Verified against the implemented code on 2026-08-04 (Phase 9). The stable
content now lives in [`docs/dev/architecture.md`](../../dev/architecture.md),
under "Planes" and "Channel exposure and parity", and that file is
authoritative.** What remains here is the record of what verification changed,
because a draft that silently becomes correct teaches nothing.

Every row of the degraded-behaviour table is now drilled. `tests/degraded/`
holds the cross-cutting drills; the workspace-marker and manifest-validation
rows are drilled inside the lane of the module that owns the state.

## What verification changed

**Row 3 of the degraded table was wrong.** The draft claimed a failing host
scheduler stops `apply` "with a typed backend error and no partial artifact
write". Wrapper scripts are in fact written *before* the crontab, because the
crontab entries have to reference their paths. What is true, and what
`test_a_failing_scheduler_write_leaves_the_durable_record_untouched` asserts,
is that no scheduler entry changes and no durable record is written — so the
orphaned wrappers are inert and the next successful `apply` overwrites them.
The error is also not typed: an unwritable crontab surfaces as `OSError`.

**Row 6 understated the store.** The draft said `metrics show` "reports empty
rather than failing". The store also *heals*: unreadable content is discarded
and the next write produces a valid document. Both halves are drilled.

**The channel exposure table listed an operation that does not exist.** There
is no `hooks session-start`, and `session_end` is SDK-only — there is no CLI
verb for it. The corrected table in `architecture.md` says so explicitly rather
than leaving the asymmetry to be discovered.

**`home.init` is now `workspace`.** Phase 5 folded `capabilities/home` into
`workspace/initializer.py`. The SDK surface is still `client.home.initialize`,
which is a channel-facing name for a workspace capability, and the table names
both.

**The `project-state.json` schema discriminator is still open.** The draft
marked it "needs an explicit `schema` discriminator" and Phase 5 chose a
different mechanism: `tests/modules/reconciliation/test_durable_state_format.py`
pins the literal key set from outside and separately proves a document holding
only the required keys still loads. That answers "can an older file still be
read", which was the live risk. It does not answer "how does a reader recognize
a format it is too old to understand", which is what a discriminator is for.
Carried forward as an open item in `architecture.md`, not silently closed.

## What verification confirmed

The four state-ownership violations the draft listed are all removed:

1. Two capabilities writing `metrics.json` — closed in Phase 4 by the
   `OutcomeRecorder` port. `operations` is the sole writer, enforced by
   `tests/architecture/test_module_edges.py`.
2. Workspace-shaped path knowledge re-derived in three places — closed in
   Phase 5; `workspace` owns the layout and everything else asks it.
3. Project identity inferred from a `schedules/` directory — closed in Phase 5
   by the marker, advisory for one release per decision 3.
4. `project-state.json` without a schema discriminator — see above; the
   compatibility half is closed, the discriminator is not.

The "next earned separation" the draft named — the `OutcomeRecorder` port — was
taken in Phase 4 and is verified by the sole-writer test plus a planted
forbidden import. The draft's conclusion that no *physical* split is justified
still holds, for the reason it gave: the data plane is the host scheduler, so
the separation that matters was earned by design rather than by packaging.
