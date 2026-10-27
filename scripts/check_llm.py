"""
Checks the language-model connection used by Synapse and prints the real error if it fails.

  $env:GROQ_API_KEY="..."     (or ANTHROPIC_API_KEY), in the same terminal
  python scripts/check_llm.py
"""
import _path  # noqa: F401
from traffix.synapse import llm

TOOLS = [{"name": "get_number", "description": "Returns a number.",
          "input_schema": {"type": "object", "properties": {}}}]

if __name__ == "__main__":
    if not llm.available():
        print("No key found. Set GROQ_API_KEY or ANTHROPIC_API_KEY in THIS terminal, then run again.")
        raise SystemExit(1)
    print("Provider:", llm.provider(), "| models:", {r: llm.model_for(r) for r in ("explainer", "copilot", "alert")})
    missing = False
    for role in ("explainer", "alert"):
        try:
            text, _ = llm.chat(role, "Reply with the single word OK.", "Say OK", max_tokens=10)
            print(f"  {role:9s} plain answer: OK ->", repr(text))
        except Exception as e:
            print(f"  {role:9s} FAILED: {e}")
            missing = missing or "model_not_found" in str(e) or "does not exist" in str(e)
    try:
        text, calls = llm.chat("explainer", "Call the tool get_number, then reply with the number it returned.",
                               "What number?", tools=TOOLS, handlers={"get_number": lambda: {"number": 42}},
                               max_tokens=50)
        print(f"  tool use  : {len(calls)} tool call(s), answer {text!r}",
              "-> OK" if calls and "42" in text else "-> the model did not use the tool")
    except Exception as e:
        print("  tool use  FAILED:", e)

    if missing:
        try:
            print("\nModels your key can use:", ", ".join(llm.list_models()))
            print("Put one in config/agents.yaml > synapse (groq_explainer_model, groq_copilot_model, groq_alert_model).")
        except Exception as e:
            print("Could not list models:", e)
