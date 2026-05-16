# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 run (session sess_a382a2149fc1), the planner's second
subgoal was sg_2 "commit the booking under policy rules" with
assigned_half: "structured". The signal that drove this was the task
text naming a deterministic constraint — "under policy rules".
Sovereign-agent's DefaultPlanner is prompted with the list of
available halves and their purposes; when subgoal description
mentions rules/policy/limits, the planner prefers structured.

This decision is advisory, not physical. The orchestrator respects
it only because both halves are wired up. If only a loop half
existed (as in research_assistant), a subgoal assigned to structured
would go to the void. That's failure mode #4 from the course slides.

The broader lesson: the planner makes an architectural decision
based on prose interpretation. Put the rules somewhere the LLM
cannot mis-assign — in the structured half's Python — and prose
ambiguity no longer matters.

### Citation

- sessions/sess_a382a2149fc1/logs/tickets/tk_*/raw_output.json
- sessions/sess_a382a2149fc1/logs/trace.jsonl:23

---

## Q2 — Dataflow integrity catch

### Your answer

In sess_0a4a1aad52f0, Qwen made 8 venue_search tool calls for different party sizes. The input party size was 6 but surprisingly the LLM model did not consider that size at all. The party size that it considered was from 8 - 20. The party size of 8 could have easily been missed by a human as it is close to the actual size.

---

## Q3 — Removing one framework primitive

### Your answer

I'd keep session directories (Decision 1) as the last thing standing
and rebuild everything else if forced. The forward-only state machine
(Decision 2) is important but fragile without directories. Tickets
(Decision 3) I could rebuild as .jsonl files inside the session.
Atomic-rename IPC (Decision 5) is replaceable by directory polling.

Session directories are the irreplaceable piece. Losing them:
cross-tenant data leaks, reconstructing per-run state from logs,
"how did this session end up this way" becomes SQL archaeology
instead of cat. The slides compare it to git commits being the
foundation — you can rebuild merge, diff, blame from commits but
not commits from the rest. Session directories are commits.

### Citation

- sessions/sess_de44a1b8eb12/ — the directory itself
- sessions/sess_a382a2149fc1/logs/trace.jsonl
