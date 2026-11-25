import os
import json
import time
import requests
import traceback
import html
from datetime import datetime
from playwright.async_api import async_playwright
from twikit import Client

from shared.config import (
    TEMPLATES_DIR, OUTPUT_DIR, STATE_FILE_PATH,
    FB_PAGE_ID, IG_USER_ID, META_PAGE_ACCESS_TOKEN
)
from shared.logger import get_logger

logger = get_logger("PublisherAgent")

class PublisherAgent:
    def __init__(self):
        pass

    async def render_tweet_image(self, quote_text: str, filename: str = "daily_quote.png") -> str:
        logger.info(f"Rendering high-resolution asset to {filename}...")
        template_path = TEMPLATES_DIR / "tweet_template.html"
        output_image_path = OUTPUT_DIR / filename
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        raw_time = datetime.now().strftime("%I:%M %p · %b %d, %Y")
        current_time = raw_time.lstrip("0").replace(" 0", " ")
        
        rendered_html = html_content.replace("{{ quote }}", html.escape(quote_text))
        rendered_html = rendered_html.replace("{{ timestamp }}", current_time)
        rendered_html = rendered_html.replace("8:00 AM · {{ date }}", current_time)
        
        import uuid
        temp_html_path = TEMPLATES_DIR / f"temp_render_{uuid.uuid4().hex}.html"
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
            
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1080, "height": 1350})
            await page.goto(f"file://{os.path.abspath(temp_html_path)}")
            
            if "video" in filename:
                # Remove timestamp and format specifically for video header
                await page.evaluate("""
                    var ts = document.querySelector('.text-gray-500.text-\\\\[30px\\\\].pt-4');
                    if(ts) ts.style.display = 'none';
                    var card = document.getElementById('tweet-card');
                    card.style.backgroundColor = '#000000';
                    card.style.maxWidth = '1080px';
                    card.style.width = '1080px';
                    card.style.padding = '80px 80px 40px 80px';
                """)
                await page.locator('#tweet-card').screenshot(path=str(output_image_path))
            else:
                await page.screenshot(path=str(output_image_path))
                
            await browser.close()
            
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
            
        return str(output_image_path)

    async def render_tweet_with_custom_photo(self, quote_text: str, custom_photo_path: str, filename: str = "manual_photo_quote.png") -> str:
        logger.info(f"Rendering high-resolution custom photo asset to {filename}...")
        template_path = TEMPLATES_DIR / "tweet_image_template.html"
        output_image_path = OUTPUT_DIR / filename
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        raw_time = datetime.now().strftime("%I:%M %p · %b %d, %Y")
        current_time = raw_time.lstrip("0").replace(" 0", " ")
        
        # Absolute path for local image rendering in playwright
        abs_photo_path = f"file://{os.path.abspath(custom_photo_path)}"
        
        rendered_html = html_content.replace("{{ quote }}", html.escape(quote_text))
        rendered_html = rendered_html.replace("{{ image_src }}", abs_photo_path)
        rendered_html = rendered_html.replace("{{ timestamp }}", current_time)
        
        import uuid
        temp_html_path = TEMPLATES_DIR / f"temp_custom_photo_{uuid.uuid4().hex}.html"
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
            
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1080, "height": 1350})
            await page.goto(f"file://{os.path.abspath(temp_html_path)}")
            # Optional: wait for image to load
            try:
                await page.wait_for_selector("img", state="attached", timeout=3000)
            except:
                pass
            await page.screenshot(path=str(output_image_path))
            await browser.close()
            
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
            
        return str(output_image_path)

    async def render_news_image(self, news_content: str) -> str:
        logger.info("Rendering high-resolution news asset...")
        template_path = TEMPLATES_DIR / "news_template.html"
        output_image_path = OUTPUT_DIR / "daily_news.png"
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        raw_time = datetime.now().strftime("%I:%M %p · %b %d, %Y")
        current_time = raw_time.lstrip("0").replace(" 0", " ")
        
        rendered_html = html_content.replace("{{ news_content }}", html.escape(news_content))
        rendered_html = rendered_html.replace("{{ timestamp }}", current_time)
        
        import uuid
        temp_html_path = TEMPLATES_DIR / f"temp_news_{uuid.uuid4().hex}.html"
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(rendered_html)
            
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1080, "height": 1350})
            await page.goto(f"file://{os.path.abspath(temp_html_path)}")
            await page.screenshot(path=str(output_image_path))
            await browser.close()
            
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
            
        return str(output_image_path)

    async def post_to_x_stealth(self, quote_text: str, image_path: str = None) -> bool:
        logger.info("Preparing to post to X...")
        twikit_client = Client('en-US', timeout=180.0)
        try:
            with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                cookie_data = json.load(f)
                
            cookies_list = cookie_data.get("cookies", cookie_data) if isinstance(cookie_data, dict) else cookie_data
            cookies_dict = {c['name']: c['value'] for c in cookies_list}
            
            twikit_client.set_cookies(cookies_dict)
            
            media_ids = None
            if image_path and os.path.exists(image_path):
                logger.info(f"Uploading media to X: {image_path}")
                media_id = await twikit_client.upload_media(image_path)
                media_ids = [media_id]
                
            await twikit_client.create_tweet(text=quote_text, media_ids=media_ids)
            logger.info("Agent posted to X.")
            return True
        except Exception as e:
            logger.error(f"Failed to post on X: {e}")
            traceback.print_exc()
            return False

    # ---- Meta Graph API helpers -------------------------------------------
    # Token goes in the Authorization header (never in URLs, which end up in logs).
    # Every request has a timeout. Version is configurable via META_GRAPH_VERSION.

    @staticmethod
    def _graph_url(path: str) -> str:
        version = os.getenv("META_GRAPH_VERSION", "v23.0")
        return f"https://graph.facebook.com/{version}/{path.lstrip('/')}"

    @staticmethod
    def _auth_headers(extra: dict | None = None) -> dict:
        headers = {"Authorization": f"OAuth {META_PAGE_ACCESS_TOKEN}"}
        if extra:
            headers.update(extra)
        return headers

    def _graph(self, method: str, path: str, timeout: float = 30.0, **kwargs) -> dict:
        resp = requests.request(
            method, self._graph_url(path), headers=self._auth_headers(), timeout=timeout, **kwargs
        )
        try:
            return resp.json()
        except ValueError:
            return {"error": {"message": f"Non-JSON response (HTTP {resp.status_code})"}}

    def _wait_for_ig_container(self, container_id: str, attempts: int = 24, delay: float = 5.0) -> bool:
        """Polls an IG media container until FINISHED. Runs in a worker thread."""
        for _ in range(attempts):
            status = self._graph("GET", container_id, params={"fields": "status_code"})
            code = status.get("status_code")
            if code == "FINISHED":
                return True
            if code == "ERROR":
                logger.error(f"IG media processing error: {status}")
                return False
            time.sleep(delay)
        logger.error("IG media processing timed out.")
        return False

    def post_to_meta(self, caption: str, image_path: str):
        """Blocking: call via asyncio.to_thread from async code."""
        if not all([FB_PAGE_ID, IG_USER_ID, META_PAGE_ACCESS_TOKEN]):
            logger.error("Missing Meta API credentials in .env file.")
            return False

        if not os.path.exists(image_path):
            logger.error(f"Image file not found at {image_path}")
            return False

        logger.info("--- STARTING META (FB & IG) PUBLISHING ---")
        try:
            with open(image_path, "rb") as image_file:
                fb_data = self._graph(
                    "POST", f"{FB_PAGE_ID}/photos", timeout=120.0,
                    data={"caption": caption}, files={"source": image_file},
                )
            if "id" not in fb_data:
                logger.error(f"Facebook Posting Failed: {fb_data}")
                return False

            photo_id = fb_data["id"]
            logger.info(f"Published to Facebook Page (Photo ID: {photo_id})")

            # IG needs an image URL; reuse the copy Facebook now hosts.
            photo_res = self._graph("GET", photo_id, params={"fields": "images"})
            public_image_url = photo_res["images"][0]["source"]

            container_res = self._graph(
                "POST", f"{IG_USER_ID}/media",
                data={"image_url": public_image_url, "caption": caption},
            )
            if "id" not in container_res:
                logger.error(f"Instagram Container Creation Failed: {container_res}")
                return False

            container_id = container_res["id"]
            if not self._wait_for_ig_container(container_id, attempts=12, delay=3.0):
                return False

            publish_res = self._graph("POST", f"{IG_USER_ID}/media_publish", data={"creation_id": container_id})
            if "id" in publish_res:
                logger.info(f"Published to Instagram Feed (Post ID: {publish_res['id']})")
                return True
            logger.error(f"Instagram Publishing Failed: {publish_res}")
            return False
        except Exception as e:
            logger.error(f"Meta Pipeline Failed: {e}")
            return False

    async def post_video_to_x(self, caption: str, video_path: str) -> bool:
        logger.info("Preparing to post Video to X...")
        twikit_client = Client('en-US', timeout=180.0)
        try:
            with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                cookie_data = json.load(f)
                
            cookies_list = cookie_data.get("cookies", cookie_data) if isinstance(cookie_data, dict) else cookie_data
            cookies_dict = {c['name']: c['value'] for c in cookies_list}
            twikit_client.set_cookies(cookies_dict)
            
            logger.info(f"Uploading video to X: {video_path}")
            media_id = await twikit_client.upload_media(video_path, media_category="tweet_video", wait_for_completion=True)
            await twikit_client.create_tweet(text=caption, media_ids=[media_id])
            logger.info("Agent posted video to X.")
            return True
        except Exception as e:
            logger.error(f"Failed to post video on X: {e}")
            traceback.print_exc()
            return False

    def post_reel_to_meta(self, caption: str, video_path: str) -> bool:
        """Blocking: call via asyncio.to_thread from async code.

        Both Facebook and Instagram use Meta's own resumable upload
        (rupload.facebook.com), so the video is never put on a public host.
        """
        if not all([FB_PAGE_ID, IG_USER_ID, META_PAGE_ACCESS_TOKEN]):
            logger.error("Missing Meta API credentials in .env file.")
            return False

        if not os.path.exists(video_path):
            logger.error(f"Video file not found at {video_path}")
            return False

        logger.info("--- STARTING META REELS PUBLISHING ---")
        overall_success = True
        with open(video_path, "rb") as f:
            video_data = f.read()
        upload_headers = self._auth_headers({"offset": "0", "file_size": str(len(video_data))})

        # 1. FACEBOOK REELS
        try:
            init_res = self._graph("POST", f"{FB_PAGE_ID}/video_reels", data={"upload_phase": "start"})
            if "video_id" in init_res:
                video_id = init_res["video_id"]
                up = requests.post(init_res["upload_url"], headers=upload_headers, data=video_data, timeout=300.0)
                if up.status_code >= 400:
                    logger.error(f"Facebook Reel upload failed: HTTP {up.status_code} {up.text[:300]}")
                    overall_success = False
                else:
                    finish_res = self._graph("POST", f"{FB_PAGE_ID}/video_reels", data={
                        "upload_phase": "finish",
                        "video_id": video_id,
                        "video_state": "PUBLISHED",
                        "description": caption,
                    })
                    if finish_res.get("success"):
                        logger.info(f"Successfully published to Facebook Reels (Video ID: {video_id})")
                    else:
                        logger.error(f"Failed to finalize Facebook Reel: {finish_res}")
                        overall_success = False
            else:
                logger.error(f"Failed to initialize Facebook Reel upload: {init_res}")
                overall_success = False
        except Exception as e:
            logger.error(f"Facebook Reels Pipeline Failed: {e}")
            overall_success = False

        # 2. INSTAGRAM REELS (resumable upload, no public URL needed)
        try:
            ig_res = self._graph("POST", f"{IG_USER_ID}/media", data={
                "media_type": "REELS",
                "upload_type": "resumable",
                "caption": caption,
            })
            if "id" in ig_res and ig_res.get("uri"):
                container_id = ig_res["id"]
                up = requests.post(ig_res["uri"], headers=upload_headers, data=video_data, timeout=300.0)
                if up.status_code >= 400:
                    logger.error(f"IG Reel upload failed: HTTP {up.status_code} {up.text[:300]}")
                    overall_success = False
                elif self._wait_for_ig_container(container_id):
                    ig_pub_res = self._graph("POST", f"{IG_USER_ID}/media_publish", data={"creation_id": container_id})
                    if "id" in ig_pub_res:
                        logger.info(f"Successfully published to Instagram Reels (Post ID: {ig_pub_res['id']})")
                    else:
                        logger.error(f"IG Publish failed: {ig_pub_res}")
                        overall_success = False
                else:
                    overall_success = False
            else:
                logger.error(f"IG resumable container creation failed: {ig_res}")
                overall_success = False
        except Exception as e:
            logger.error(f"Instagram Reels Pipeline Failed: {e}")
            overall_success = False

        return overall_success
