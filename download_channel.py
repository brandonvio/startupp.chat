#!/usr/bin/env python3
"""
Download all videos from a YouTube channel using the YouTubeDownloadService.

Usage:
    python download_channel.py <channel_handle> [--output <path>] [--format <format>] [--max <num>] [--no-metadata]

Examples:
    python download_channel.py @channelname
    python download_channel.py @channelname --output ./my-videos
    python download_channel.py @channelname --max 10
    python download_channel.py @channelname --format "bestvideo[height<=720]+bestaudio"
    python download_channel.py UCuAXFkgsw1L7xaCfnd5JJOw  # Channel ID format also supported
"""

import sys
import os
import argparse
import json
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from services.youtube_download_service import YouTubeDownloadService
from services.minio_service import MinIOService


def get_minio_config() -> dict:
    """Load MinIO configuration from environment variables."""
    load_dotenv()

    required_vars = [
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    secure = os.getenv("MINIO_SECURE", "false").lower() in ("true", "1", "yes", "on")
    region = os.getenv("MINIO_REGION")

    return {
        "endpoint": os.getenv("MINIO_ENDPOINT"),
        "access_key": os.getenv("MINIO_ACCESS_KEY"),
        "secret_key": os.getenv("MINIO_SECRET_KEY"),
        "bucket_name": os.getenv("MINIO_BUCKET"),
        "secure": secure,
        "region": region,
    }


def init_minio_service() -> MinIOService:
    """Initialize Minio service from environment variables."""
    minio_config = get_minio_config()

    minio_service = MinIOService(
        endpoint=minio_config["endpoint"],
        access_key=minio_config["access_key"],
        secret_key=minio_config["secret_key"],
        bucket_name=minio_config["bucket_name"],
        secure=minio_config["secure"],
        region=minio_config["region"],
    )
    logger.success(f"✅ Connected to Minio at {minio_config['endpoint']}")
    return minio_service


def main():
    parser = argparse.ArgumentParser(
        description="Download all videos from a YouTube channel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s @channelname
  %(prog)s @channelname --output ./my-videos
  %(prog)s @channelname --max 10
  %(prog)s @channelname --format "bestvideo[height<=720]+bestaudio"
  %(prog)s UCuAXFkgsw1L7xaCfnd5JJOw  # Channel ID format

Format Examples:
  bv*+ba/best                     Best video+audio (default)
  bestvideo[height<=720]+bestaudio  720p or lower
  bestvideo[height<=1080]+bestaudio 1080p or lower
  bestaudio                       Audio only
        """,
    )

    parser.add_argument(
        "channel", help="YouTube channel handle (@channelname) or channel ID (UCxxxxxx)"
    )

    parser.add_argument(
        "-o",
        "--output",
        default="downloads",
        help="Output directory (default: downloads)",
    )

    parser.add_argument(
        "-f",
        "--format",
        default="bv*+ba/best",
        help="Format selector for yt-dlp (default: bv*+ba/best)",
    )

    parser.add_argument(
        "-m",
        "--max",
        type=int,
        default=None,
        help="Maximum number of videos to download (default: all)",
    )

    parser.add_argument(
        "--no-metadata", action="store_true", help="Don't save metadata JSON files"
    )

    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save download results to a JSON file",
    )

    args = parser.parse_args()

    # Validate channel input
    if not args.channel:
        logger.error("Channel handle or ID is required")
        sys.exit(1)

    # Convert channel handle/ID to URL and extract channel identifier
    channel = args.channel.strip()
    channel_subfolder = None

    if channel.startswith("@"):
        # Handle format: @channelname
        channel_url = f"https://www.youtube.com/{channel}/videos"
        channel_subfolder = channel  # Keep the @ prefix
        logger.info(f"Using channel handle: {channel}")
    elif channel.startswith("UC") and len(channel) == 24:
        # Channel ID format: UCxxxxxx (24 characters starting with UC)
        channel_url = f"https://www.youtube.com/channel/{channel}/videos"
        channel_subfolder = channel
        logger.info(f"Using channel ID: {channel}")
    elif "youtube.com" in channel:
        # Already a full URL - try to extract channel identifier
        channel_url = channel
        if not channel_url.endswith("/videos"):
            channel_url = channel_url.rstrip("/") + "/videos"

        # Try to extract @handle or channel ID from URL
        if "/@" in channel_url:
            # Extract @handle from URL
            parts = channel_url.split("/@")
            if len(parts) > 1:
                channel_subfolder = "@" + parts[1].split("/")[0]
        elif "/channel/" in channel_url:
            # Extract channel ID from URL
            parts = channel_url.split("/channel/")
            if len(parts) > 1:
                channel_subfolder = parts[1].split("/")[0]
    else:
        logger.error(
            "Invalid channel format. Use @handle, channel ID (UCxxxxxx), or full URL"
        )
        sys.exit(1)

    try:
        # Initialize Minio
        logger.info("Loading MinIO configuration from .env...")
        minio_service = init_minio_service()

        # Initialize service
        service = YouTubeDownloadService(
            minio_service=minio_service,
            default_output_path=args.output,
            default_format=args.format,
        )

        logger.info(f"Channel URL: {channel_url}")
        logger.info(f"Channel subfolder: {channel_subfolder or 'None'}")
        logger.info(f"Output directory: {args.output}")
        logger.info(f"Format: {args.format}")
        logger.info(f"Max videos: {args.max or 'all'}")
        logger.info(f"Save metadata: {not args.no_metadata}")

        # Download all videos from the channel (using playlist download with channel URL)
        results = service.download_playlist(
            playlist_url=channel_url,
            output_path=args.output,
            format_selector=args.format,
            save_metadata=not args.no_metadata,
            max_videos=args.max,
            channel_subfolder=channel_subfolder,
        )

        # Display summary
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]

        logger.success("\nChannel download complete!")
        logger.success(f"Total videos: {len(results)}")
        logger.success(f"Successful: {len(successful)}")

        if failed:
            logger.warning(f"Failed: {len(failed)}")
            logger.warning("\nFailed videos:")
            for r in failed:
                logger.warning(
                    f"  - {r['title']} ({r['video_id']}): {r.get('error', 'Unknown error')}"
                )

        # Save results if requested
        if args.save_results:
            results_path = Path(args.output) / "channel_download_results.json"
            with results_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"\nResults saved to: {results_path}")

        return 0 if not failed else 1

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info("Please set the required environment variables in .env file")
        return 1
    except Exception as e:
        logger.error(f"\nChannel download failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
