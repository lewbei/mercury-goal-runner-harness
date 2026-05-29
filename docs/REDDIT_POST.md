# Reddit Post

## Title

I built a verification harness for AI coding agents — started with Mercury v2

## Subreddits

- r/LocalLLaMA
- r/MachineLearning
- r/artificial
- r/ClaudeAI
- r/cursor
- r/coding

## Body

This project started as a way to get better results from Mercury v2 (Inception Labs' coding model). I wanted to make sure the model was actually doing what it claimed — not just saying "DONE" without proof.

It evolved into Mercury Goal Runner Harness — a verification system that:

- Runs multi-level verification (planning, step, final)
- Provides deterministic status (CERTIFIED_DONE or FAILED)
- Works with any AI coding agent
- Includes 48 tests and health checks

The harness follows a QRSPI pipeline with verification at every stage:
INTAKE → RESEARCHING → DESIGNING → STRUCTURING → PLANNING
→ IMPLEMENTING → VALIDATING → CERTIFYING → DONE

Each phase produces artifacts. The certifier verifies all artifacts before certifying DONE.

It's open source and ready to use:
https://github.com/lewbei/mercury-goal-runner-harness

Would love to hear your feedback!
