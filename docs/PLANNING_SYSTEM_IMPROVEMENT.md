# Planning System Improvement Plan

## Research Findings (Google Antigravity 93 Agents)

### How the 93 agents actually worked

From Google's official blog:

```
1. SINGLE PROMPT
   - The OS was built from a single prompt
   - No manual intervention during execution

2. SPECIALIZED ROLES (7 types)
   - The Sentinel — front-desk manager (doesn't write code)
   - The Orchestrator — dispatch-only manager (doesn't write code)
   - The Explorer — analyzes requirements (doesn't write code)
   - The Worker — the actual coder
   - The Reviewer — reviews changes
   - The Critic — stress-tests
   - The Auditor — verifies authenticity

3. KEY TECHNIQUES
   - Self-succession: handles context length limits
   - Crons: handles stuck/blocked processes
   - Auditor: combats LLM laziness (cheating)

4. SINGLE WORKSPACE
   - All agents work on the same project
   - No isolated workspaces
   - Agents coordinate through the platform

5. PARALLEL EXECUTION
   - 93 agents running simultaneously
   - Each agent has specific role
   - Agents work on different parts
```

### Key Insights

1. **Single workspace, not multiple isolated workspaces**
   - All agents work on the same project
   - No need for workspace isolation
   - Agents coordinate through the platform

2. **Specialized roles, not generic agents**
   - Each agent has a specific role
   - Roles are complementary
   - Roles don't overlap

3. **Parallel execution with coordination**
   - Agents work in parallel
   - Agents coordinate through the platform
   - No conflicts between agents

4. **Self-healing mechanisms**
   - Self-succession for context length
   - Crons for stuck processes
   - Auditor for LLM laziness

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

## Proposed Solution

### 1. Multi-Agent Planning with Specialized Roles

```
PLANNING AGENTS:
  - Sentinel: manages the planning process
  - Orchestrator: coordinates planning tasks
  - Explorer: researches solutions
  - Worker: creates plan artifacts
  - Reviewer: reviews plan quality
  - Critic: stress-tests the plan
  - Auditor: verifies plan authenticity
```

### 2. Iterative Planning Process

```
PLANNING PROCESS (ITERATIVE):
  1. Sentinel receives goal
     └── Spawns Orchestrator

  2. Orchestrator decomposes goal
     ├── Spawns Explorer to research
     ├── Spawns Worker to create plan
     ├── Spawns Reviewer to review
     ├── Spawns Critic to stress-test
     └── Spawns Auditor to verify

  3. Each agent works in parallel
     ├── Explorer researches solutions
     ├── Worker creates plan artifacts
     ├── Reviewer reviews quality
     ├── Critic stress-tests
     └── Auditor verifies

  4. Orchestrator synthesizes results
     ├── Combines findings
     ├── Evaluates confidence
     └── If confidence is low → iterate
     └── If confidence is high → finalize

  5. Sentinel reports to user
     └── Final plan ready
```

### 3. Specialized Planning Agents

```python
class PlanningSentinel:
    """Manages the planning process."""
    def plan(self, goal: str) -> dict:
        # Spawn Orchestrator
        orchestrator = PlanningOrchestrator()
        return orchestrator.orchestrate(goal)

class PlanningOrchestrator:
    """Coordinates planning tasks."""
    def orchestrate(self, goal: str) -> dict:
        # Spawn specialized agents
        explorer = PlanningExplorer()
        worker = PlanningWorker()
        reviewer = PlanningReviewer()
        critic = PlanningCritic()
        auditor = PlanningAuditor()
        
        # Run agents in parallel
        research = explorer.research(goal)
        plan = worker.create_plan(goal, research)
        review = reviewer.review(plan)
        critique = critic.stress_test(plan)
        verification = auditor.verify(plan)
        
        # Synthesize results
        return self.synthesize(plan, review, critique, verification)

class PlanningExplorer:
    """Researches solutions."""
    def research(self, goal: str) -> dict:
        # Analyze goal
        analysis = self.analyze_goal(goal)
        
        # Research solutions
        solutions = self.research_solutions(analysis)
        
        # Return findings
        return {
            "analysis": analysis,
            "solutions": solutions,
        }

class PlanningWorker:
    """Creates plan artifacts."""
    def create_plan(self, goal: str, research: dict) -> dict:
        # Create plan based on research
        plan = {
            "goal": goal,
            "steps": self.create_steps(research),
            "dependencies": self.create_dependencies(research),
            "expected_outputs": self.create_expected_outputs(research),
        }
        return plan

class PlanningReviewer:
    """Reviews plan quality."""
    def review(self, plan: dict) -> dict:
        # Review plan for quality
        return {
            "quality_score": self.assess_quality(plan),
            "issues": self.find_issues(plan),
            "suggestions": self.suggest_improvements(plan),
        }

class PlanningCritic:
    """Stress-tests the plan."""
    def stress_test(self, plan: dict) -> dict:
        # Stress-test the plan
        return {
            "robustness_score": self.assess_robustness(plan),
            "failure_modes": self.identify_failure_modes(plan),
            "mitigations": self.suggest_mitigations(plan),
        }

class PlanningAuditor:
    """Verifies plan authenticity."""
    def verify(self, plan: dict) -> dict:
        # Verify plan authenticity
        return {
            "authenticity_score": self.assess_authenticity(plan),
            "cheating_signals": self.detect_cheating(plan),
            "verification": self.verify_plan(plan),
        }
```

### 4. Self-Healing Mechanisms

```python
class SelfHealingPlanner:
    """Handles planning failures."""
    
    def handle_context_length(self, planner, goal):
        """Handle context length limits."""
        # Dump state to handoff files
        state = planner.dump_state()
        
        # Spawn successor
        successor = PlanningOrchestrator()
        return successor.resume(state, goal)
    
    def handle_stuck_process(self, planner, timeout):
        """Handle stuck processes."""
        # Check progress files
        if planner.is_stale(timeout):
            # Terminate and respawn
            planner.terminate()
            return self.respawn(planner)
    
    def handle_llm_laziness(self, plan):
        """Handle LLM laziness (cheating)."""
        # Run auditor
        auditor = PlanningAuditor()
        verification = auditor.verify(plan)
        
        if verification["cheating_signals"]:
            # Force re-planning
            return self.replan(plan)
```

### 5. Parallel Execution with Coordination

```python
class ParallelPlanningExecutor:
    """Executes planning agents in parallel."""
    
    def execute(self, agents: list, goal: str) -> dict:
        """Execute agents in parallel."""
        # Create tasks
        tasks = [agent.plan(goal) for agent in agents]
        
        # Run in parallel
        results = self.run_parallel(tasks)
        
        # Coordinate results
        return self.coordinate(results)
    
    def run_parallel(self, tasks: list) -> list:
        """Run tasks in parallel."""
        # Use thread pool or async
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda t: t(), tasks))
        return results
    
    def coordinate(self, results: list) -> dict:
        """Coordinate results from parallel agents."""
        # Combine results
        combined = {
            "research": results[0],
            "plan": results[1],
            "review": results[2],
            "critique": results[3],
            "verification": results[4],
        }
        
        # Evaluate confidence
        confidence = self.evaluate_confidence(combined)
        
        return {
            "combined": combined,
            "confidence": confidence,
        }
```

## Implementation Plan

### Phase 1: Planning Agents (1 week)

1. Create `planning_sentinel.py`
   - Manages the planning process
   - Spawns Orchestrator

2. Create `planning_orchestrator.py`
   - Coordinates planning tasks
   - Spawns specialized agents

3. Create `planning_explorer.py`
   - Researches solutions
   - Analyzes goal

### Phase 2: Specialized Agents (1 week)

1. Create `planning_worker.py`
   - Creates plan artifacts
   - Uses research findings

2. Create `planning_reviewer.py`
   - Reviews plan quality
   - Finds issues

3. Create `planning_critic.py`
   - Stress-tests the plan
   - Identifies failure modes

4. Create `planning_auditor.py`
   - Verifies plan authenticity
   - Detects cheating

### Phase 3: Self-Healing (1 week)

1. Create `self_healing_planner.py`
   - Handles context length limits
   - Handles stuck processes
   - Handles LLM laziness

2. Update `planning_orchestrator.py`
   - Use self-healing mechanisms
   - Handle failures gracefully

### Phase 4: Parallel Execution (1 week)

1. Create `parallel_planning_executor.py`
   - Executes agents in parallel
   - Coordinates results

2. Update `planning_orchestrator.py`
   - Use parallel execution
   - Coordinate results

### Phase 5: Integration (1 week)

1. Update `run_goal.py`
   - Use new planning system
   - Integrate with existing pipeline

2. Update tests
   - Test new planning system
   - Verify plans are specific

## Success Criteria

1. Planning system uses specialized agents
2. Agents work in parallel
3. Agents coordinate through the platform
4. Self-healing mechanisms handle failures
5. Plans are specific to the goal, not generic
6. Example: Scaling feature identifies workspace configuration

## Timeline

- Phase 1: 1 week
- Phase 2: 1 week
- Phase 3: 1 week
- Phase 4: 1 week
- Phase 5: 1 week

**Total: 5 weeks**
