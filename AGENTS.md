# Rules for every agent working in this repository

Project: research toward solving chess (see `chess-solving-research-2.md`).
Architecture and shared formats: `design/SPEC.md`. Read both before starting.

## Roles

- The designer (Claude, in the lead session) owns `design/` and the task briefs. Do not edit them.
  If the spec is wrong or ambiguous, do not silently deviate: write the issue in your
  `REPORT.md` under "Spec issues" and pick the most conservative reading.
- Each agent owns exactly one numbered folder and writes only inside it.

## Hard constraints

- Stay inside your own folder. Read other folders only where your TASK.md says so.
- Install nothing: no pacman, yay, pip, npm, cargo, go get, no sudo. Use only what is on the
  machine: g++ / clang (C++17), Python 3.14 standard library, go, make.
  If a missing tool would clearly help (a SAT/SMT solver, a proof assistant, a library), do
  not install it: name it in `REPORT.md` under "Tools wanted" with the reason. The lead
  session decides and installs.
- No network, except the `01-survey` agent.
- This is a 4-core laptop. Build with at most `-j4`. No single command may run longer than
  5 minutes or use more than 4 GB of RAM. Put a size or time limit on every search.
- No git push, no email, no messages, nothing outside this directory tree.

## Research discipline

- Correctness over plausibility. A number you did not compute or read in a source you opened
  is a hypothesis; label it so.
- Every result must come with the exact command that reproduces it.
- Tests are part of the deliverable. A failing test is reported as failing, never hidden,
  skipped or loosened to make it pass.

## Time

Your whole session is cut off after 50 minutes of wall clock, and a cut-off session leaves no
report. So: create `REPORT.md` as soon as the first result exists and update it after every
experiment. Never wait on a background job longer than 5 minutes; if an experiment needs
more, shrink it or split it, and say so in the report.

## When you finish

Write `REPORT.md` in your folder: what was built, how to build and test it (exact commands),
the actual test output, measured numbers, known gaps, spec issues. Keep it short and factual.
