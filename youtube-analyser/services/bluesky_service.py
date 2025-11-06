from typing import Optional, List, Union, BinaryIO, Dict, Any
import mimetypes
import re
import time
import requests
import subprocess
import json
import ssl
from pathlib import Path
from datetime import datetime
from loguru import logger

try:
    from atproto import Client, models
except ImportError:
    logger.error("atproto library not found. Install with: pip install atproto")
    raise ImportError("atproto library is required for Bluesky functionality")


class BlueskyService:
    def __init__(
        self, handle: str, password: str, service_url: str = "https://bsky.social"
    ):
        """
        Initialize Bluesky service with credentials.

        Args:
            handle: Bluesky handle (e.g., "user.bsky.social")
            password: App password or account password
            service_url: Bluesky service URL (default: https://bsky.social)
        """
        self.handle = handle
        self.password = password
        self.service_url = service_url
        self.client = Client()
        self._authenticated = False

    def authenticate(self) -> bool:
        """
        Authenticate with Bluesky service.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            logger.info(f"Attempting to authenticate with Bluesky as {self.handle}")
            self.client.login(self.handle, self.password)
            self._authenticated = True
            logger.success(f"Successfully authenticated to Bluesky as {self.handle}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to authenticate to Bluesky as {self.handle}: {type(e).__name__}: {e}"
            )
            self._authenticated = False
            return False

    def _ensure_authenticated(self):
        """Ensure the client is authenticated before making requests."""
        if not self._authenticated:
            if not self.authenticate():
                raise RuntimeError("Not authenticated with Bluesky service")

    def _count_graphemes(self, text: str) -> int:
        """
        Count graphemes (visual characters) in text, which is what Bluesky uses for limits.
        This is more accurate than counting bytes or unicode code points.
        """
        try:
            # Try using the grapheme library if available
            import grapheme

            return grapheme.length(text)
        except ImportError:
            # Fallback: use a simple approximation
            # This isn't perfect but handles basic cases
            import unicodedata

            # Remove combining characters and count
            normalized = unicodedata.normalize("NFC", text)
            return len(normalized)

    def _truncate_to_grapheme_limit(self, text: str, limit: int = 299) -> str:
        """
        Truncate text to fit within Bluesky's grapheme limit.
        Uses limit-1 to leave room for potential encoding differences.
        """
        if self._count_graphemes(text) <= limit:
            return text

        # Simple truncation - could be improved to preserve hashtags
        truncated = text
        while self._count_graphemes(truncated) > limit:
            truncated = truncated[:-1]

        # Add ellipsis if truncated
        if truncated != text:
            while self._count_graphemes(truncated + "...") > limit:
                truncated = truncated[:-1]
            truncated += "..."

        return truncated

    def _create_facets(self, text: str) -> List[dict]:
        """
        Create facets for URLs and hashtags in the text to make them clickable.

        Args:
            text: The text content to scan for URLs and hashtags

        Returns:
            List of facet dictionaries for URLs and hashtags found in the text
        """
        facets = []

        # Pattern to match URLs (http/https)
        url_pattern = r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.-])*(?:\?(?:[\w&=%.~-])*)?(?:#(?:[\w.-])*)?)?"

        # Pattern to match hashtags (# followed by alphanumeric characters, underscores, and some unicode)
        # Hashtags must be word-bounded and can contain letters, numbers, underscores
        hashtag_pattern = (
            r"(?:^|[\s\.,!?;])(#[\w\u00c0-\u024f\u1e00-\u1eff]+)(?=[\s\.,!?;]|$)"
        )

        # Find URLs
        for match in re.finditer(url_pattern, text):
            url = match.group()
            start_pos = match.start()
            end_pos = match.end()

            # Convert character positions to byte positions
            byte_start = len(text[:start_pos].encode("utf-8"))
            byte_end = len(text[:end_pos].encode("utf-8"))

            facet = {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
            }
            facets.append(facet)

        # Find hashtags
        for match in re.finditer(hashtag_pattern, text):
            full_match = match.group()
            hashtag = match.group(1)  # The hashtag without leading whitespace

            # Find the actual position of the hashtag within the full match
            hashtag_start_in_match = full_match.index(hashtag)
            start_pos = match.start() + hashtag_start_in_match
            end_pos = start_pos + len(hashtag)

            # Convert character positions to byte positions
            byte_start = len(text[:start_pos].encode("utf-8"))
            byte_end = len(text[:end_pos].encode("utf-8"))

            # Extract hashtag text without the # symbol for the tag value
            tag_value = hashtag[1:]  # Remove the # symbol

            facet = {
                "index": {"byteStart": byte_start, "byteEnd": byte_end},
                "features": [
                    {"$type": "app.bsky.richtext.facet#tag", "tag": tag_value}
                ],
            }
            facets.append(facet)

        return facets

    def _upload_media(self, media_data: Union[bytes, BinaryIO, str, Path]):
        """
        Upload media to Bluesky and return blob reference.

        Args:
            media_data: Media data as bytes, file-like object, file path string, or Path object

        Returns:
            Blob reference for the uploaded media
        """
        if isinstance(media_data, (str, Path)):
            # File path
            file_path = Path(media_data)
            if not file_path.exists():
                raise FileNotFoundError(f"Media file not found: {file_path}")

            with open(file_path, "rb") as f:
                data = f.read()

            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

        elif isinstance(media_data, bytes):
            # Raw bytes
            data = media_data
            mime_type = "application/octet-stream"

        elif hasattr(media_data, "read"):
            # File-like object
            if hasattr(media_data, "seek"):
                media_data.seek(0)
            data = media_data.read()
            mime_type = getattr(media_data, "content_type", "application/octet-stream")

        else:
            raise TypeError("media_data must be bytes, file path, or file-like object")

        # Upload to Bluesky
        try:
            logger.debug(
                f"Uploading media blob to Bluesky ({len(data)} bytes, {mime_type})"
            )
            response = self.client.upload_blob(data)
            # Extract blob from response
            if hasattr(response, "blob"):
                blob = response.blob
            else:
                # Fallback if response structure is different
                blob = response
            logger.success(f"Successfully uploaded media blob: {blob}")
            return blob
        except Exception as e:
            logger.error(
                f"Failed to upload media blob to Bluesky: {type(e).__name__}: {e}"
            )
            raise

    def post(
        self,
        text: str,
        media: Optional[List[Union[bytes, BinaryIO, str, Path]]] = None,
        alt_texts: Optional[List[str]] = None,
    ) -> bool:
        """
        Post text and optional media to Bluesky.

        Args:
            text: Text content of the post
            media: Optional list of media items (file paths, bytes, or file-like objects)
            alt_texts: Optional list of alt text for each media item

        Returns:
            bool: True if post was successful, False otherwise
        """
        self._ensure_authenticated()

        if not text and not media:
            raise ValueError("Post must contain either text or media")

        try:
            # Create post text and ensure it fits within grapheme limit
            original_text = text or ""
            post_text = self._truncate_to_grapheme_limit(original_text)

            if post_text != original_text:
                logger.warning(
                    f"Post text truncated from {len(original_text)} to {len(post_text)} characters"
                )

            grapheme_count = self._count_graphemes(post_text)
            logger.info(
                f"Preparing Bluesky post ({len(post_text)} characters, {grapheme_count} graphemes, {len(media) if media else 0} media attachments)"
            )

            # Create facets for clickable links and hashtags
            facets = self._create_facets(post_text)
            if facets:
                logger.debug(f"Created {len(facets)} facets for post (links/hashtags)")

            # Handle media attachments
            if media:
                if len(media) > 4:  # Bluesky limit
                    raise ValueError("Maximum 4 media attachments allowed")

                logger.info(f"Processing {len(media)} media attachments...")
                embeds = []
                for i, media_item in enumerate(media):
                    try:
                        logger.debug(
                            f"Processing media attachment {i + 1}/{len(media)}"
                        )
                        blob = self._upload_media(media_item)

                        # Get alt text if provided
                        alt_text = ""
                        if alt_texts and i < len(alt_texts):
                            alt_text = alt_texts[i] or ""

                        # Create image embed
                        embed = models.AppBskyEmbedImages.Image(
                            image=blob, alt=alt_text
                        )
                        embeds.append(embed)
                        logger.debug(f"Successfully processed media attachment {i + 1}")

                    except Exception as e:
                        logger.error(
                            f"Failed to process media item {i + 1}/{len(media)}: {type(e).__name__}: {e}"
                        )
                        raise

                logger.info("Sending post with media to Bluesky...")
                if embeds:
                    embed_data = models.AppBskyEmbedImages.Main(images=embeds)
                    if facets:
                        self.client.send_post(
                            text=post_text, embed=embed_data, facets=facets
                        )
                    else:
                        self.client.send_post(text=post_text, embed=embed_data)
                else:
                    if facets:
                        self.client.send_post(text=post_text, facets=facets)
                    else:
                        self.client.send_post(text=post_text)
            else:
                # Text-only post
                logger.info("Sending text-only post to Bluesky...")
                if facets:
                    self.client.send_post(text=post_text, facets=facets)
                else:
                    self.client.send_post(text=post_text)
            logger.success("Successfully posted to Bluesky")
            return True

        except Exception as e:
            logger.error(f"Failed to post to Bluesky: {type(e).__name__}: {e}")
            return False

    def post_text_only(self, text: str) -> bool:
        """
        Post text-only content to Bluesky.

        Args:
            text: Text content to post

        Returns:
            bool: True if post was successful, False otherwise
        """
        return self.post(text=text)

    def post_with_image(
        self, text: str, image_path: Union[str, Path], alt_text: Optional[str] = None
    ) -> bool:
        """
        Post text with a single image to Bluesky.

        Args:
            text: Text content of the post
            image_path: Path to the image file
            alt_text: Optional alt text for the image

        Returns:
            bool: True if post was successful, False otherwise
        """
        alt_texts = [alt_text] if alt_text else None
        return self.post(text=text, media=[image_path], alt_texts=alt_texts)

    def _extract_youtube_info(self, youtube_url: str) -> dict:
        """Extract YouTube video information for external embed."""
        try:
            # Extract video ID from URL
            import re

            video_id = None

            # Try different YouTube URL formats
            patterns = [
                r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)",
                r"youtube\.com/embed/([a-zA-Z0-9_-]+)",
            ]

            for pattern in patterns:
                match = re.search(pattern, youtube_url)
                if match:
                    video_id = match.group(1)
                    break

            if not video_id:
                logger.warning(f"Could not extract video ID from URL: {youtube_url}")
                return {
                    "uri": youtube_url,
                    "title": "YouTube Video",
                    "description": "Watch this video on YouTube",
                }

            # Try to get video info (simplified approach)
            title = f"YouTube Video ({video_id})"
            description = "Watch this video on YouTube"
            thumb_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

            return {
                "uri": youtube_url,
                "title": title,
                "description": description,
                "thumb_url": thumb_url,
            }

        except Exception as e:
            logger.warning(f"Failed to extract YouTube info: {e}")
            return {
                "uri": youtube_url,
                "title": "YouTube Video",
                "description": "Watch this video on YouTube",
            }

    def post_with_youtube_facet(self, text: str, youtube_url: str) -> bool:
        """
        Post text with a YouTube URL using Bluesky external embed for rich preview.

        This creates a rich card preview for the YouTube video using app.bsky.embed.external.

        Args:
            text: Text content of the post
            youtube_url: YouTube video URL (e.g., https://youtube.com/watch?v=...)

        Returns:
            bool: True if post was successful, False otherwise
        """
        self._ensure_authenticated()

        try:
            # Ensure text fits within grapheme limit
            original_text = text
            post_text = self._truncate_to_grapheme_limit(text)

            if post_text != original_text:
                logger.warning(
                    f"Post text truncated from {len(original_text)} to {len(post_text)} characters"
                )

            grapheme_count = self._count_graphemes(post_text)
            logger.info(
                f"Preparing YouTube external embed post ({grapheme_count} graphemes, {len(post_text)} characters)"
            )

            # Extract YouTube info
            youtube_info = self._extract_youtube_info(youtube_url)
            logger.info(f"YouTube info: {youtube_info}")

            # Try to upload thumbnail if available
            thumb_blob = None
            if "thumb_url" in youtube_info:
                try:
                    logger.debug(
                        f"Downloading YouTube thumbnail: {youtube_info['thumb_url']}"
                    )
                    import requests

                    thumb_response = requests.get(youtube_info["thumb_url"], timeout=10)
                    thumb_response.raise_for_status()

                    # Upload thumbnail to Bluesky
                    thumb_data = thumb_response.content
                    thumb_blob = self._upload_media(thumb_data)
                    logger.success("Successfully uploaded YouTube thumbnail")

                except Exception as e:
                    logger.warning(f"Failed to upload YouTube thumbnail: {e}")

            # Create external embed
            external_embed = {
                "uri": youtube_info["uri"],
                "title": youtube_info["title"],
                "description": youtube_info["description"],
            }

            if thumb_blob:
                external_embed["thumb"] = thumb_blob

            # Create facets for hashtags and any other URLs in the text
            facets = self._create_facets(post_text)
            logger.debug(f"Created {len(facets)} facets for hashtags/links")

            # Create the post with external embed and facets
            user_did = self.client.me.did

            post_data = {
                "$type": "app.bsky.feed.post",
                "text": post_text,
                "embed": {
                    "$type": "app.bsky.embed.external",
                    "external": external_embed,
                },
                "createdAt": datetime.now().isoformat() + "Z",
                "langs": ["en"],
            }

            # Add facets if any were created
            if facets:
                post_data["facets"] = facets
                logger.debug(f"Added {len(facets)} facets to post")

            logger.info("Sending YouTube external embed post to Bluesky...")
            logger.debug(f"Post data: {post_data}")

            try:
                response = self.client.com.atproto.repo.create_record(
                    {
                        "repo": user_did,
                        "collection": "app.bsky.feed.post",
                        "record": post_data,
                    }
                )

                logger.success("Successfully posted YouTube external embed to Bluesky")
                logger.debug(f"Create record response: {response}")

                # Log response details
                if hasattr(response, "uri"):
                    logger.info(f"Post URI: {response.uri}")
                if hasattr(response, "cid"):
                    logger.info(f"Post CID: {response.cid}")

                # Try to extract the post URL for easy access
                if hasattr(response, "uri"):
                    # Convert AT-URI to web URL
                    # Format: at://did:plc:.../app.bsky.feed.post/...
                    uri_parts = response.uri.split("/")
                    if len(uri_parts) >= 5:
                        did = uri_parts[2]
                        rkey = uri_parts[-1]
                        # Convert DID to handle if possible
                        try:
                            profile = self.client.get_profile(did)
                            handle = profile.handle
                            post_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
                            logger.info(f"🔗 Post URL: {post_url}")
                        except Exception as e:
                            logger.debug(f"Could not resolve handle: {e}")
                            logger.info(f"🔗 Post AT-URI: {response.uri}")

                return True

            except Exception as create_error:
                logger.error(
                    f"Failed to create external embed post: {type(create_error).__name__}: {create_error}"
                )

                # Log detailed error info
                if hasattr(create_error, "response"):
                    logger.error(f"Error response: {create_error.response}")
                if hasattr(create_error, "status_code"):
                    logger.error(f"Status code: {create_error.status_code}")

                raise

        except Exception as e:
            logger.error(
                f"Failed to post YouTube external embed to Bluesky: {type(e).__name__}: {e}"
            )
            return False

    def _debug_ssl_context(self) -> None:
        """Debug SSL context and configuration."""
        try:
            logger.info(f"SSL version: {ssl.OPENSSL_VERSION}")
            logger.info(f"SSL version info: {ssl.OPENSSL_VERSION_INFO}")

            # Test basic connectivity to Bluesky video service
            import socket

            logger.info("Testing connectivity to video.bsky.app...")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex(("video.bsky.app", 443))
            sock.close()

            if result == 0:
                logger.info("✓ Can connect to video.bsky.app:443")
            else:
                logger.error(
                    f"✗ Cannot connect to video.bsky.app:443 (error: {result})"
                )

        except Exception as e:
            logger.error(f"SSL debugging failed: {e}")

    def _get_video_aspect_ratio(self, video_path: str) -> Dict[str, int]:
        """Get video aspect ratio using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    width = stream.get("width", 1280)
                    height = stream.get("height", 720)
                    logger.info(f"Detected video dimensions: {width}x{height}")
                    return {"width": width, "height": height}

            # Fallback dimensions
            logger.warning("Could not detect video dimensions, using fallback 1280x720")
            return {"width": 1280, "height": 720}

        except Exception as e:
            logger.warning(f"Failed to get video dimensions, using fallback: {e}")
            return {"width": 1280, "height": 720}

    def _upload_video_debug(
        self, video_path: Union[str, Path]
    ) -> Optional[Dict[str, Any]]:
        """Upload video to Bluesky with extensive debugging."""
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")

            file_size = video_path.stat().st_size
            logger.info(f"Starting video upload: {video_path}")
            logger.info(
                f"File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f}MB)"
            )

            # Debug SSL/connectivity first
            self._debug_ssl_context()

            # Get user info
            me_response = self.client.me
            user_did = me_response.did
            logger.info(f"User DID: {user_did}")

            # Get service auth token
            logger.info("Requesting service auth token...")
            try:
                # Get user's PDS information from session
                session = self.client.com.atproto.server.get_session()
                # Extract PDS DID from the error message format: should be "did:web:leccinum.us-west.host.bsky.network"
                pds_host = session.did_doc.service[0].service_endpoint.replace(
                    "https://", ""
                )
                pds_did = f"did:web:{pds_host}"
                logger.debug(f"User PDS DID: {pds_did}")

                # Create service auth token with PDS DID as audience
                service_auth_response = self.client.com.atproto.server.get_service_auth(
                    {
                        "aud": pds_did,  # Use PDS DID as audience
                        "lxm": "com.atproto.repo.uploadBlob",
                        "exp": int(time.time()) + 30 * 60,  # 30 minutes
                    }
                )
                token = service_auth_response.token
                logger.info(f"✓ Got service auth token (length: {len(token)})")
            except Exception as e:
                logger.error(
                    f"Failed to get service auth token: {type(e).__name__}: {e}"
                )
                raise

            # Prepare upload parameters
            upload_url = "https://video.bsky.app/xrpc/app.bsky.video.uploadVideo"
            params = {"did": user_did, "name": video_path.name}
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "User-Agent": "youtube-analyser/1.0",
            }

            logger.info(f"Upload URL: {upload_url}")
            logger.info(f"Upload params: {params}")
            logger.info(
                f"Headers: {dict((k, v if k != 'Authorization' else 'Bearer ***') for k, v in headers.items())}"
            )

            # Upload the video file
            logger.info("Uploading video file...")
            try:
                with open(video_path, "rb") as f:
                    upload_response = requests.post(
                        upload_url,
                        params=params,
                        headers=headers,
                        data=f,
                        timeout=(60, 600),  # Longer timeout for video uploads
                        verify=True,
                    )
                    upload_response.raise_for_status()
                    logger.success("✓ Video upload successful")
            except requests.exceptions.SSLError as e:
                logger.warning(f"SSL error with requests, trying curl fallback: {e}")
                upload_response = self._try_curl_upload(
                    upload_url, params, headers, video_path, file_size
                )
            except Exception as e:
                logger.error(f"Upload failed: {type(e).__name__}: {e}")
                raise

            # Process response
            job_status = upload_response.json()
            job_id = job_status.get("jobId")
            blob = job_status.get("blob")

            logger.info(f"Upload job created: {job_id}")
            logger.info(f"Immediate blob: {'Yes' if blob else 'No, will poll'}")

            # Poll for completion if needed
            if not blob:
                if not job_id:
                    raise RuntimeError(
                        "No jobId returned from video upload and no immediate blob"
                    )
                blob = self._poll_for_completion(job_id, token)

            logger.success("Video upload completed successfully")
            return blob

        except Exception as e:
            logger.error(f"Video upload failed: {type(e).__name__}: {e}")
            logger.error(f"Error details: {str(e)}")
            return None

    def _try_curl_upload(self, upload_url, params, headers, video_path, file_size):
        """Try using curl as a fallback."""
        import shutil

        if not shutil.which("curl"):
            raise RuntimeError("curl not available")

        # Build curl command
        cmd = [
            "curl",
            "-X",
            "POST",
            f"{upload_url}?" + "&".join(f"{k}={v}" for k, v in params.items()),
            "--data-binary",
            f"@{video_path}",
            "--connect-timeout",
            "30",
            "--max-time",
            "300",
            "-s",  # Silent mode to avoid progress output
        ]

        # Add headers
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])

        # Execute curl
        logger.debug(
            f"Executing curl command: {' '.join(cmd[:5])} [... headers omitted ...]"
        )
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=350)
        if result.returncode != 0:
            logger.error(f"Curl stderr: {result.stderr}")
            raise RuntimeError(
                f"curl failed with exit code {result.returncode}: {result.stderr}"
            )

        # Debug the response
        logger.debug(f"Curl stdout: {result.stdout}")
        logger.debug(f"Curl stderr: {result.stderr}")

        # Validate and parse JSON response
        try:
            response_data = json.loads(result.stdout)
            logger.debug(f"Parsed JSON response: {response_data}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse curl response as JSON: {e}")
            logger.error(f"Raw response: {result.stdout}")
            raise RuntimeError(f"Invalid JSON response from video upload: {e}")

        # Create a simple response-like object with the JSON data
        class CurlResponse:
            def __init__(self, data, status_code=200):
                self._data = data
                self.status_code = status_code

            def json(self):
                return self._data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

        return CurlResponse(response_data)

    def _poll_for_completion(self, job_id: str, token: str) -> Optional[Dict[str, Any]]:
        """Poll for video processing completion."""
        headers = {"Authorization": f"Bearer {token}"}
        poll_timeout = 300
        poll_start = time.time()

        while time.time() - poll_start < poll_timeout:
            try:
                response = requests.get(
                    "https://video.bsky.app/xrpc/app.bsky.video.getJobStatus",
                    params={"jobId": job_id},
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()

                data = response.json()
                job_info = data.get("jobStatus", {})
                state = job_info.get("state")
                progress = job_info.get("progress", "")

                logger.info(f"Processing status: {state} {progress}")

                if job_info.get("blob"):
                    return job_info["blob"]
                elif state == "failed":
                    raise RuntimeError(
                        f"Processing failed: {job_info.get('error', 'Unknown error')}"
                    )

                time.sleep(2)
            except Exception as e:
                logger.warning(f"Polling error: {e}")
                time.sleep(5)
                continue

        raise RuntimeError(f"Processing timed out after {poll_timeout} seconds")

    def post_with_video(self, text: str, video_path: Union[str, Path]) -> bool:
        """Post text with a video to Bluesky."""
        self._ensure_authenticated()

        try:
            logger.info(f"Preparing Bluesky post with video: {video_path}")

            # Upload video with debugging
            video_blob = self._upload_video_debug(video_path)
            if not video_blob:
                logger.error("Failed to upload video")
                return False

            # Get video aspect ratio
            aspect_ratio = self._get_video_aspect_ratio(str(video_path))

            # Ensure text fits within grapheme limit
            original_text = text
            post_text = self._truncate_to_grapheme_limit(text)

            if post_text != original_text:
                logger.warning(
                    f"Post text truncated from {len(original_text)} to {len(post_text)} characters"
                )

            grapheme_count = self._count_graphemes(post_text)
            logger.info(
                f"Post text: {grapheme_count} graphemes, {len(post_text)} characters"
            )

            # Create facets
            facets = self._create_facets(post_text)
            if facets:
                logger.debug(f"Created {len(facets)} facets for post")

            # Create video embed
            embed_data = {
                "$type": "app.bsky.embed.video",
                "video": video_blob,
                "aspectRatio": aspect_ratio,
            }

            # Send post
            logger.info("Sending post with video to Bluesky...")
            user_did = self.client.me.did

            post_data = {"text": post_text, "embed": embed_data}
            if facets:
                post_data["facets"] = facets

            self.client.com.atproto.repo.create_record(
                {
                    "repo": user_did,
                    "collection": "app.bsky.feed.post",
                    "record": {
                        **post_data,
                        "createdAt": datetime.now().isoformat() + "Z",
                        "langs": ["en"],
                    },
                }
            )

            logger.success("Successfully posted video to Bluesky")
            return True

        except Exception as e:
            logger.error(f"Failed to post video to Bluesky: {type(e).__name__}: {e}")
            return False
