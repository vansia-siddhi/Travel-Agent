"""
Smart Travel Planner Agent — Flask Backend
=============================================
Streams the propose -> check -> revise loop live to the browser via SSE.

Currency: Indian Rupees (INR / ₹)
"""

import os
import json
import time
from flask import Flask, request, Response, send_from_directory, jsonify
from flask_cors import CORS
from groq import Groq

app = Flask(__name__, static_folder="static")
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"
MAX_REVISIONS = 3


def llm_call(prompt, json_mode=True):
    messages = [{"role": "system", "content": "You are a precise, structured assistant."},
                {"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.4}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def think_propose(destination, days, budget_inr, interests, feedback=None):
    feedback_block = ""
    if feedback:
        feedback_block = f"""
Your previous draft was REJECTED for this reason: {feedback}
Fix this specific issue in your new draft.
"""
    per_day_budget = budget_inr / days

    prompt = f"""Create a {days}-day travel itinerary for {destination}, India.

Constraints:
- Total budget: ₹{budget_inr} INR (Indian Rupees) — covers activities + food, NOT flights/hotel
- That works out to roughly ₹{per_day_budget:.0f} per day across all activities and meals
- Interests: {', '.join(interests)}
{feedback_block}

IMPORTANT — use REALISTIC current Indian Rupee prices, for example:
- A simple local meal: ₹150–400
- A restaurant meal with drinks: ₹400–1000
- Entry tickets / activities: ₹200–1500
- Adventure activities (scuba, parasailing, etc.): ₹1500–4000
- Local transport (auto/taxi) per trip: ₹100–500
Do NOT use dollar-scale numbers like ₹10, ₹15, or ₹25 for meals or activities —
those are far too low to be realistic in INR and will be rejected.

For each day, list 2-3 activities with a realistic estimated cost in INR for each.

Respond ONLY with JSON in this format:
{{
  "days": [
    {{
      "day": 1,
      "theme": "short theme for the day",
      "activities": [
        {{"name": "activity name", "cost_inr": 350, "note": "one short tip"}}
      ]
    }}
  ],
  "total_estimated_cost": 0
}}"""
    raw = llm_call(prompt)
    return json.loads(raw)


def check_validate(itinerary, days, budget_inr):
    errors = []
    if len(itinerary.get("days", [])) != days:
        errors.append(f"Itinerary has {len(itinerary.get('days', []))} days, expected {days}")

    total = sum(
        act.get("cost_inr", 0)
        for day in itinerary.get("days", [])
        for act in day.get("activities", [])
    )
    budget_limit = budget_inr * 1.10
    if total > budget_limit:
        errors.append(f"Total cost ₹{total} exceeds budget ₹{budget_inr} (even with 10% buffer)")

    for day in itinerary.get("days", []):
        if not day.get("activities"):
            errors.append(f"Day {day.get('day')} has no activities")

    # Catch unrealistically cheap pricing -- the bug the user found.
    all_activities = [
        act for day in itinerary.get("days", []) for act in day.get("activities", [])
    ]
    if all_activities:
        avg_cost = total / len(all_activities)
        if avg_cost < 80:
            errors.append(
                f"Average activity cost is ₹{avg_cost:.0f}, which is unrealistically low for India. "
                f"Use realistic INR prices (meals ₹150+, activities ₹200+)."
            )

    return {"valid": len(errors) == 0, "errors": errors, "calculated_total": total}


def sse_event(event_type, data):
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


def run_planner_stream(destination, days, budget_inr, interests):
    yield sse_event("status", {
        "message": f"Planning {days}-day trip to {destination}",
        "destination": destination, "days": days, "budget": budget_inr, "interests": interests
    })

    feedback = None
    revision_log = []
    final_itinerary = None

    for attempt in range(1, MAX_REVISIONS + 1):
        yield sse_event("step", {"phase": "think", "message": f"Drafting itinerary (attempt {attempt}/{MAX_REVISIONS})...", "attempt": attempt})

        try:
            itinerary = think_propose(destination, days, budget_inr, interests, feedback)
        except Exception as e:
            yield sse_event("error", {"message": f"Drafting failed: {str(e)}"})
            return

        yield sse_event("draft", {"attempt": attempt, "itinerary": itinerary})

        yield sse_event("step", {"phase": "check", "message": "Validating against constraints...", "attempt": attempt})
        check = check_validate(itinerary, days, budget_inr)

        revision_log.append({"attempt": attempt, "valid": check["valid"], "errors": check["errors"], "calculated_total": check["calculated_total"]})

        if check["valid"]:
            yield sse_event("validated", {"attempt": attempt, "valid": True, "calculated_total": check["calculated_total"]})
            final_itinerary = itinerary
            break
        else:
            yield sse_event("validated", {"attempt": attempt, "valid": False, "errors": check["errors"], "calculated_total": check["calculated_total"]})
            feedback = "; ".join(check["errors"])
            time.sleep(0.3)
            final_itinerary = itinerary  # keep best-effort in case all attempts fail

    yield sse_event("done", {"itinerary": final_itinerary, "revision_log": revision_log})


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/plan")
def plan():
    destination = request.args.get("destination", "Goa, India")
    days = int(request.args.get("days", 3))
    budget = float(request.args.get("budget", 15000))
    interests_raw = request.args.get("interests", "beaches, food")
    interests = [i.strip() for i in interests_raw.split(",") if i.strip()]

    return Response(run_planner_stream(destination, days, budget, interests),
                     mimetype="text/event-stream",
                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/health")
def health():
    key = os.environ.get("GROQ_API_KEY", "")
    return jsonify({"status": "ok", "api_key_set": bool(key)})


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  Smart Travel Planner Agent — Web UI")
    print("=" * 55)
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        print("  ⚠️  GROQ_API_KEY not set!")
        print("  Get a free key at https://console.groq.com")
    else:
        print(f"  ✅ API Key detected: {key[:8]}...")
    print("  🌐 Open: http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000, threaded=True)
