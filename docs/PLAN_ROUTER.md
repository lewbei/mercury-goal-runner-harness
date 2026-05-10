# Plan Router (Deterministic Stub)

The current `plan_router.py` is a **deterministic stub** used for testing the harness. It does **not** invoke any real Mercury or Pi planner agents. Instead, it generates plan JSON based on the `complexity_level` of the goal contract:

- **SIMPLE** - plans a placeholder documentation file at the first `final_outputs` path.
- **MEDIUM** - plans a placeholder examples file at the first `final_outputs` path.
- **HARD** - plans a small `cli_tool.py` at the first `final_outputs` path. The script reads `data.csv` from the run folder and prints row and column counts.
- **RISKY / IMPOSSIBLE** - plans a placeholder output that should fail certification if the contract requires real executable behavior.

The router must not create final artifacts. Only the Guarded Worker executes selected plan steps and writes final outputs inside `.agentic-runs/<run_id>/`.

The stub is intentionally minimal and should be replaced with real planner agents that generate adaptive plans based on the goal contract. Until then, the stub is clearly marked in the source code.
