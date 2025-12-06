#!/usr/bin/env python3
"""
downloader.py
Download a YouTube video using the YouTubeDownloadService.
Automatically uploads to Minio storage.

Usage:
  python downloader.py <VIDEO_ID>

Example:
  python downloader.py dQw4w9WgXcQ
"""

import os
import sys
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
    if len(sys.argv) != 2:
        print("Usage: python downloader.py <VIDEO_ID>")
        sys.exit(1)

    video_id = sys.argv[1].strip()

    try:
        # Initialize Minio
        logger.info("Loading MinIO configuration from .env...")
        minio_service = init_minio_service()

        # Initialize service
        service = YouTubeDownloadService(
            minio_service=minio_service,
            default_output_path="downloads",
            default_format="bv*+ba/best",
        )

        result = service.download_video(video_id=video_id)

        if result.get("skipped"):
            logger.info(f"Video {video_id} already exists in Minio - skipped download")
        else:
            logger.success(f"✅ Download and upload complete for {video_id}!")

        return 0

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info("Please set the required environment variables in .env file")
        return 1
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
