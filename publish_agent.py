import os
import time
import requests
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MetaPublisher")

class PublishAgent:
    """
    Agent #2: The Python Execution Layer for Meta Graph API.
    """
    
    def __init__(self, api_version: str = "v19.0"):
        self.api_version = api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.ig_poll_attempts_image = 6
        self.ig_poll_attempts_video = 24
        self.ig_poll_interval_image = 3
        self.ig_poll_interval_video = 5

    def publish(self, agent1_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution method for publishing.
        """
        # 1. Validation 
        if agent1_output.get("status") != "success":
            logger.warning(f"Agent #1 did not return success. Status: {agent1_output.get('status')}. Aborting publish.")
            return {
                "status": "error",
                "message": "Caption generation failed or was held for review.",
                "agent1_status": agent1_output.get("status")
            }

        client_name = agent1_output.get("client_name", "unknown_client")
        
        # 2. Extract configuration (Prefer vault isolation, fallback to .env for testing)
        fb_page_id = os.getenv("META_PAGE_ID")
        ig_user_id = os.getenv("META_IG_USER_ID")
        access_token = os.getenv("META_ACCESS_TOKEN")
        
        client_vault = f"clients/{client_name}.json"
        if os.path.exists(client_vault):
            try:
                import json
                with open(client_vault, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                access_token = cdata.get("meta_access_token", access_token)
                fb_page_id = cdata.get("facebook_page_id", fb_page_id)
                ig_user_id = cdata.get("instagram_account_id", ig_user_id)
            except Exception as e:
                logger.error(f"Vault decryption failed for {client_name}: {e}")

        # 3. Handle media URL Asset Mapping
        images = agent1_output.get("images", [])
        videos = agent1_output.get("videos", [])
        if "image_path" in agent1_output and agent1_output["image_path"] and not images:
            val = agent1_output["image_path"]
            images = val if isinstance(val, list) else [val]
            
        tunnel = os.getenv("WEBHOOK_PROXY_URL", "http://localhost:8000").rstrip('/')
        
        import urllib.parse
        image_urls = []
        for img in images:
            encoded = urllib.parse.quote(img, safe='/')
            image_urls.append(f"{tunnel}/{encoded}")
        video_urls = []
        for video in videos:
            encoded = urllib.parse.quote(video, safe='/')
            video_urls.append(f"{tunnel}/{encoded}")

        logger.info(f"Resolved media URLs for publish: images={image_urls}, videos={video_urls}")

        if image_urls and video_urls:
            return {"status": "error", "message": "Mixed image and video publishing is not supported yet."}
        if len(video_urls) > 1:
            return {"status": "error", "message": "Only a single video is supported per post in this version."}
        if not image_urls and not video_urls:
            return {"status": "error", "message": "No media assets were provided for publish."}

        if not access_token:
            logger.error("Missing META_ACCESS_TOKEN.")
            return {"status": "error", "message": "Missing META_ACCESS_TOKEN in environment."}

        # 4. Format Content
        # Agent #1's prompt explicitly instructs it to naturally place hashtags within the caption itself.
        # We should NOT blindly append the structured 'hashtags' array again, or we get duplicates.
        caption = agent1_output.get("caption", "")
        
        fb_message = caption
        ig_caption = caption

        # 5. Execute API Calls
        # Extract client_name if available from context, otherwise use default
        client_name = agent1_output.get("client_name", "unknown_client")
        results = {
            "status": "success",
            "client_name": client_name,
            "platform_results": {}
        }
        
        # Publish to Facebook
        if fb_page_id:
            media_count = len(video_urls) if video_urls else len(image_urls)
            logger.info(f"Publishing to Facebook Page: {fb_page_id} ({media_count} items)")
            fb_res = self._publish_to_facebook(fb_page_id, access_token, fb_message, image_urls, video_urls)
            results["platform_results"]["facebook"] = fb_res
        else:
            logger.warning("No META_PAGE_ID defined. Skipping Facebook.")

        # Publish to Instagram
        if ig_user_id:
            media_count = len(video_urls) if video_urls else len(image_urls)
            logger.info(f"Publishing to Instagram Account: {ig_user_id} ({media_count} items)")
            ig_res = self._publish_to_instagram(ig_user_id, access_token, ig_caption, image_urls, video_urls)
            results["platform_results"]["instagram"] = ig_res
        else:
            logger.warning("No META_IG_USER_ID defined. Skipping Instagram.")

        # Post-analysis of results
        # If both platforms attempted and both failed, explicitly note it
        if results["platform_results"] and all(res.get("status") == "error" for res in results["platform_results"].values()):
            results["status"] = "error"
            results["message"] = "Publishing failed on all configured platforms."

        return results

    def _publish_to_facebook(self, page_id: str, token: str, message: str, image_urls: list, video_urls: list) -> dict:
        try:
            if video_urls:
                url = f"{self.base_url}/{page_id}/videos"
                payload = {"file_url": video_urls[0], "description": message, "access_token": token}
                response = requests.post(url, data=payload).json()
                if "error" in response:
                    return {"status": "error", "error_message": response["error"]["message"], "step": "upload_video"}
                return {"status": "published", "post_id": response.get("id")}

            if len(image_urls) == 1:
                url = f"{self.base_url}/{page_id}/photos"
                payload = {"url": image_urls[0], "message": message, "access_token": token}
                response = requests.post(url, data=payload).json()
                if "error" in response: return {"status": "error", "error_message": response["error"]["message"]}
                return {"status": "published", "post_id": response.get("id")}
            else:
                # Multi-photo FB post
                attached_media = []
                for murl in image_urls:
                    res = requests.post(f"{self.base_url}/{page_id}/photos", data={"url": murl, "published": "false", "access_token": token}).json()
                    if "id" in res: attached_media.append({"media_fbid": res["id"]})
                
                payload = {"message": message, "access_token": token}
                for i, m in enumerate(attached_media):
                    payload[f"attached_media[{i}]"] = str(m).replace("'", '"')
                    
                final_res = requests.post(f"{self.base_url}/{page_id}/feed", data=payload).json()
                if "error" in final_res: return {"status": "error", "error_message": final_res["error"]["message"]}
                return {"status": "published", "post_id": final_res.get("id")}
        except Exception as e:
            return {"status": "error", "error_message": str(e)}

    def _publish_to_instagram(self, ig_user_id: str, token: str, caption: str, image_urls: list, video_urls: list) -> dict:
        try:
            is_video_post = bool(video_urls)
            if video_urls:
                create_payload = {"media_type": "REELS", "video_url": video_urls[0], "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram video container response: {create_resp}")
                if "error" in create_resp:
                    return {"status": "error", "error_message": create_resp["error"]["message"], "step": "create_video_container", "raw_error": create_resp["error"]}
                creation_id = create_resp.get("id")
            elif len(image_urls) == 1:
                create_payload = {"image_url": image_urls[0], "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram create container response: {create_resp}")
                if "error" in create_resp: return {"status": "error", "error_message": create_resp["error"]["message"], "step": "create_container", "raw_error": create_resp["error"]}
                creation_id = create_resp.get("id")
            else:
                # Instagram Carousel
                child_ids = []
                for murl in image_urls:
                    res = requests.post(f"{self.base_url}/{ig_user_id}/media", data={"image_url": murl, "is_carousel_item": "true", "access_token": token}).json()
                    logger.info(f"Instagram child container response for {murl}: {res}")
                    if "error" in res: return {"status": "error", "error_message": res["error"]["message"], "step": "create_child_container", "raw_error": res["error"]}
                    child_ids.append(res["id"])
                    
                time.sleep(3) # Wait for children containers to parse
                create_payload = {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption, "access_token": token}
                create_resp = requests.post(f"{self.base_url}/{ig_user_id}/media", data=create_payload).json()
                logger.info(f"Instagram carousel container response: {create_resp}")
                if "error" in create_resp: return {"status": "error", "error_message": create_resp["error"]["message"], "step": "create_carousel_container", "raw_error": create_resp["error"]}
                creation_id = create_resp.get("id")
                
            logger.info(f"Insta Container {creation_id} created. Polling readiness...")
            
            # Step 2: Poll container status
            status_url = f"{self.base_url}/{creation_id}"
            status_params = {"fields": "status_code", "access_token": token}
            max_retries = self.ig_poll_attempts_video if is_video_post else self.ig_poll_attempts_image
            poll_interval = self.ig_poll_interval_video if is_video_post else self.ig_poll_interval_image
            is_finished = False
            last_status_code = None
            started_polling_at = time.time()
            
            for attempt in range(max_retries):
                status_resp = requests.get(status_url, params=status_params, timeout=30)
                status_data = status_resp.json()
                logger.info(f"Instagram status poll payload: {status_data}")
                
                if "error" in status_data:
                    logger.error(f"Instagram status check error: {status_data['error']['message']}")
                    return {"status": "error", "error_message": status_data["error"]["message"], "step": "poll_status"}
                
                status_code = status_data.get("status_code")
                last_status_code = status_code
                logger.info(f"Polling attempt {attempt + 1}: Status is {status_code}")
                
                if status_code == "FINISHED":
                    is_finished = True
                    break
                elif status_code == "IN_PROGRESS":
                    time.sleep(poll_interval)
                else:
                    # Could be "ERROR" or something else
                    logger.error(f"Container failed with status: {status_code}")
                    return {"status": "error", "error_message": f"Container failed with status: {status_code}", "step": "poll_status"}
            
            if not is_finished:
                elapsed = int(time.time() - started_polling_at)
                logger.error(
                    f"Container polling timed out after {elapsed}s. Last status: {last_status_code}. Halting Instagram publish."
                )
                media_label = "video" if is_video_post else "media"
                return {
                    "status": "error",
                    "error_message": f"Instagram {media_label} processing timed out after {elapsed}s. Last status: {last_status_code or 'unknown'}.",
                    "step": "poll_status",
                    "last_status": last_status_code,
                    "poll_elapsed_seconds": elapsed,
                }

            # Step 3: Publish Media Container
            logger.info(f"Container {creation_id} finished. Publishing to feed.")
            publish_url = f"{self.base_url}/{ig_user_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": token
            }
            
            pub_resp = requests.post(publish_url, data=publish_payload)
            pub_data = pub_resp.json()
            logger.info(f"Instagram publish response: {pub_data}")
            
            if "error" in pub_data:
                logger.error(f"Instagram Publish Media Error: {pub_data['error']['message']}")
                return {"status": "error", "error_message": pub_data["error"]["message"], "step": "publish_container"}
                
            return {
                "status": "published",
                "media_id": pub_data.get("id")
            }
            
        except Exception as e:
            logger.error(f"Instagram Request Failed: {str(e)}")
            return {"status": "error", "error_message": str(e)}

# Singleton instance
publish_agent = PublishAgent()
