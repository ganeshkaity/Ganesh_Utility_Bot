import os
import uuid
import asyncio
import logging
import aiohttp
import aiofiles
import yt_dlp
import tempfile
from typing import Optional, List, Dict
from groq import Groq

logger = logging.getLogger(__name__)

class GroqChatWrapper:
    """Wrapper for Groq API chat completions."""
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model_id = "llama-3.3-70b-versatile"  # Fast, free-tier friendly

    async def generate_response(self, prompt: str, history: Optional[List[Dict]] = None) -> str:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Build messages list from history
                messages = []
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})

                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model_id,
                    messages=messages,
                    max_tokens=2048,
                )
                return response.choices[0].message.content
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"Rate limited. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                logger.error(f"Groq API error: {e}")
                if "429" in error_str:
                    return "⏳ Rate-limited. Please wait a moment and try again."
                return f"Sorry, I encountered an error: {error_str}"
        return "⏳ Still rate-limited. Please wait a minute and try again."

class YouTubeDownloader:
    def __init__(self):
        self.output_dir = tempfile.gettempdir()

    async def download_audio(self, query: str, progress_hook=None) -> Optional[tuple[str, str]]:
        """
        Downloads the best audio from YouTube and converts it to MP3.
        Returns a tuple: (file_path, sanitized_title)
        """
        unique_id = str(uuid.uuid4())
        # We'll use the unique_id for the initial download to avoid conflicts, then rename or just pass the title
        output_template = os.path.join(self.output_dir, f"{unique_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'logger': logger,
            'progress_hooks': [progress_hook] if progress_hook else [],
            'default_search': 'ytsearch1',
            'noplaylist': True,
        }

        try:
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=True)
                    title = info.get('title', 'Unknown Title')
                    # Sanitize title for filename
                    import re
                    sanitized_title = re.sub(r'[\\/*?:"<>|]', "", title)
                    final_path = os.path.join(self.output_dir, f"{unique_id}.mp3")
                    return final_path, sanitized_title

            file_path, title = await asyncio.to_thread(_download)
            if os.path.exists(file_path):
                return file_path, title
        except Exception as e:
            logger.error(f"YouTube download error: {e}")
        return None

    async def get_video_url(self, query: str) -> Optional[tuple[str, str]]:
        """
        Gets the direct video URL and title without downloading.
        Returns a tuple: (video_url, title)
        """
        ydl_opts = {
            # 22 is 720p progressive, 18 is 360p progressive. 
            # These are single-URL formats that don't require merging or file saving.
            'format': '22/18/best[ext=mp4]/best',
            'quiet': True,
            'default_search': 'ytsearch1',
            'noplaylist': True,
        }
        try:
            def _get_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    return info.get('url'), info.get('title', 'Video')

            return await asyncio.to_thread(_get_info)
        except Exception as e:
            logger.error(f"Error getting video URL: {e}")
            return None

    async def get_audio_url(self, query: str) -> Optional[tuple[str, str]]:
        """
        Gets a direct audio URL and title without downloading.
        Returns a tuple: (audio_url, title)
        """
        ydl_opts_no_cookies = {
            'format': '140/bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch1',
            'noplaylist': True,
        }
        
        ydl_opts_cookies = {
            'format': '140/bestaudio/best',
            'quiet': True,
            'cookiesfrombrowser': ('chrome',),
            'default_search': 'ytsearch1',
            'noplaylist': True,
        }

        try:
            def _get_info(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    return info.get('url'), info.get('title', 'Audio')

            try:
                # First attempt: No cookies
                return await asyncio.to_thread(_get_info, ydl_opts_no_cookies)
            except Exception:
                # Second attempt: With cookies
                logger.info("Retrying YouTube Audio with Chrome cookies...")
                return await asyncio.to_thread(_get_info, ydl_opts_cookies)

        except Exception as e:
            logger.error(f"Error getting audio URL: {e}")
            return None

class InstagramDownloader:
    """Fetches direct links for Instagram Reels."""
    async def get_reel_url(self, url: str) -> Optional[tuple[str, str]]:
        """
        Gets the direct video URL and title for an Instagram Reel.
        Uses Chrome cookies to bypass login screens.
        """
        # Try without cookies first (faster and avoids locks for public reels)
        ydl_opts_no_cookies = {
            'format': 'best',
            'quiet': True,
            'noplaylist': True,
        }
        
        # Fallback with cookies
        ydl_opts_cookies = {
            'format': 'best',
            'quiet': True,
            'cookiesfrombrowser': ('chrome',),
            'noplaylist': True,
        }

        try:
            def _get_info(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return info.get('url'), info.get('title', 'Instagram Reel')

            # First attempt: No cookies
            try:
                return await asyncio.to_thread(_get_info, ydl_opts_no_cookies)
            except Exception:
                # Second attempt: With cookies
                logger.info("Retrying Instagram with Chrome cookies...")
                return await asyncio.to_thread(_get_info, ydl_opts_cookies)

        except Exception as e:
            error_msg = str(e)
            if "cookie database" in error_msg.lower():
                logger.error("Instagram Cookie Error: Chrome database is locked. Close Chrome and try again.")
            else:
                logger.error(f"Instagram reel error: {e}")
            return None

class ImageGenerator:
    """Generates images using Hugging Face Inference API."""
    
    # Map friendly names to Hugging Face model IDs
    MODELS = {
        "flux": "black-forest-labs/FLUX.1-schnell",
        "stable-diffusion-xl": "stabilityai/stable-diffusion-xl-base-1.0",
        "openjourney": "prompthero/openjourney-v4",
        "dreamshaper": "Lykon/dreamshaper-xl-v2-turbo",
        "anime": "cagliostrolab/animagine-xl-3.1",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_image(self, prompt: str, model_key: str, width: int, height: int) -> Optional[bytes]:
        """Generates an image using HuggingFace Inference API and returns raw bytes."""
        model_id = self.MODELS.get(model_key, self.MODELS["flux"])
        url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {"width": width, "height": height}
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        body = await response.text()
                        logger.error(f"HuggingFace API error ({response.status}): {body}")
        except Exception as e:
            logger.error(f"Image generation error: {e}")
        return None

async def cleanup_file(file_path: Optional[str]):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")
