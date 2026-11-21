# 01-survey, round 2: recent proof-search methods and what transfers

Round 1 is accepted. Read `../design/SPEC.md` (v1.1), `../design/LOOP.md`, and your own
`assessment.md` and `sources.md`. You may use the network. Write only inside `01-survey/`.

## Why this round

The project is moving from flat certificates to an iterated propose-and-verify loop
(`LOOP.md`), modelled on recent AI-assisted mathematics. Before leaning on that literature we
need it checked from primary sources, and we need to know what each method actually requires.

## Deliverables

1. `recent-methods.md` (about 2000 words). For each method family below: what the system
   does, what plays the role of proposer and of trusted evaluator, the scale of compute, what
   kind of statement it has actually proven or improved, and which results were independently
   checked. Cover at least: neural proof search against a proof-assistant kernel; program
   search with an automatic scorer; LLM agents writing formal proofs; SAT/SMT solvers with
   checkable proof logs for combinatorial results; anything from the last two years that
   applies these to combinatorial games or game solving. Use the newest primary sources you
   can open, and give the publication date of each.
2. Re-open and re-verify the round 1 sources that the design depends on most: the set-based
   retrograde analysis paper, the capture-quiet decomposition paper, the Coq tablebase
   generator, and the Mhalla and Prost 5x5 proof. For each give: full citation, where it was
   published and whether it was peer reviewed, a two-sentence account of the method in your
   own words, the exact numbers we quote, and a direct short quotation supporting each
   number. If a source cannot be opened or does not say what round 1 claimed, say so and
   correct `sources.md`.
3. `transfer.md` (about 800 words): a critique of `LOOP.md`. Is a strategy program expanded
   and checked by enumeration a sound and useful object? What is the closest prior work
   (strategy synthesis, reactive synthesis, inductive invariants, endgame strategies proven
   in proof assistants, chess endgame rule induction)? What would the symbolic step named in
   "Honest limits" require, and which existing tools could carry it? Rank three concrete next
   experiments by expected information per unit of effort.

## Rules

Same as round 1: `VERIFIED` only for claims you saw in an opened source; separate published
results from claims and speculation; report disagreements; append a "Round 2" section to
`REPORT.md` listing what could not be verified.
