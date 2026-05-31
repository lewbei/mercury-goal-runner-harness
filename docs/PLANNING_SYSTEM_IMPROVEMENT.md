# Planning System Improvement Plan

## Current Problem

The planning system generates generic plans, not specific ones:

```
roadmap_planner.py:
  - Uses generic templates
  - Doesn't think about the problem
  - Doesn't understand context
  - Doesn't iterate until confident
  - Creates generic artifacts, not specific plans
```

## What's Needed

1. **Think about the problem** — understand context, reason about solutions
2. **Iterate until confident** — keep planning until highest probability of success
3. **Use own knowledge** — leverage what the agent already knows
4. **Optionally search web** — supplement with web search when needed
5. **Create specific plans** — plans that address specific needs

## Proposed Solution

### 1. Iterative Planning Process

```
PLANNING PROCESS (ITERATIVE):
  1. Analyze goal
     ├── What is the user trying to do?
     ├── What similar problems exist?
     └── What solutions are known?

  2. Reason about solutions
     ├── What approaches exist?
     ├── What are the trade-offs?
     └── What's the best approach?

  3. Create plan
     ├── What steps are needed?
     ├── What are the dependencies?
     └── What are the expected outputs?

  4. Evaluate confidence
     ├── How confident are we in the plan?
     ├── What are the uncertainties?
     └── Do we need more information?

  5. If confidence is low:
     ├── Think more about the problem
     ├── Search web for more information
     ├── Refine plan
     └── Go back to step 2

  6. If confidence is high:
     ├── Finalize plan
     ├── Create specific artifacts
     └── Proceed with implementation
```

### 2. Create planning_system.py

```python
class PlanningSystem:
    def __init__(self):
        self.goal_analyzer = GoalAnalyzer()
        self.reasoning_engine = ReasoningEngine()
        self.confidence_evaluator = ConfidenceEvaluator()
        self.plan_generator = PlanGenerator()
    
    def plan(self, goal: str, max_iterations: int = 5) -> dict:
        """Plan iteratively until confident."""
        iteration = 0
        confidence = 0.0
        plan = None
        
        while iteration < max_iterations and confidence < 0.8:
            iteration += 1
            
            # 1. Analyze goal
            analysis = self.goal_analyzer.analyze(goal, plan)
            
            # 2. Reason about solutions
            reasoning = self.reasoning_engine.reason(analysis)
            
            # 3. Create plan
            plan = self.plan_generator.generate(reasoning)
            
            # 4. Evaluate confidence
            confidence = self.confidence_evaluator.evaluate(plan)
            
            # 5. Log iteration
            self.log_iteration(iteration, confidence, plan)
        
        return {
            "goal": goal,
            "iterations": iteration,
            "confidence": confidence,
            "plan": plan,
        }
```

### 3. Goal Analyzer

```python
class GoalAnalyzer:
    def analyze(self, goal: str, previous_plan: dict = None) -> dict:
        """Analyze goal to understand what's needed."""
        # Extract key concepts
        concepts = self.extract_concepts(goal)
        
        # Identify similar problems
        similar_problems = self.identify_similar_problems(concepts)
        
        # Understand context
        context = self.understand_context(goal, concepts)
        
        # Learn from previous plan if available
        if previous_plan:
            lessons = self.extract_lessons(previous_plan)
            context["lessons"] = lessons
        
        return {
            "concepts": concepts,
            "similar_problems": similar_problems,
            "context": context,
        }
```

### 4. Reasoning Engine

```python
class ReasoningEngine:
    def reason(self, analysis: dict) -> dict:
        """Reason about solutions using own knowledge."""
        # What approaches exist?
        approaches = self.identify_approaches(analysis)
        
        # What are the trade-offs?
        trade_offs = self.analyze_trade_offs(approaches)
        
        # What's the best approach?
        best_approach = self.select_best_approach(approaches, trade_offs)
        
        return {
            "approaches": approaches,
            "trade_offs": trade_offs,
            "best_approach": best_approach,
        }
```

### 5. Confidence Evaluator

```python
class ConfidenceEvaluator:
    def evaluate(self, plan: dict) -> float:
        """Evaluate confidence in the plan."""
        # How clear is the problem?
        problem_clarity = self.assess_problem_clarity(plan.analysis)
        
        # How well do we understand the solutions?
        solution_understanding = self.assess_solution_understanding(plan.reasoning)
        
        # How confident are we in the plan?
        plan_confidence = self.assess_plan_confidence(plan)
        
        # Overall confidence
        confidence = (problem_clarity + solution_understanding + plan_confidence) / 3
        
        return confidence
```

### 6. Plan Generator

```python
class PlanGenerator:
    def generate(self, reasoning: dict) -> dict:
        """Generate specific plan based on reasoning."""
        # Create steps
        steps = self.create_steps(reasoning.best_approach)
        
        # Create dependencies
        dependencies = self.create_dependencies(steps)
        
        # Create expected outputs
        expected_outputs = self.create_expected_outputs(steps)
        
        return {
            "steps": steps,
            "dependencies": dependencies,
            "expected_outputs": expected_outputs,
        }
```

## Implementation Plan

### Phase 1: Goal Analyzer (1 week)

1. Create `goal_analyzer.py`
   - Analyze goal to understand what's needed
   - Extract key concepts
   - Identify similar problems

2. Update `roadmap_planner.py`
   - Use goal analyzer to understand context
   - Generate targeted analysis

### Phase 2: Reasoning Engine (1 week)

1. Create `reasoning_engine.py`
   - Reason about solutions using own knowledge
   - Identify approaches and trade-offs
   - Select best approach

2. Update `roadmap_planner.py`
   - Use reasoning engine to think about solutions
   - Generate recommendations

### Phase 3: Confidence Evaluator (1 week)

1. Create `confidence_evaluator.py`
   - Evaluate confidence in plans
   - Identify uncertainties
   - Determine if more planning is needed

2. Update `roadmap_planner.py`
   - Use confidence evaluator to iterate
   - Keep planning until confident

### Phase 4: Plan Generator (1 week)

1. Create `plan_generator.py`
   - Generate specific plans based on reasoning
   - Create steps, dependencies, expected outputs
   - Include research findings

2. Update `roadmap_planner.py`
   - Use plan generator to create specific plans
   - Include workspace configuration, etc.

### Phase 5: Integration (1 week)

1. Update `run_goal.py`
   - Use new planning system
   - Integrate with existing pipeline

2. Update tests
   - Test new planning system
   - Verify plans are specific

## Success Criteria

1. Planning system thinks iteratively about the problem
2. Keeps planning until confidence is high (≥ 0.8)
3. Uses own knowledge before searching
4. Plans are specific to the goal, not generic
5. Example: Scaling feature identifies workspace configuration

## Timeline

- Phase 1: 1 week
- Phase 2: 1 week
- Phase 3: 1 week
- Phase 4: 1 week
- Phase 5: 1 week

**Total: 5 weeks**
