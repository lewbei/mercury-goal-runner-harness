# Governance Model

This harness uses a constitutional executor model.

Branches:
1. Constitution: hard rules and forbidden actions.
2. CEO / Orchestrator: routes, approves, stops, requests repair.
3. Planners: propose plans.
4. Skeptic: attacks risks and fake-DONE.
5. Worker: executes one approved step.
6. Supervisor: watches drift and repeated failure.
7. Certifier: decides PASS / FAIL / BLOCKED from evidence.

Core rule:
Planner proposes.
Worker executes.
Supervisor watches.
Certifier decides.
Mercury cannot certify itself.
