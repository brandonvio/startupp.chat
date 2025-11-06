#!/usr/bin/env python3
"""Test different types of link posting to understand Bluesky's preview behavior."""

import os
import sys
from dotenv import load_dotenv
from loguru import logger
from services.bluesky_service import BlueskyService

load_dotenv()


def test_different_links():
    """Test different types of links to see what gets rich previews."""

    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")

    if not handle or not password:
        logger.error("Missing Bluesky credentials")
        return False

    try:
        service = BlueskyService(handle, password, service_url)

        # Test different link types
        tests = [
            {
                "name": "Regular website",
                "text": "Check out this website: https://github.com/microsoft/vscode",
                "description": "Should show rich preview for GitHub",
            },
            {
                "name": "News article",
                "text": "Interesting article: https://www.bbc.com/news",
                "description": "News sites usually have rich previews",
            },
            {
                "name": "YouTube standard URL",
                "text": "YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "description": "Standard YouTube URL",
            },
            {
                "name": "YouTube short URL",
                "text": "YouTube video: https://youtu.be/dQw4w9WgXcQ",
                "description": "Short YouTube URL",
            },
        ]

        for i, test in enumerate(tests, 1):
            logger.info(f"\n--- Test {i}: {test['name']} ---")
            logger.info(f"Description: {test['description']}")
            logger.info(f"Text: {test['text']}")

            # Use the simple text-only posting (which should auto-detect links)
            success = service.post_text_only(test["text"])

            if success:
                logger.success("✅ Posted successfully")
            else:
                logger.error("❌ Failed to post")

            # Small delay between posts
            import time

            time.sleep(2)

        return True

    except Exception as e:
        logger.error(f"Test failed: {type(e).__name__}: {e}")
        return False


def main():
    """Main test function."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        colorize=True,
    )

    logger.info("Link Preview Test")
    logger.info("=" * 50)
    logger.info(
        "Testing different types of links to see what gets rich previews on Bluesky"
    )

    success = test_different_links()

    if success:
        logger.success("\n🎉 Link tests completed!")
        logger.info("Check your Bluesky feed to see which links show rich previews")
    else:
        logger.error("\n❌ Link tests failed.")


if __name__ == "__main__":
    main()
