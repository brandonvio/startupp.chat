import os
from typing import Optional
from loguru import logger

from .bluesky_service import BlueskyService


class BlueskyPostBuilder:
    """
    Simplified service for posting to Bluesky with local media files.
    
    This service only handles posting with already available local files.
    All data retrieval and generation should be done before calling this service.
    """

    def __init__(self, bluesky_service: BlueskyService):
        """
        Initialize BlueskyPostBuilder with Bluesky service.

        Args:
            bluesky_service: Bluesky service for posting
        """
        self.bluesky_service = bluesky_service

    async def post_content_with_media(
        self,
        text: str,
        video_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        video_title: str = "Video",
        youtube_url: Optional[str] = None,
        use_youtube_facets: bool = False
    ) -> bool:
        """
        Post content to Bluesky with media or YouTube facets.

        Posting priority:
        1. If use_youtube_facets=True and youtube_url provided: YouTube facet post (rich preview)
        2. If video file available: Upload and post video
        3. If thumbnail available: Post with thumbnail image
        4. Otherwise: Text-only post

        Args:
            text: The post text content
            video_path: Optional path to local video file
            thumbnail_path: Optional path to local thumbnail file
            video_title: Title for alt text (default: "Video")
            youtube_url: Optional YouTube URL for facet posting
            use_youtube_facets: If True, prefer YouTube facets over media uploads

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Authenticating with Bluesky...")
            if not self.bluesky_service.authenticate():
                logger.error("Failed to authenticate with Bluesky")
                return False

            logger.success("Authenticated with Bluesky")

            # Priority 1: YouTube facet posting (if enabled and URL provided)
            if use_youtube_facets and youtube_url:
                logger.info(f"Posting to Bluesky with YouTube facets: {youtube_url}")
                success = self.bluesky_service.post_with_youtube_facet(
                    text=text,
                    youtube_url=youtube_url
                )
            # Priority 2: Video upload
            elif video_path and os.path.exists(video_path):
                logger.info(f"Posting to Bluesky with video: {video_path}")
                success = self.bluesky_service.post_with_video(
                    text=text,
                    video_path=video_path
                )
            # Priority 3: Thumbnail image
            elif thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"Posting to Bluesky with thumbnail: {thumbnail_path}")
                alt_text = f"Thumbnail for {video_title}"
                success = self.bluesky_service.post_with_image(
                    text=text,
                    image_path=thumbnail_path,
                    alt_text=alt_text
                )
            # Priority 4: Text-only fallback
            else:
                logger.info("No media available, posting text only")
                success = self.bluesky_service.post_text_only(text=text)

            if success:
                logger.success("Successfully posted to Bluesky!")
                return True
            else:
                logger.error("Failed to post to Bluesky - posting method returned False")
                return False

        except Exception as e:
            logger.error(f"Exception occurred while posting to Bluesky: {type(e).__name__}: {e}")
            return False
