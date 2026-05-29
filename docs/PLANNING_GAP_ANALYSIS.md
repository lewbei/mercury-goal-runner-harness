# Planning Framework Gap Analysis

## Research findings (2026)

### 1. Task decomposition
- Breaking complex tasks into sub-tasks is fundamental
- DAG-based execution for dependency-aware parallel execution
- Source: VMAO framework (arxiv.org/html/2603.11445v2)

### 2. Verification-driven adaptive replanning
- Verifier as coordination signal for multi-agent quality assurance
- Adaptive replanning to address gaps
- Source: VMAO framework

### 3. Context management
- Performance degradation after 35 minutes of human time
- Context drift is a fundamental challenge
- Source: Zylos research (zylos.ai/research/2026-01-16-long-running-ai-agents)

### 4. Long-horizon agents
- Handling 2-hour tasks autonomously
- Moving to 8-hour workdays by late 2026
- Task duration doubling every 7 months
- Source: Zylos research

### 5. Multi-agent orchestration
- Coordinating specialized agents
- Dependency-aware parallel execution
- Source: VMAO framework

## Our current planning system

### What we have
1. roadmap_planner.py - builds plan (strategy selection, milestones, local steps)
2. planning_search_tree.py - bounded search tree (MAX_DEPTH=5, MAX_ITERATIONS=4, MAX_NODES=64)
3. planning_coverage.py - coverage evidence (alternatives, assumptions, risk register)
4. plan_selector.py - selects best plan
5. plan_merger.py - merges plans
6. plan_completeness_gate.py - checks completeness
7. cross_run_learner.py - learns from past runs

### What we're missing

#### 1. DAG-based execution (ALREADY HAVE)
- We have plan_graph.json with nodes and edges
- Edges show dependencies: task -> artifact -> next task
- Gap: No parallel execution of independent steps (optimization)

#### 2. Verification-driven adaptive replanning (HIGH PRIORITY)
- We have certifier gates at the end
- Research says verifier should be coordination signal during planning
- Gap: No adaptive replanning based on verifier feedback

#### 3. Context management (MEDIUM PRIORITY)
- We don't address context drift
- Research says performance degrades after 35 minutes
- Gap: No context management for long-running tasks

#### 4. Long-horizon support (MEDIUM PRIORITY)
- We don't support multi-hour tasks
- Research says task duration is doubling every 7 months
- Gap: No support for tasks > 1 hour

#### 5. Multi-agent parallel execution (LOW PRIORITY)
- We have sequential agent execution
- Research says parallel execution improves quality
- Gap: No parallel agent execution

## Recommendations

### 1. Add DAG-based execution
- Build dependency graph from step_logs
- Execute independent steps in parallel
- Track step dependencies in plan_graph.json

### 2. Add verification-driven replanning
- Run verifier during planning (not just at end)
- Use verifier feedback to adjust plan
- Add replanning loop when verifier finds gaps

### 3. Add context management
- Track context window usage
- Summarize old context when approaching limits
- Add context refresh mechanism

### 4. Add long-horizon support
- Add checkpoint mechanism for multi-hour tasks
- Add progress tracking for long tasks
- Add resume capability for interrupted tasks

## Priority

1. Verification-driven replanning (HIGH) - catches mistakes earlier
2. Context management (MEDIUM) - needed for long tasks
3. Long-horizon support (MEDIUM) - future-proofing
4. Parallel execution of independent steps (LOW) - optimization (DAG already exists)
