# `process` branch

This orphan branch holds the project's **implementation artifacts** — story files, sprint
status, epic retrospectives, and the deferred-work ledger — under
`_bmad-output/implementation-artifacts/`. They were moved here from `master` (which keeps the
planning artifacts: PRD, architecture, UX, research, and specs) so the public tree carries the
design record without the working-process history.

The bmad skills read these files through a local worktree of this branch:

```
git worktree add .worktrees/process process
```

`.worktrees/` is gitignored on `master`, and the local bmad config points
`implementation_artifacts` at `.worktrees/process/_bmad-output/implementation-artifacts`.

This branch shares no history with `master` and carries no `.pre-commit-config.yaml`; commit
here with `PRE_COMMIT_ALLOW_NO_CONFIG=1` if the repo's pre-commit hook is installed.
