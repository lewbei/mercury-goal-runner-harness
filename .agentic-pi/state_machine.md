# Mercury Goal Runner State Machine

INIT_READY
  -> CONTRACT_READY
  -> PLANNING
  -> PLAN_READY
  -> EXECUTING
  -> OBSERVING
  -> CERTIFYING
  -> DONE_PASS | DONE_FAIL | BLOCKED | NEED_USER | MAX_STEPS_REACHED

Rules:
- No raw user goal is executed directly.
- A Goal Contract must exist before planning.
- A plan must exist before execution.
- A step log must exist before certification.
- Only certifier logic writes certification.json and final_status.md.
- If the same failure repeats twice, mark BLOCKED.
- If evidence is missing, do not mark DONE_PASS.
