# Research Module Improvement Plan

## Current Problem

The research modules generate static templates, not real research:

```
research_module.py:
  - Generates search queries: "latest AI coding models 2026"
  - Doesn't actually search

adaptive_research_inputs.py:
  - Generates template findings: "Planning should record decomposition..."
  - Doesn't actually research

context_injector.py:
  - Injects past learnings
  - Doesn't research new solutions
```

## What's Needed

1. **Actually search the web** for solutions
2. **Understand context** of the goal
3. **Research how similar problems** are solved
4. **Include findings** in planning

## Proposed Solution

### 1. Update research_module.py

```python
def run_research(run_dir: Path, goal: str) -> dict:
    """Run research and generate context."""
    # 1. Analyze goal to understand what's needed
    analysis = analyze_goal(goal)
    
    # 2. Generate search queries based on analysis
    queries = generate_search_queries(analysis)
    
    # 3. Actually search the web
    findings = search_web(queries)
    
    # 4. Include findings in research context
    research_context = {
        "goal": goal,
        "analysis": analysis,
        "queries": queries,
        "findings": findings,
    }
    
    return research_context
```

### 2. Update adaptive_research_inputs.py

```python
def build_adaptive_research_inputs(run_dir: Path, findings: list) -> dict:
    """Build adaptive research inputs with real findings."""
    # Include real findings from web search
    research_inputs = {
        "findings": findings,
        "planning_inputs": extract_planning_inputs(findings),
    }
    
    return research_inputs
```

### 3. Integrate with web search

```python
def search_web(queries: list[str]) -> list[dict]:
    """Search the web for solutions."""
    findings = []
    for query in queries:
        results = web_search(query)
        findings.extend(results)
    return findings
```

## Implementation Plan

### Phase 1: Goal Analysis (1 week)

1. Create `goal_analyzer.py`
   - Analyze goal to understand what's needed
   - Extract key concepts
   - Identify similar problems

2. Update `research_module.py`
   - Use goal analyzer to understand context
   - Generate targeted search queries

### Phase 2: Web Search Integration (1 week)

1. Create `web_searcher.py`
   - Search the web for solutions
   - Extract relevant information
   - Filter and rank results

2. Update `research_module.py`
   - Use web searcher to find solutions
   - Include findings in research context

### Phase 3: Planning Integration (1 week)

1. Update `adaptive_research_inputs.py`
   - Include real findings from web search
   - Extract planning inputs from findings

2. Update `roadmap_planner.py`
   - Use research findings in planning
   - Create specific plans based on research

## Success Criteria

1. Research module actually searches the web
2. Findings are included in planning
3. Plans are specific to the goal, not generic
4. Example: Scaling feature identifies workspace configuration

## Timeline

- Phase 1: 1 week
- Phase 2: 1 week
- Phase 3: 1 week

**Total: 3 weeks**
