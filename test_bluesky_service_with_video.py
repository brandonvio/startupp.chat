import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from services.bluesky_service import BlueskyService

# Load environment variables
load_dotenv()


def test_bluesky_with_video():
    """
    Test posting to Bluesky with video content using actual files from downloads folder.

    This test reads the Bluesky post text from O5xeyoRL95U-bluesky.txt and posts it
    along with the video file O5xeyoRL95U-sm.mp4 to Bluesky.

    Required .env variables:
    BLUESKY_HANDLE=your.handle.bsky.social
    BLUESKY_PASSWORD=your-app-password
    BLUESKY_SERVICE_URL=https://bsky.social (optional)
    """

    # Get configuration from environment
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")

    if not handle or not password:
        logger.error("BLUESKY_HANDLE and BLUESKY_PASSWORD must be set in .env file")
        logger.info("\nExample .env configuration:")
        logger.info("BLUESKY_HANDLE=your.handle.bsky.social")
        logger.info("BLUESKY_PASSWORD=your-app-password")
        logger.info("BLUESKY_SERVICE_URL=https://bsky.social  # Optional")
        return False

    # Define file paths
    text_file_path = Path("downloads/O5xeyoRL95U-bluesky.txt")
    video_file_path = Path("downloads/O5xeyoRL95U-sm.mp4")

    # Check if files exist
    if not text_file_path.exists():
        logger.error(f"Text file not found: {text_file_path}")
        return False

    if not video_file_path.exists():
        logger.error(f"Video file not found: {video_file_path}")
        return False

    # Read post content from text file
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            post_content = f.read().strip()

        logger.info(f"Read post content ({len(post_content)} characters):")
        logger.info(f"Text: {post_content}")

        video_size = video_file_path.stat().st_size
        logger.info(
            f"Video file size: {video_size:,} bytes ({video_size / 1024 / 1024:.1f}MB)"
        )

    except Exception as e:
        logger.error(f"Failed to read files: {e}")
        return False

    try:
        # Initialize Bluesky service
        logger.info(f"Initializing BlueskyService for {handle}...")
        service = BlueskyService(handle, password, service_url)

        # Test authentication
        logger.info("Testing authentication...")
        if not service.authenticate():
            logger.error("Authentication failed!")
            return False

        logger.success("Authentication successful!")

        # Post with video
        logger.info("Posting content with video to Bluesky...")
        logger.info(f"Post text: {post_content}")
        logger.info(f"Video file: {video_file_path}")

        success = service.post_with_video(text=post_content, video_path=video_file_path)

        if success:
            logger.success(" Successfully posted video content to Bluesky!")
            return True
        else:
            logger.error(" Failed to post video content to Bluesky")
            return False

    except Exception as e:
        logger.error(f"Test failed with error: {type(e).__name__}: {e}")
        return False


def main():
    """Main function to run the test."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="DEBUG",  # Enable debug logging to see curl response details
        colorize=True,
    )

    logger.info("Bluesky Service Video Test")
    logger.info("=" * 50)

    # Check if .env exists
    if not Path(".env").exists():
        logger.error("No .env file found.")
        logger.info("Please create a .env file with your Bluesky credentials:")
        logger.info("BLUESKY_HANDLE=your.handle.bsky.social")
        logger.info("BLUESKY_PASSWORD=your-app-password")
        logger.info("BLUESKY_SERVICE_URL=https://bsky.social  # Optional")
        return

    # Run the test
    success = test_bluesky_with_video()

    if success:
        logger.success("\n<� Video posting test completed successfully!")
    else:
        logger.error(
            "\nL Video posting test failed. Check the output above for details."
        )


if __name__ == "__main__":
    main()
