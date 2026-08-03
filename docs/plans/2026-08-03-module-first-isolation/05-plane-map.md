# Plane map

Filled from `PLANE-MAP.md`. This is a draft against the current
implementation; Phase 9 verifies each row against the refactored code and
moves the stable content into `docs/dev/architecture.md`.

## System boundary

**System:** xcron — per-project schedule reconciliation onto native OS
schedulers (`launchd`, `cron`).

**Primary value delivered:** a project's schedule manifest is converged into
the host scheduler, reversibly and with visible drift.

**Last-known-good safety window:** the deployed native artifacts — plist,
managed crontab block, and wrapper scripts. They keep executing indefinitely
without xcron running. `project-state.json` is xcron's record of the last
successful convergence; it has no expiry, and `status` exists precisely because
it can be stale.

## Responsibilities and state

| Plane | Capabilities / actions | Trigger and cadence | Authoritative state and sole writer | Inputs | Outputs | Authority |
| --- | --- | --- | --- | --- | --- | --- |
| Data | scheduled job execution via generated wrapper; `operations.logs` reads and clears the evidence | per scheduler firing; operator-initiated reads | wrapper stdout/stderr/event logs — written by the scheduled process, read/cleared by `operations` | rendered wrapper, environment, working directory | process exit status, log and event files | the user's own account, via the host scheduler |
| Control | `validate`, `plan`, `status`, `apply`, `prune`, `inspect` | operator-initiated convergence | `project-state.json`, generated wrappers, plist / managed crontab block — written by `reconciliation` | normalized manifest, derived state, actual scheduler state | `ProjectPlan`, `StatusEntry`, `ApplyResult`, `SchedulerInspection` | user-level `launchctl` / `crontab`; no root |
| Management | `init`, `jobs` edits, `hooks` install/status/repair, `metrics` show/reset, configuration | operator / lifecycle | manifest YAML (`manifest`), workspace marker and layout (`workspace`), metrics store (`operations`), hook files (`agent_hooks`) | operator intent | typed change sets, validation messages | filesystem write access to the project and `~/.xcron` |

## Cross-plane contracts

| Contract | Producer | Consumer | Schema / version | Freshness | Compatibility rule | Bounds |
| --- | --- | --- | --- | --- | --- | --- |
| `NormalizedManifest` | `manifest` (management) | `reconciliation` (control) | in-process typed value | per invocation | additive fields only; unknown YAML keys rejected at load | bounded by manifest size |
| `project-state.json` | `reconciliation.apply` | `reconciliation.plan` | durable JSON; **needs an explicit `schema` discriminator** | may be arbitrarily stale — `status` is the authority | old-reader/new-writer test required | one file per project |
| native artifacts (plist, crontab block, wrapper) | `reconciliation` adapters | host scheduler (data) | file formats with xcron ownership markers | until the next `apply` or `prune` | ownership markers must never change meaning | one artifact set per project |
| wrapper log and event files | scheduled process (data) | `operations` (management view) | line-oriented text / JSONL | read-only tail | reader tolerates truncation and partial lines | path layout owned by `workspace` |
| outcome summary | `reconciliation` (control) | `operations` (management) | `OutcomeRecorder` port — **to be introduced in Phase 4** | per action | bounded counter summary, never per-job callbacks | one record per action invocation |
| workspace `marker.toml` | `workspace` (management) | every plane | TOML, `schema = 1` | until an explicit migration | unsupported version refuses with a recovery hint | one file per project |

## Degraded behaviour

| Failure | Continues | Waits or queues | Stops safely | Recovery path | Verification |
| --- | --- | --- | --- | --- | --- |
| xcron not installed or broken | **yes** — deployed jobs keep firing; this is the core availability property | — | — | reinstall; `status` reveals drift | drill: uninstall xcron, confirm a scheduled job still fires, reinstall, `status` reports converged |
| `project-state.json` missing or stale | `status` and `apply` (they query the scheduler) | — | `plan` reports everything as new | run `status`, then `apply` | test: delete derived state, assert `status` is correct and `plan` degrades visibly, not silently |
| Host scheduler unavailable (`launchctl` / `crontab` failure) | `validate`, `plan`, `jobs` edits | — | `status`, `apply`, `prune` stop with a typed backend error and no partial artifact write | retry once the scheduler responds | test: fake backend raising on every call; assert exit code 1 and no state mutation |
| Manifest invalid | `status`, `logs`, `metrics` | — | `plan` and `apply` refuse before touching artifacts | fix the manifest; `validate` | existing validation tests |
| Workspace marker missing | one release: warns and proceeds (decision 3) | — | thereafter: refuses with a recovery hint | `xcron init` | test both release behaviours |
| Metrics store unreadable | every action | — | `metrics show` reports empty rather than failing | `metrics reset` | test: corrupt metrics file, assert actions still succeed |

The first row is the property that justifies xcron's whole design: the control
plane is operator-initiated and the data plane is the host scheduler, so
control-plane unavailability never stops already-authorized work. It is
currently undrilled.

## Channel exposure

| Capability / action | SDK | CLI | REST | Web | Plane | Intentional omissions |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `home.init` | yes | yes | no | no | management | no remote channel exists |
| `manifest` load/validate | internal | via `validate` | no | no | management | not a public capability surface |
| `jobs` list / show | yes | yes | no | no | management | — |
| `jobs` add / update / enable / disable / remove | yes | yes | no | no | management | manifest edit only; never touches the scheduler |
| `schedules.validate` | yes | yes | no | no | control | — |
| `schedules.plan` | yes | yes | no | no | control | reads derived state; never mutates |
| `schedules.status` | yes | yes | no | no | control | queries the real scheduler |
| `schedules.inspect` | yes | yes | no | no | control | `--full` expansion is CLI-only presentation |
| `schedules.apply` | yes | yes | no | no | control | the only converging mutation |
| `schedules.prune` | yes | yes | no | no | control | removes xcron-owned artifacts only |
| `operations.logs` list / clear | yes | yes | no | no | data evidence / management | clear never deletes outside owned paths |
| `operations.metrics` show / reset | yes | yes | no | no | management | — |
| `hooks` install / status / repair | yes | yes | no | no | management | repository-local files only |
| `hooks` session-start / session-end | yes | yes | no | no | management | agent-invoked |

REST and Web are `no` by decision, not by omission: xcron is a local,
single-user tool and the standard says to add HTTP when remote, multi-user, or
multi-language use is real.

## State ownership violations to remove

Current, with the phase that removes each:

1. `reconciliation.status` and `reconciliation.apply` construct
   `MetricsService` and write `~/.xcron/metrics/metrics.json`, a state family
   `operations` owns. → Phase 4, via the `OutcomeRecorder` port.
2. `workspace`-shaped path knowledge is re-derived in `state_store`,
   `logging_paths`, and `metrics` independently. → Phase 5.
3. Project identity is inferred from the presence of a `schedules/` directory
   rather than validated from a marker, so an unrelated directory can be
   treated as an xcron project. → Phase 5.
4. `project-state.json` is a durable cross-invocation contract with no
   explicit schema discriminator. → Phase 5 contract test.

## Next earned separation

**Smallest useful seam:** the `OutcomeRecorder` port between reconciliation
(control) and operations (management). It is the only place where two planes
currently write one file, and it converts an implicit shared dependency into
one typed, bounded contract.

**Verification:** the sole-writer test for `metrics.json` plus a planted
forbidden import proving `reconciliation` cannot reach `operations`
implementation.

**Physical split justified now?** No. xcron has one process, one user, one
release cadence, and one failure domain. The data plane is already physically
separate — it is the host scheduler — which is the separation that matters,
and it was earned by design rather than by packaging.
