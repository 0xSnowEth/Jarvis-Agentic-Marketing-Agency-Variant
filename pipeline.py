import argparse
import sys
import json
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
import logging
from caption_agent import generate_caption_payload
from publish_agent import publish_agent
from draft_store import delete_draft_payload, get_draft_payload
from publish_run_store import record_publish_run
from schedule_store import mark_job_delivered, mark_job_failed

load_dotenv()


def get_agency_runtime_config() -> dict:
    config = {}
    if os.path.exists("agency_config.json"):
        try:
            with open("agency_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {}
    return {
        "owner_phone": str(config.get("owner_phone") or os.getenv("OWNER_PHONE", "")).strip(),
        "whatsapp_access_token": str(config.get("whatsapp_access_token") or os.getenv("WHATSAPP_TOKEN", "")).strip(),
        "whatsapp_phone_id": str(config.get("whatsapp_phone_id") or os.getenv("WHATSAPP_TEST_PHONE_NUMBER_ID", "")).strip(),
    }


def send_owner_briefing(client_name, caption, platforms, publish_results=None, image_count=0, video_count=0):
    config = get_agency_runtime_config()
    owner_phone = config["owner_phone"]
    whatsapp_token = config["whatsapp_access_token"]
    whatsapp_phone_id = config["whatsapp_phone_id"]

    if not whatsapp_token or not whatsapp_phone_id or not owner_phone:
        logger.warning("WhatsApp briefing skipped: missing WhatsApp token, phone ID, or owner phone.")
        return

    url = f"https://graph.facebook.com/v22.0/{whatsapp_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json"
    }
    preview = caption[:120] + "..." if len(caption) > 120 else caption
    platform_str = ", ".join(platforms)
    media_type = "Single Video" if video_count else ("Carousel" if image_count > 1 else "Single Image" if image_count == 1 else "Text Only")

    post_ids = ""
    if publish_results:
        pr = publish_results.get("platform_results", {})
        fb_id = pr.get("facebook", {}).get("post_id")
        ig_id = pr.get("instagram", {}).get("media_id")
        if fb_id:
            post_ids += f"\nFB: fb.com/{fb_id}"
        if ig_id:
            post_ids += f"\nIG: {ig_id}"

    timestamp = datetime.now().strftime("%I:%M %p")

    text = (
        f"Post Published Successfully 🟢\n\n"
        f"Client: {client_name.replace('_', ' ').title()}\n"
        f"Platforms: {platform_str}\n"
        f"Format: {media_type}\n"
        f"Time: {timestamp}\n\n"
        f"Caption Preview:\n{preview}"
        f"{post_ids}"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": owner_phone,
        "type": "text",
        "text": {"body": text}
    }
    try:
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.warning(f"WhatsApp briefing API returned {resp.status_code}: {resp.text[:200]}")
        else:
            logger.info(f"WhatsApp briefing sent to {owner_phone}")
    except Exception as e:
        logger.warning(f"WhatsApp briefing failed: {e}")

# Silence the Agents SDK logger if needed, keep our local pipeline log clean
# Silence the Agents SDK logger if needed, keep our local pipeline log clean
# Silence the Agents SDK logger if needed, keep our local pipeline log clean
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Pipeline")

def load_draft_caption(client_name: str, draft_name: str | None) -> dict | None:
    if not draft_name:
        return None
    payload = get_draft_payload(client_name, draft_name)
    if not payload:
        return None

    caption_text = str(payload.get("caption_text") or "").strip()
    if not caption_text:
        return None

    hashtags = payload.get("hashtags", [])
    if not isinstance(hashtags, list):
        hashtags = []

    return {
        "status": "success",
        "caption": caption_text,
        "hashtags": [str(tag).strip() for tag in hashtags if str(tag).strip()],
        "seo_keyword_used": str(payload.get("seo_keyword_used") or "").strip(),
        "client_name": client_name,
        "caption_mode": str(payload.get("caption_mode") or "ai").strip().lower(),
        "caption_status": str(payload.get("caption_status") or "ready").strip().lower(),
    }


def derive_failure_step(publish_results: dict) -> str | None:
    platform_results = publish_results.get("platform_results", {}) or {}
    for _, platform_data in platform_results.items():
        step = str(platform_data.get("step") or "").strip()
        if step:
            return step
    return None


def persist_publish_run(
    client_name: str,
    topic: str,
    draft_name: str | None,
    job_id: str | None,
    publish_results: dict,
) -> None:
    draft_payload = get_draft_payload(client_name, draft_name) if draft_name else None
    raw_output = {
        "topic": topic,
        "status": publish_results.get("status"),
        "message": publish_results.get("message"),
        "platform_results": publish_results.get("platform_results", {}),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        record_publish_run(
            {
                "client_id": client_name,
                "job_id": job_id or None,
                "draft_id": str((draft_payload or {}).get("draft_id") or "").strip() or None,
                "topic": topic,
                "status": str(publish_results.get("status") or "unknown").strip().lower(),
                "failure_step": derive_failure_step(publish_results),
                "platform_results": publish_results.get("platform_results", {}) or {},
                "raw_output": json.dumps(raw_output, ensure_ascii=False),
            }
        )
        logger.info("Publish run persisted to active backend.")
    except Exception as exc:
        logger.warning(f"Failed to persist publish run: {exc}")

def main():
    parser = argparse.ArgumentParser(description="Social Media Automation Pipeline (Agent 1 + Agent 2)")
    parser.add_argument("--client", required=True, help="Client brand identifier (e.g., client_a)")
    parser.add_argument("--topic", required=True, help="The prompt/topic for the post")
    parser.add_argument("--image", required=False, action="append", help="Target image path from the isolated vault (pass multiple times for carousel)")
    parser.add_argument("--video", required=False, action="append", help="Target video path from the isolated vault (single video currently supported)")
    parser.add_argument("--job-id", required=False, help="Stable schedule job identifier for delivery marking")
    parser.add_argument("--draft-name", required=False, help="Creative draft name used to load stored caption content")
    args = parser.parse_args()

    # 1. GENERATION PHASE (Agent #1)
    logger.info(f"Starting Pipeline for client '{args.client}'...")
    logger.info(f"Topic: {args.topic}")
    if args.job_id:
        logger.info(f"Job ID: {args.job_id}")
    if args.image:
        logger.info(f"Images attached: {len(args.image)} items: {args.image}")
    if args.video:
        logger.info(f"Videos attached: {len(args.video)} items: {args.video}")

    media_type = "single_video" if args.video else ("image_carousel" if args.image and len(args.image) > 1 else "image_post")
    agent1_data = load_draft_caption(args.client, args.draft_name)

    if agent1_data:
        logger.info(f"Using stored {agent1_data.get('caption_mode', 'manual')} caption from draft '{args.draft_name}'.")
    else:
        logger.info("Handing off to Agent #1 (Caption Generator)...")
        try:
            agent1_data = generate_caption_payload(args.client, args.topic, media_type=media_type)
        except Exception as e:
            logger.error(f"Failed to generate caption payload: {e}")
            sys.exit(1)

    # Inject client name and asset trace for Agent #2 context
    agent1_data["client_name"] = args.client
    if args.image:
        agent1_data["images"] = args.image  # List of paths for carousel support
    if args.video:
        agent1_data["videos"] = args.video

    # 2. SAFETY GATE
    status = agent1_data.get("status")
    if status != "success":
        logger.warning(f"🛑 Pipeline Halted by Agent #1 Safety Gate. Status: {status}")
        logger.info(f"Reason/Caption Output: {agent1_data.get('caption')}")
        sys.exit(1)
        
    logger.info("✅ Agent #1 successfully generated content.")
    logger.info(f"Caption Length: {len(agent1_data.get('caption', ''))} chars")
    logger.info(f"Hashtags: {', '.join(agent1_data.get('hashtags', []))}")

    # 3. PUBLISHING PHASE (Agent #2)
    logger.info("🚀 Handing off to Agent #2 (Meta Publisher)...")
    publish_results = publish_agent.publish(agent1_data)
    persist_publish_run(args.client, args.topic, args.draft_name, args.job_id, publish_results)
    
    # 4. FINAL REPORT
    print("\n" + "="*60)
    print("📊 PIPELINE FINAL REPORT")
    print("="*60)
    print(f"Client:       {args.client}")
    print(f"Topic:        {args.topic}")
    print(f"SEO Keyword:  {agent1_data.get('seo_keyword_used')}")
    print("-" * 60)
    print("📋 GENERATED TEXT:")
    print(f"{agent1_data.get('caption')}")
    print("-" * 60)
    print("🏷️  LOGGED HASHTAGS (From JSON, not appended):")
    print(f"{', '.join(agent1_data.get('hashtags', []))}")
    print("-" * 60)
    print("📈 PUBLISHING RESULTS:")
    
    platforms = publish_results.get("platform_results", {})
    
    if platforms:
        fb = platforms.get("facebook", {})
        ig = platforms.get("instagram", {})
        
        print(f"Facebook:  {fb.get('status', 'Skipped')} " + (f"(ID: {fb.get('post_id')})" if fb.get('post_id') else ""))
        if fb.get("status") == "error":
            print(f"           Error: {fb.get('error_message')}")
            
        print(f"Instagram: {ig.get('status', 'Skipped')} " + (f"(ID: {ig.get('media_id')})" if ig.get('media_id') else ""))
        if ig.get("status") == "error":
            print(f"           Error: {ig.get('error_message')}")
            if ig.get("step"):
                print(f"           Step: {ig.get('step')}")

    print(f"PIPELINE_STATUS: {publish_results.get('status', 'unknown')}")
    if publish_results.get("message"):
        print(f"PIPELINE_MESSAGE: {publish_results.get('message')}")
    
    if publish_results.get("status") == "error":
        if args.job_id:
            try:
                matched, _ = mark_job_failed(args.job_id, reason=str(publish_results.get("message") or "Publishing failed.").strip()[:500])
                if matched:
                    logger.info(f"Marked job '{args.job_id}' as failed after publish error.")
                else:
                    logger.warning(f"Job '{args.job_id}' not found when trying to mark as failed.")
            except Exception as e:
                logger.warning(f"Failed to flag publish failure for job '{args.job_id}': {e}")
        print(f"\n=> Global Note: {publish_results.get('message', 'Failure encountered.')}")
        print("="*60 + "\n")
        sys.exit(1)
        
    # Phase 6: Executive Briefing
    platforms = []
    for platform, data in publish_results.get("platform_results", {}).items():
        if data.get("status") == "published":
            platforms.append(platform.capitalize())
            
    if platforms:
        image_count = len(args.image) if args.image else 0
        video_count = len(args.video) if args.video else 0
        send_owner_briefing(args.client, agent1_data.get('caption', ''), platforms, 
                           publish_results=publish_results, image_count=image_count, video_count=video_count)

        if not args.job_id and args.draft_name and publish_results.get("status") == "success":
            try:
                if delete_draft_payload(args.client, args.draft_name):
                    logger.info(f"Cleared published draft '{args.draft_name}' from the creative queue.")
            except Exception as exc:
                logger.warning(f"Failed to clear published draft '{args.draft_name}': {exc}")
        
        if args.job_id:
            try:
                matched, _ = mark_job_delivered(args.job_id)
                if matched:
                    logger.info(f"✅ Marked job '{args.job_id}' as delivered in the schedule.")
                else:
                    logger.warning(f"Job '{args.job_id}' was not found when marking as delivered.")
            except Exception as e:
                logger.warning(f"Failed to flag delivery status for job '{args.job_id}': {e}")
        else:
            logger.info("Skipping schedule delivery mark because no job_id was provided.")

    print("="*60 + "\n")

if __name__ == "__main__":
    main()
