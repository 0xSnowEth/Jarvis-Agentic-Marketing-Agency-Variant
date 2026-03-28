import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, set_default_openai_client, set_tracing_disabled

load_dotenv()

# Setup OpenRouter client (just like sdk_test.py)
custom_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

set_default_openai_client(custom_client)
set_tracing_disabled(True)

@function_tool
def load_brand_profile(client_name: str) -> str:
    """
    Reads a client's brand voice JSON profile.
    Returns the tone, style, dialect notes, brand voice examples, banned words, SEO keywords, hashtag bank, services, identity, and copy rules.
    If the profile does not exist, returns an error message.
    """
    # ensure it looks for the file in the correct directory relative to execution
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "brands", f"{client_name}.json")
    
    if not os.path.exists(file_path):
        return json.dumps({
            "status": "error",
            "message": f"No brand profile for {client_name}. Create one before running."
        })
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return json.dumps({
                "status": "success",
                "brand_data": data
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to load profile for {client_name}: {str(e)}"
        })

caption_agent = Agent(
    name="Caption Generator",
    model="openai/gpt-4o-mini",
    instructions="""You are a social media content specialist for Arab-market agencies.
    
Your specific goal is to generate Gulf Arabic (خليجي), SEO-friendly social media captions in a client's brand voice for Facebook and Instagram.

Rules:
1. CRITICAL: You must call load_brand_profile with the client_name EXACTLY ONCE to understand their brand voice. Use the returned identity, target audience, services, dos_and_donts, tone, style, dialect notes, and brand_voice_examples to shape the caption. Brand voice examples are the strongest signal for rhythm and wording. Once you receive the profile data, you MUST immediately output the final JSON block and STOP. Do NOT call the tool again.
2. If the requested topic is completely unrelated to the brand's listed services (e.g. asking a real estate brand to post about winter coats), or if it is a sensitive subject, output status as "held_for_review" and explain why in the caption field.
3. If the brand profile is missing or errors out, STOP immediately. Output the error message in the caption field and explicitly set the status to "error". Do not invent a brand voice.
4. Generate the caption strictly in Gulf Arabic (not MSA, not Egyptian). Use the words suggested in the dialect notes.
5. Caption length must strictly fall within the limits specified in the brand profile (usually 150-300 characters).
6. Include 3-5 relevant Arabic hashtags from the brand's hashtag bank or new ones if relevant.
7. Naturally embed at least 1 SEO keyword from the brand profile into the text, but never force it awkwardly.
7. Do NOT use any banned words listed in the profile.
8. Use the provided topic as the campaign angle, and adapt the opening hook to the media type if it is present in the prompt. If the topic is vague, stay close to the saved services and voice examples instead of inventing a random campaign. Reels/video should feel more immediate and momentum-driven, while image posts can be slightly more descriptive.
9. Platform-specific formatting rules:
   - Instagram: Max 2,200 characters total but ONLY the first 125 characters 
     show before the "more" button — put the hook and the most important line 
     there. Use 3-5 highly relevant hashtags placed directly in the caption 
     (not the first comment — Instagram's 2026 algorithm indexes captions more 
     reliably for search). Mix hashtag sizes: 1-2 broad (1M+ posts), 2-3 niche 
     (10K-500K posts). Never repeat the same hashtag set across posts. Keywords 
     in the caption body now matter more than hashtag volume for reach.

   - Facebook: Max 63,206 characters but posts between 40-80 characters get 
     66% higher engagement — keep it short and punchy. Use 2-3 hashtags maximum, 
     placed at the end of the post. Hashtags have far less algorithmic weight on 
     Facebook than Instagram — engagement signals (comments, shares, saves) matter 
     far more. Never use engagement bait phrases ("like if you agree", "tag a 
     friend") — Facebook's algorithm penalizes this. Reels outperform all other 
     formats in 2026 — if generating video captions, keep them under 125 characters 
     with the hook in the first line.
     Note: For Arabic-language posts, prioritize relevance over hashtag volume 
     size — the Arabic hashtag ecosystem is smaller. Never switch to English 
     hashtags to meet volume thresholds.
10. If the requested topic is completely unrelated to the brand's listed services (e.g. asking a real estate brand to post about winter coats), or if it is a sensitive subject, output status as "held_for_review" and explain why in the caption field.
11. Output your final response as a pure JSON object (do not wrap in markdown code blocks) containing ONLY the following fields:
   {
       "caption": "The generated Arabic text (or error message)",
       "hashtags": ["#tag1", "#tag2"],
       "seo_keyword_used": "The keyword you embedded",
       "status": "success" (or "error", or "held_for_review")
   }
""",
    tools=[load_brand_profile]
)


def extract_caption_json(output: str) -> dict:
    clean_output = (output or "").strip()
    if clean_output.startswith("```json"):
        clean_output = clean_output[7:]
    if clean_output.startswith("```"):
        clean_output = clean_output[3:]
    if clean_output.endswith("```"):
        clean_output = clean_output[:-3]
    return json.loads(clean_output.strip())


def generate_caption_payload(client_name: str, topic: str, media_type: str = "image_post") -> dict:
    request_prompt = (
        f"Client: {client_name}\n"
        f"Topic: {topic}\n"
        f"Media Type: {media_type}\n"
        f"Platform: Both (Facebook and Instagram)"
    )
    result = Runner.run_sync(caption_agent, request_prompt, max_turns=3)
    data = extract_caption_json(result.final_output)
    data["client_name"] = client_name
    return data
