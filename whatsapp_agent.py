import os
import json
from dotenv import load_dotenv

load_dotenv()
from agents import Agent, Runner, function_tool, set_default_openai_client, set_tracing_disabled
from openai import AsyncOpenAI

# Override base URL to OpenRouter so we can utilize free models seamlessly
custom_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
set_default_openai_client(custom_client)
set_tracing_disabled(True)


@function_tool
def load_brand_profile(client_name: str) -> str:
    """
    Loads the client's CRM profile containing their voice, rules, and services.
    ALWAYS call this before generating a response to ensure tone matching.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "brands", f"{client_name}.json")
    
    if not os.path.exists(file_path):
        return json.dumps({"status": "error", "message": f"Profile for {client_name} not found."})
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        data["status"] = "success"
        return json.dumps(data, ensure_ascii=False)


whatsapp_agent = Agent(
    name="Account Manager",
    model="openai/gpt-4o-mini",
    instructions="""You are a highly professional, extremely friendly Account Manager for an Arab-market social media agency.
    
Your mandate is to reply to incoming WhatsApp messages from clients.

Rules:
1. ALWAYS call `load_brand_profile` using the strictly provided client_name to understand exactly who you are speaking to. DO NOT call it more than once.
2. Formulate your response organically in Gulf Arabic (Khaleeji). Use native dialect markers like "حياك الله", "أبشر", "طال عمرك" naturally, unless their profile strictly mandates MSA.
3. Keep the response very concise—this is a WhatsApp text, not an email. Use emojis carefully and sparingly.
4. If they ask about recent posts, reassure them that our automated Cron Scheduler engine and publishing pipeline are handling the schedule flawlessly.
5. Do NOT output markdown blocks or JSON schemas. Your final output MUST BE THE EXACT, RAW ARABIC TEXT you intend to beam directly to their phone screen.
""",
    tools=[load_brand_profile]
)

def run_whatsapp_agent(client_name: str, message_text: str) -> str:
    """
    Kicks off the autonomous response loop natively via the agents SDK.
    """
    request_prompt = (
        f"Client ID: {client_name}\n"
        f"Incoming Message: '{message_text}'\n\n"
        f"Task: Load their profile, answer them politely in Khaleeji, and output ONLY the raw response string."
    )
    
    try:
        result = Runner.run_sync(whatsapp_agent, request_prompt)
        
        # Clean up any potential hallucinated markdown blocks from the raw response
        clean_out = result.final_output.strip()
        if clean_out.startswith("```"):
            lines = clean_out.split('\n')
            clean_out = '\n'.join(lines[1:-1]) if len(lines) > 2 else clean_out
            
        return clean_out.strip()
        
    except Exception as e:
        return f"أبشر طال عمرك، نحن في طور تحديث النظام حالياً. (System Exception: {str(e)})"

# =========================================================
# THE TRIAGE AGENT (SAFETY FIREWALL)
# =========================================================
triage_agent = Agent(
    name="Escalation Router",
    model="openai/gpt-4o-mini",
    instructions="""You are a strict security firewall for an Arab-market social media agency.
Your ONLY job is to read an incoming client text message and decide if it urgently needs human intervention.

Rules:
1. Does the client genuinely sound angry, furious, complaining about bad service, or threatening to cancel? Output: ESCALATE
2. Are they explicitly saying they have a major "problem" or "issue" (مشكلة, شكوى)? Output: ESCALATE
3. Is it a normal inquiry, a joke, a casual check-in, or playfully using complaint language? Output: SAFE

You must ONLY output the exact literal word "SAFE" or "ESCALATE". Do not output punctuation. Do not explain your reasoning.
"""
)

def run_triage_agent(message_text: str) -> str:
    """
    Evaluates the message semantically. Returns 'SAFE' or 'ESCALATE'.
    """
    try:
        result = Runner.run_sync(triage_agent, f"Message to evaluate: '{message_text}'")
        return result.final_output.strip().upper()
    except Exception as e:
        # Failsafe: If the Triage AI crashes, assume SAFE so the main agent can still attempt to help
        return "SAFE"
