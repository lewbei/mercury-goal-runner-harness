# Mercury Goal Runner Harness v0.1

This harness controls Mercury V2 as a fast worker inside a verified goal-execution system.

## Core parts

1. Prompt Compiler  
Converts a rough user goal into a structured Goal Contract.

2. Goal Contract  
Defines the cleaned goal, final outputs, constraints, done criteria, and failure criteria.

3. Guarded Worker  
Executes one approved step at a time and reports evidence.

4. Trace Logger  
Records what happened during the run.

5. Certifier  
Checks evidence, required files, logs, and done criteria before marking DONE_PASS.

## Core rule

Mercury may propose, plan, execute, and report, but it cannot certify final success.

Evidence beats confidence.
