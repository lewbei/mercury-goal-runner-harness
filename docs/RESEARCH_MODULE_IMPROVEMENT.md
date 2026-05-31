# Research Module Improvement Plan

## Current Problem

The research modules generate static templates, not real research:

```
research_module.py:
  - Generates search queries: "latest AI coding models 2026"
  - Doesn't think about the problem
  - Doesn't understand context
  - Doesn't iterate until confident

adaptive_research_inputs.py:
  - Generates template findings: "Planning should record decomposition..."
  - Doesn't think about solutions
```

## What's Needed

1. **Think about the problem** — understand context, reason about solutions
2. **Iterate until confident** — keep thinking until highest probability of success
3. **Use own knowledge** — leverage what the agent already knows
4. **Optionally search web** — supplement with web search when needed
5. **Include findings in planning** — create specific plans

## Proposed Solution

### 1. Iterative Thinking Process

```
RESEARCH PROCESS (ITERATIVE):
  1. Analyze goal
     ├── What is the user trying to do?
     ├── What similar problems exist?
     └── What solutions are known?

  2. Reason about solutions
     ├── What approaches exist?
     ├── What are the trade-offs?
     └── What's the best approach?

  3. Evaluate confidence
     ├── How confident are we in the solution?
     ├── What are the uncertainties?
     └── Do we need more information?

  4. If confidence is low:
     ├── Think more about the problem
     ├── Search web for more information
     ├── Refine reasoning
     └── Go back to step 2

  5. If confidence is high:
     ├── Include in planning
     ├── Create specific plans
     └── Proceed with implementation
```

### 2. Update research_module.py

```python
def run_research(run_dir: Path, goal: str, max_iterations: int = 5) -> dict:
    """Run research by thinking iteratively until confident."""
    iteration = 0
    confidence = 0.0
    findings = []
    
    while iteration < max_iterations and confidence < 0.8:
        iteration += 1
        
        # 1. Analyze goal to understand what's needed
        analysis = analyze_goal(goal, findings)
        
        # 2. Reason about solutions using own knowledge
        reasoning = reason_about_solutions(analysis, findings)
        
        # 3. Evaluate confidence
        confidence = evaluate_confidence(reasoning)
        
        # 4. If confidence is low, search for more information
        if confidence < 0.8:
            web_findings = search_web(reasoning.queries)
            findings.extend(web_findings)
        
        # 5. Log iteration
        log_iteration(iteration, confidence, reasoning)
    
    # 6. Generate final recommendations
    recommendations = generate_recommendations(reasoning, findings)
    
    return {
        "goal": goal,
        "iterations": iteration,
        "confidence": confidence,
        "analysis": analysis,
        "reasoning": reasoning,
        "findings": findings,
        "recommendations": recommendations,
    }
```

### 3. Confidence Evaluation

```python
def evaluate_confidence(reasoning: dict) -> float:
    """Evaluate confidence in the solution."""
    # How clear is the problem?
    problem_clarity = assess_problem_clarity(reasoning.analysis)
    
    # How well do we understand the solutions?
    solution_understanding = assess_solution_understanding(reasoning.approaches)
    
    # How confident are we in the best approach?
    approach_confidence = assess_approach_confidence(reasoning.best_approach)
    
    # Overall confidence
    confidence = (problem_clarity + solution_understanding + approach_confidence) / 3
    
    return confidence
```

### 4. Iteration Logging

```python
def log_iteration(iteration: int, confidence: float, reasoning: dict):
    """Log iteration for transparency."""
    print(f"Iteration {iteration}: confidence={confidence:.2f}")
    print(f"  Problem: {reasoning.analysis.summary}")
    print(f"  Best approach: {reasoning.best_approach.name}")
    print(f"  Uncertainties: {reasoning.uncertainties}")
```

## Implementation Plan

### Phase 1: Goal Analysis (1 week)

1. Create `goal_analyzer.py`
   - Analyze goal to understand what's needed
   - Extract key concepts
   - Identify similar problems

2. Update `research_module.py`
   - Use goal analyzer to understand context
   - Generate targeted analysis

### Phase 2: Reasoning Engine (1 week)

1. Create `reasoning_engine.py`
   - Reason about solutions using own knowledge
   - Identify approaches and trade-offs
   - Select best approach

2. Update `research_module.py`
   - Use reasoning engine to think about solutions
   - Generate recommendations

### Phase 3: Confidence Evaluation (1 week)

1. Create `confidence_evaluator.py`
   - Evaluate confidence in solutions
   - Identify uncertainties
   - Determine if more research is needed

2. Update `research_module.py`
   - Use confidence evaluator to iterate
   - Keep thinking until confident

### Phase 4: Web Search Integration (1 week)

1. Create `web_searcher.py`
   - Search the web for solutions
   - Extract relevant information
   - Filter and rank results

2. Update `research_module.py`
   - Use web searcher to supplement reasoning
   - Include web findings in research context

### Phase 5: Planning Integration (1 week)

1. Update `adaptive_research_inputs.py`
   - Include real findings from reasoning
   - Extract planning inputs from findings

2. Update `roadmap_planner.py`
   - Use research findings in planning
   - Create specific plans based on research

## Success Criteria

1. Research module thinks iteratively about the problem
2. Keeps thinking until confidence is high (≥ 0.8)
3. Uses own knowledge before searching
4. Web search is supplementary, not primary
5. Plans are specific to the goal, not generic
6. Example: Scaling feature identifies workspace configuration

## Timeline

- Phase 1: 1 week
- Phase 2: 1 week
- Phase 3: 1 week
- Phase 4: 1 week
- Phase 5: 1 week

**Total: 5 weeks**
