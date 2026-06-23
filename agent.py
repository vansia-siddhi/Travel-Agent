"""
Smart Travel Planner Agent
============================
Demonstrates the SELF-CRITIQUE / REVISE loop -- a more advanced agent
pattern than simple read->summarize or classify->route.

Given a destination + constraints (days, budget, interests), this agent:

  1. THINK    -> research the destination, propose a draft itinerary
  2. CHECK    -> validate the draft against constraints (budget, day count)
  3. DECIDE   -> if it fails validation, go back and revise; if it passes, finalize
  4. ACT      -> output the final, validated itinerary

This "propose -> check -> revise" loop is the same pattern used in more
advanced agent frameworks (AutoGPT, LangGraph, CrewAI) where an agent
checks its own work instead of trusting the first answer.

Currency: Indian Rupees (INR / ₹)
Uses Groq's free API (same as the other agent projects).
"""

import os
import json
import time
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
MODEL = "llama-3.3-70b-versatile"
MAX_REVISIONS = 3


def llm_call(prompt, system="You are a precise, structured assistant.", json_mode=True):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.4}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


class TravelPlannerAgent:
    """
    Demonstrates: THINK (propose) -> CHECK (validate) -> DECIDE (revise or finalize)
    """

    def __init__(self, destination, days, budget_inr, interests):
        self.destination = destination
        self.days = days
        self.budget_inr = budget_inr
        self.interests = interests
        self.revision_log = []   # memory of every attempt + why it was rejected

    def think_propose(self, feedback=None):
        """Step 1 - THINK: propose a draft itinerary.
        On revision attempts, includes feedback from the previous check."""
        feedback_block = ""
        if feedback:
            feedback_block = f"""
Your previous draft was REJECTED for this reason: {feedback}
Fix this specific issue in your new draft.
"""

        # Per-day budget guidance helps the model anchor to a realistic scale
        # instead of guessing -- this is the actual fix for unrealistic pricing.
        per_day_budget = self.budget_inr / self.days

        prompt = f"""Create a {self.days}-day travel itinerary for {self.destination}, India.

Constraints:
- Total budget: ₹{self.budget_inr} INR (Indian Rupees) — covers activities + food, NOT flights/hotel
- That works out to roughly ₹{per_day_budget:.0f} per day across all activities and meals
- Interests: {', '.join(self.interests)}
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

    def check_validate(self, itinerary):
        """Step 2 - CHECK: validate the draft against hard constraints.
        This is plain Python logic, not another LLM call -- the agent
        checking its own work with deterministic rules."""
        errors = []

        # Rule 1: correct number of days
        if len(itinerary.get("days", [])) != self.days:
            errors.append(f"Itinerary has {len(itinerary.get('days', []))} days, expected {self.days}")

        # Rule 2: budget check (allow 10% buffer for estimation error)
        total = sum(
            act.get("cost_inr", 0)
            for day in itinerary.get("days", [])
            for act in day.get("activities", [])
        )
        budget_limit = self.budget_inr * 1.10
        if total > budget_limit:
            errors.append(f"Total cost ₹{total} exceeds budget ₹{self.budget_inr} (even with 10% buffer)")

        # Rule 3: every day must have at least 1 activity
        for day in itinerary.get("days", []):
            if not day.get("activities"):
                errors.append(f"Day {day.get('day')} has no activities")

        # Rule 4: catch unrealistically cheap pricing (the bug you found!)
        # If average cost per activity is below a sane floor, the LLM is
        # likely reusing dollar-scale numbers instead of real INR prices.
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

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "calculated_total": total
        }

    def run(self):
        """Main loop: THINK -> CHECK -> (revise and repeat) OR finalize."""
        print(f"\n{'='*70}")
        print(f"🧳 TRAVEL PLANNER AGENT")
        print(f"   Destination: {self.destination} | {self.days} days | Budget: ₹{self.budget_inr}")
        print(f"   Interests: {', '.join(self.interests)}")
        print(f"{'='*70}\n")

        feedback = None
        for attempt in range(1, MAX_REVISIONS + 1):
            print(f"🧠 THINK: Drafting itinerary (attempt {attempt}/{MAX_REVISIONS})...")
            itinerary = self.think_propose(feedback)

            print(f"✅ CHECK: Validating against constraints...")
            check = self.check_validate(itinerary)

            self.revision_log.append({
                "attempt": attempt,
                "valid": check["valid"],
                "errors": check["errors"],
                "calculated_total": check["calculated_total"]
            })

            if check["valid"]:
                print(f"   ✓ PASSED — total cost ₹{check['calculated_total']} within budget\n")
                self._print_itinerary(itinerary)
                return itinerary
            else:
                print(f"   ✗ FAILED: {'; '.join(check['errors'])}")
                feedback = "; ".join(check["errors"])
                print(f"   🔁 Revising...\n")
                time.sleep(0.5)

        print(f"\n⚠️  Could not produce a valid itinerary within {MAX_REVISIONS} attempts.")
        print("   Returning best attempt anyway (may not meet all constraints).\n")
        self._print_itinerary(itinerary)
        return itinerary

    def _print_itinerary(self, itinerary):
        print(f"{'='*70}\n📋 FINAL ITINERARY\n{'='*70}")
        for day in itinerary.get("days", []):
            print(f"\n📅 Day {day['day']}: {day.get('theme', '')}")
            for act in day.get("activities", []):
                print(f"   • {act['name']} — ₹{act['cost_inr']}  ({act.get('note', '')})")
        print(f"\n💰 Total estimated cost: ₹{itinerary.get('total_estimated_cost', 'N/A')}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("⚠️  Set your free Groq API key first:")
        print('    $env:GROQ_API_KEY="your_key_here"   (Windows PowerShell)')
        print("    export GROQ_API_KEY=your_key_here    (Mac/Linux)")
        print("\nGet a free key at: https://console.groq.com")
        exit(1)

    destination = input("Destination (e.g. Goa, India): ").strip() or "Goa, India"
    days = int(input("Number of days (e.g. 3): ").strip() or "3")
    budget = float(input("Total budget in INR ₹ (e.g. 15000): ").strip() or "15000")
    interests_raw = input("Interests, comma-separated (e.g. beaches, food, nightlife): ").strip() or "beaches, food"
    interests = [i.strip() for i in interests_raw.split(",")]

    agent = TravelPlannerAgent(destination, days, budget, interests)
    final = agent.run()

    with open("itinerary_output.json", "w", encoding="utf-8") as f:
        json.dump({"itinerary": final, "revision_log": agent.revision_log}, f, indent=2)
    print("💾 Saved to itinerary_output.json")
