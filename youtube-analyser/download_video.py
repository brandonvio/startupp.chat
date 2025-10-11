#!/usr/bin/env python3
"""
Download a single YouTube video using the YouTubeDownloadService.

Usage:
    python download_video.py <video_id> [--output <path>] [--format <format>] [--no-metadata]

Examples:
    python download_video.py dQw4w9WgXcQ
    python download_video.py dQw4w9WgXcQ --output ./my-videos
    python download_video.py dQw4w9WgXcQ --format "bestvideo[height<=720]+bestaudio"
    python download_video.py dQw4w9WgXcQ --no-metadata
"""

import sys
import os
import argparse
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
        endpoint=minio_config['endpoint'],
        access_key=minio_config['access_key'],
        secret_key=minio_config['secret_key'],
        bucket_name=minio_config['bucket_name'],
        secure=minio_config['secure'],
        region=minio_config['region']
    )
    logger.success(f"✅ Connected to Minio at {minio_config['endpoint']}")
    return minio_service


def main():
    parser = argparse.ArgumentParser(
        description="Download a YouTube video by ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dQw4w9WgXcQ
  %(prog)s dQw4w9WgXcQ --output ./my-videos
  %(prog)s dQw4w9WgXcQ --format "bestvideo[height<=720]+bestaudio"
  %(prog)s dQw4w9WgXcQ --no-metadata

Format Examples:
  bv*+ba/best                     Best video+audio (default)
  bestvideo[height<=720]+bestaudio  720p or lower
  bestvideo[height<=1080]+bestaudio 1080p or lower
  bestaudio                       Audio only
        """
    )

    parser.add_argument(
        "video_id",
        help="YouTube video ID (e.g., dQw4w9WgXcQ)"
    )

    parser.add_argument(
        "-o", "--output",
        default="downloads",
        help="Output directory (default: downloads)"
    )

    parser.add_argument(
        "-f", "--format",
        default="bv*+ba/best",
        help="Format selector for yt-dlp (default: bv*+ba/best)"
    )

    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Don't save metadata JSON file"
    )

    args = parser.parse_args()

    # Validate video ID
    if not args.video_id or not isinstance(args.video_id, str):
        logger.error("Invalid video ID provided")
        sys.exit(1)

    try:
        # Initialize Minio
        logger.info("Loading MinIO configuration from .env...")
        minio_service = init_minio_service()

        # Initialize service
        service = YouTubeDownloadService(
            minio_service=minio_service,
            default_output_path=args.output,
            default_format=args.format
        )

        logger.info(f"Downloading video: {args.video_id}")
        logger.info(f"Output directory: {args.output}")
        logger.info(f"Format: {args.format}")
        logger.info(f"Save metadata: {not args.no_metadata}")

        # Download the video
        result = service.download_video(
            video_id=args.video_id,
            output_path=args.output,
            format_selector=args.format,
            save_metadata=not args.no_metadata
        )

        logger.success(f"\nDownload complete!")
        if not result.get("skipped"):
            if 'video_path' in result:
                logger.success(f"Video: {result['video_path']}")
            if 'metadata_path' in result:
                logger.success(f"Metadata: {result['metadata_path']}")

        return 0

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info("Please set the required environment variables in .env file")
        return 1
    except Exception as e:
        logger.error(f"\nDownload failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
