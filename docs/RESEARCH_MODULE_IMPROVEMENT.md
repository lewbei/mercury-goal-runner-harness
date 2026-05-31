# Research Module Improvement Plan

## Current Problem

The research modules generate static templates, not real research:

```
research_module.py:
  - Generates search queries: "latest AI coding models 2026"
  - Doesn't think about the problem
  - Doesn't understand context

adaptive_research_inputs.py:
  - Generates template findings: "Planning should record decomposition..."
  - Doesn't think about solutions
```

## What's Needed

1. **Think about the problem** — understand context, reason about solutions
2. **Use own knowledge** — leverage what the agent already knows
3. **Optionally search web** — supplement with web search when needed
4. **Include findings in planning** — create specific plans

## Proposed Solution

### 1. Think First, Search Second

```
RESEARCH PROCESS:
  1. Analyze goal
     ├── What is the user trying to do?
     ├── What similar problems exist?
     └── What solutions are known?

  2. Reason about solutions
     ├── What approaches exist?
     ├── What are the trade-offs?
     └── What's the best approach?

  3. Optionally search web
     ├── Is web search available?
     ├── Is more information needed?
     └── What to search for?

  4. Include in planning
     ├── What did we learn?
     ├── What's the recommended approach?
    └── What should the plan include?
```

### 2. Update research_module.py

```python
def run_research(run_dir: Path, goal: str) -> dict:
    """Run research by thinking about the problem."""
    # 1. Analyze goal to understand what's needed
    analysis = analyze_goal(goal)
    
    # 2. Reason about solutions using own knowledge
    reasoning = reason_about_solutions(analysis)
    
    # 3. Optionally search web for more information
    web_findings = []
    if should_search_web(reasoning):
        web_findings = search_web(reasoning.queries)
    
    # 4. Combine reasoning and web findings
    research_context = {
        "goal": goal,
        "analysis": analysis,
        "reasoning": reasoning,
        "web_findings": web_findings,
        "recommendations": generate_recommendations(reasoning, web_findings),
    }
    
    return research_context
```

### 3. Goal Analysis

```python
def analyze_goal(goal: str) -> dict:
    """Analyze goal to understand what's needed."""
    # Extract key concepts
    concepts = extract_concepts(goal)
    
    # Identify similar problems
    similar_problems = identify_similar_problems(concepts)
    
    # Understand context
    context = understand_context(goal, concepts)
    
    return {
        "concepts": concepts,
        "similar_problems": similar_problems,
        "context": context,
    }
```

### 4. Reasoning

```python
def reason_about_solutions(analysis: dict) -> dict:
    """Reason about solutions using own knowledge."""
    # What approaches exist?
    approaches = identify_approaches(analysis)
    
    # What are the trade-offs?
    trade_offs = analyze_trade_offs(approaches)
    
    # What's the best approach?
    best_approach = select_best_approach(approaches, trade_offs)
    
    return {
        "approaches": approaches,
        "trade_offs": trade_offs,
        "best_approach": best_approach,
    }
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

### Phase 3: Web Search Integration (1 week)

1. Create `web_searcher.py`
   - Search the web for solutions
   - Extract relevant information
   - Filter and rank results

2. Update `research_module.py`
   - Use web searcher to supplement reasoning
   - Include web findings in research context

### Phase 4: Planning Integration (1 week)

1. Update `adaptive_research_inputs.py`
   - Include real findings from reasoning
   - Extract planning inputs from findings

2. Update `roadmap_planner.py`
   - Use research findings in planning
   - Create specific plans based on research

## Success Criteria

1. Research module thinks about the problem
2. Uses own knowledge before searching
3. Web search is supplementary, not primary
4. Plans are specific to the goal, not generic
5. Example: Scaling feature identifies workspace configuration

## Timeline

- Phase 1: 1 week
- Phase 2: 1 week
- Phase 3: 1 week
- Phase 4: 1 week

**Total: 4 weeks**
