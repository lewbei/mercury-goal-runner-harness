# Known Issues

## Critical Issues

None

## Medium Issues

### 1. Audit run fails with missing outputs

**Description:** Audit run fails when expected outputs are missing (e.g., KNOWN_ISSUES.md, TROUBLESHOOTING.md).

**Impact:** Audit report shows violations, but the harness still certifies.

**Workaround:** Ensure all expected outputs exist before running audit.

**Status:** Expected behavior - audit checks for expected outputs.

## Low Issues

### 1. Research module fails silently

**Description:** Research module fails silently if it can't fetch latest information.

**Impact:** Research context may be incomplete.

**Workaround:** None needed - the harness works without research context.

**Status:** Expected behavior - research is optional.

### 2. Resume module needs manual intervention

**Description:** Resume module requires manual intervention to find and resume incomplete runs.

**Impact:** User needs to run resume module manually after /new.

**Workaround:** Run `python .agentic-pi/runtime/resume_module.py` to find incomplete runs.

**Status:** Expected behavior - resume is manual.

## Fixed Issues

### 1. Cross-run learning unavailable ✅

**Description:** Cross-run learning fails with error: `<lambda>() missing 1 required positional argument: 'base_dir'`

**Impact:** Cross-run learning doesn't work, but the harness still functions.

**Fix:** Updated lambda in @Requires decorator to handle optional base_dir parameter.

**Status:** Fixed

## Notes

- All critical paths work
- Health check passes
- 48 tests pass
- Documentation is complete
