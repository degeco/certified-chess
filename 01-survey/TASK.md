# 01-survey: source-backed research assessment

Read `../chess-solving-research-2.md`, `../AGENTS.md` and `../design/SPEC.md` first.
You are the only agent allowed to use the network. Write only inside `01-survey/`.

## Goal

Produce the "initial deliverable" of the research brief: a concise assessment of whether and
how chess could be solved, built on sources you actually opened during this session.

## Deliverables

1. `assessment.md`, at most about 2500 words, with these sections:
   - What solving chess formally requires (ultra-weak, weak, strong solutions; which rules;
     what would count as a checkable proof).
   - Strongest relevant methods and results as of today.
   - Main obstacles and realistic computational constraints, with numbers.
   - Ranked shortlist of research directions, each with reasons and uncertainties.
   - Critique of `../design/SPEC.md`: is the proposed first experiment sound and informative?
     What would you change? Has it been done already?
2. `sources.md`: one row per claim used in the assessment.
   Columns: claim, value, source (author, year, title, URL or DOI), source type
   (peer-reviewed / preprint / thesis / project page / forum), date you accessed it, status.
   Status is `VERIFIED` only if you opened the source and saw the claim; otherwise
   `UNVERIFIED`. Never fill in a number from memory and mark it verified.
3. `small-boards.md`: what is published about chess on boards smaller than 8x8 and about our
   three start positions `mini4x4`, `mini4x5`, `mini5x5`: historical names, exact rules used
   in the publication (pawn double step? castling? promotion?), proven values, proof sizes,
   compute used. Flag every rule difference from our "mini" rules, because a published value
   only transfers if the rules match.

## Topics to cover

These are pointers for searching, not facts to repeat. Verify each one.

- Size of chess: legal position counts and estimates, game-tree size.
- Solved games and how: checkers, awari, nine men's morris, connect four, othello, hex on
  small boards, losing chess / antichess. For each: state-space size, proof size, compute,
  whether the proof was independently checked.
- Small-board chess results (3x3, 3x4, 4x4, 4x5, 5x5, 6x6).
- Endgame tablebases: 7-piece status, 8-piece progress, storage, how they are verified.
- Search methods for proving: proof-number search and its descendants, retrograde analysis,
  how the checkers proof combined them.
- Complexity theory of generalised chess.
- Formal verification applied to chess or game solving (proof assistants, SAT/SMT,
  verified tablebases or endgame strategies).
- Recent AI-assisted mathematics and proof search, and whether any of it applies to
  producing compact, checkable game proofs.
- What top engines do and do not establish about the value of the start position.

## Rules

- Prefer primary sources. Separate published results, experimental claims, conjecture and
  speculation in the text itself.
- If two sources disagree, report both.
- If something could not be found or verified, say so plainly.
- Finish with `REPORT.md` as described in `../AGENTS.md`, listing what you could not verify.
