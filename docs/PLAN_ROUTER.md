# Plan Router Boundary

`.agentic-pi/runtime/plan_router.py` is a strict router, not a plan generator.

## Current behavior

The strict router only checks that planner-owned plan files already exist:

```text
.agentic-runs/<run_id>/plans/*_plan.json
```

If no planner-owned plan exists, it fails closed with:

```text
STRICT_PLAN_ROUTER_REQUIRES_EXISTING_PLAN
```

It does not generate SIMPLE / MEDIUM / HARD substitute plans, does not write substitute artifacts, and does not certify DONE.

## Why

The old complexity-based router was useful for early harness slices, but it could make a run look more complete than it really was. The current cleanup direction is stricter:

```text
Planner agents produce plans.
Workers execute approved plans.
Policy decides.
Certifier writes final status.
```

## Authority boundary

Plan routing is not certification. Final status still comes only from:

```text
.agentic-pi/validators/certify_run.py
.agentic-pi/runtime/policy_engine.py
```
