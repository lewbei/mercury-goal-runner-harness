---
description: Project-local Pi skill tree for the Mercury Goal Runner Harness.
---

# Project Pi Skills

This directory is the project-local Pi skill tree used by this repository.

Canonical project-local skill layout:

```text
.pi/skills/<skill-name>/SKILL.md
```

Legacy flat files such as `governance_model.md` and `mental_model.md` have been replaced by directory-based skill definitions:

```text
.pi/skills/governance-model/SKILL.md
.pi/skills/mental-model/SKILL.md
```

The top-level `skills/` directory is the packaged Pi skill tree and is outside the default harness cleanup boundary. Keep package-skill changes explicit and synchronized separately.

Authority reminder: skills can guide planning, implementation, repair, and evidence writing. Skills cannot certify DONE. Final status comes only from `certify_run.py` / `policy_engine.py` and their owned status artifacts.
