# Prompt Compiler Seed Eval

Status: diagnostic seed set, not certification evidence.

Purpose: test whether a prompt improver reduces known prompt failures instead of only making prompts sound cleaner.

Run boundaries:

```text
raw prompt -> improved prompt candidate -> deterministic seed rubric score
```

This eval does not prove arbitrary prompt coverage. It checks a small first set of failure modes:

- messy raw prompt
- contradiction
- false DONE trap
- research evidence
- coding minimal patch
- planning skepticism
- user voice preservation
- missing information
- tool-use control
- prompt compression

Commands:

```cmd
python .agentic-pi/validators/validate_prompt_eval_case.py .agentic-pi/diagnostics/prompt_compiler_eval/cases
python .agentic-pi/runtime/run_prompt_compiler_eval.py --generate-v0 --cases-dir .agentic-pi/diagnostics/prompt_compiler_eval/cases
```

Authority boundary:

```text
Prompt eval scores are advisory diagnostics.
They cannot certify task DONE.
They cannot replace verifier evidence.
```
