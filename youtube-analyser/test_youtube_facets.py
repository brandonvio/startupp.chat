#!/usr/bin/env python3
"""Test YouTube facet posting functionality."""

import os
import sys
from dotenv import load_dotenv
from loguru import logger
from services.bluesky_service import BlueskyService

load_dotenv()


def test_youtube_facets():
    """Test posting with YouTube facets."""

    # Get configuration
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")

    if not handle or not password:
        logger.error("BLUESKY_HANDLE and BLUESKY_PASSWORD must be set in .env file")
        return False

    try:
        # Initialize service
        service = BlueskyService(handle, password, service_url)

        # Test data - try standard YouTube URL format
        youtube_url = (
            "https://www.youtube.com/watch?v=O5xeyoRL95U"  # MIT deep learning video
        )
        post_text = f"Testing YouTube facets! Check out this MIT deep learning masterclass: {youtube_url} #AI #MachineLearning #MIT"

        logger.info("Testing YouTube facet post...")
        logger.info(f"Text: {post_text}")
        logger.info(f"YouTube URL: {youtube_url}")

        # Post with YouTube facets
        success = service.post_with_youtube_facet(
            text=post_text, youtube_url=youtube_url
        )

        if success:
            logger.success("✅ YouTube facet post successful!")
            logger.info(
                "Check your Bluesky feed - the YouTube link should show a rich preview!"
            )
            return True
        else:
            logger.error("❌ YouTube facet post failed")
            return False

    except Exception as e:
        logger.error(f"Test failed: {type(e).__name__}: {e}")
        return False


def main():
    """Main test function."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",
        colorize=True,
    )

    logger.info("YouTube Facets Test")
    logger.info("=" * 50)

    success = test_youtube_facets()

    if success:
        logger.success("\n🎉 YouTube facets test completed successfully!")
        logger.info("The post should appear with a rich YouTube preview on Bluesky!")
    else:
        logger.error("\n❌ YouTube facets test failed.")


if __name__ == "__main__":
    main()
