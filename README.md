# Smart Travel Planner Agent (Free, No Paid API)

Your third agent project — introduces the **self-critique / revise loop**,
a more advanced pattern than the previous two projects.

## What makes this different

| Research Agent | Triage Agent | Travel Planner (this one) |
|---|---|---|
| Read → summarize | Classify → route | **Propose → validate → revise** |
| Single pass | Single decision | **Iterative loop with feedback** |
| No self-checking | Rule-based routing | **Agent checks its own output and retries** |

This pattern — propose, check against rules, revise based on specific
feedback, repeat — is the same idea behind more advanced agent frameworks
(AutoGPT, LangGraph, CrewAI). The agent doesn't just trust its first answer.

## The loop

```
🧠 THINK     → draft a full itinerary for the trip
   ↓
✅ CHECK     → plain Python rules: right number of days? within budget?
              every day has activities?
   ↓
   ├── PASS → 📋 finalize and return
   └── FAIL → 🔁 send specific error back to the LLM, try again (max 3 attempts)
```

Notice the validation step uses NO LLM call — it's pure Python arithmetic
and list-checking. Only the proposing and revising steps call the AI.
This is intentional: never use an LLM for something deterministic code
can check faster and more reliably.

## Setup

1. Reuse your free Groq key from the other two projects (or get one at console.groq.com)
2. `pip install -r requirements.txt`
3. Set the key:
   - Windows PowerShell: `$env:GROQ_API_KEY="gsk_..."`
   - Mac/Linux: `export GROQ_API_KEY="gsk_..."`

## Run it

**Terminal version:**
```
python agent.py
```
Prompts you for destination, days, budget, interests. Saves to `itinerary_output.json`.

**Web version:**
```
python app.py
```
Open http://localhost:5000 — pick a destination, days, budget, and interest
chips, then watch each attempt appear live: drafted → validated → pass/fail →
(if failed) revised automatically.

## Try this to see the revision loop in action

Set an unreasonably low budget (e.g. $20 for 5 days) — you'll watch the agent
fail validation on attempt 1, receive the specific error ("total cost exceeds
budget"), and try to fix it on attempt 2. This is the easiest way to *see*
the self-correction behavior rather than just read about it.

## Files

```
travel_agent/
├── agent.py            # terminal version, standalone
├── app.py               # Flask backend with SSE streaming
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## Exercises to extend this

1. **Add a 4th rule**: e.g. "no two consecutive days can have the same theme."
2. **Increase MAX_REVISIONS** and log how often attempt 1 fails vs attempt 3 —
   gives you a feel for how reliable a single LLM call really is without checks.
3. **Make the check smarter**: instead of just budget math, ask the LLM itself
   "does this itinerary realistically fit these interests?" as an additional
   AI-based check alongside the code-based ones (mixing both check types).
4. **Chain all three agents**: Travel Planner produces an itinerary →
   Triage Agent could process "customer questions" about that itinerary →
   Research Agent could look up current info about specific stops. This is
   your first real multi-agent pipeline.
