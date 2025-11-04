#!/usr/bin/env python3
"""
Download all videos from a YouTube playlist using the YouTubeDownloadService.

Usage:
    python download_playlist.py <playlist_url> [--output <path>] [--format <format>] [--max <num>] [--no-metadata]

Examples:
    python download_playlist.py "https://www.youtube.com/playlist?list=PLxxxxxxx"
    python download_playlist.py "https://www.youtube.com/playlist?list=PLxxxxxxx" --output ./my-videos
    python download_playlist.py "https://www.youtube.com/playlist?list=PLxxxxxxx" --max 5
    python download_playlist.py "https://www.youtube.com/playlist?list=PLxxxxxxx" --format "bestvideo[height<=720]+bestaudio"
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
        description="Download all videos from a YouTube playlist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://www.youtube.com/playlist?list=PLxxxxxxx"
  %(prog)s "https://www.youtube.com/playlist?list=PLxxxxxxx" --output ./my-videos
  %(prog)s "https://www.youtube.com/playlist?list=PLxxxxxxx" --max 5
  %(prog)s "https://www.youtube.com/playlist?list=PLxxxxxxx" --format "bestvideo[height<=720]+bestaudio"

Format Examples:
  bv*+ba/best                     Best video+audio (default)
  bestvideo[height<=720]+bestaudio  720p or lower
  bestvideo[height<=1080]+bestaudio 1080p or lower
  bestaudio                       Audio only
        """
    )

    parser.add_argument(
        "playlist_url",
        help="YouTube playlist URL"
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
        "-m", "--max",
        type=int,
        default=None,
        help="Maximum number of videos to download (default: all)"
    )

    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Don't save metadata JSON files"
    )

    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save download results to a JSON file"
    )

    args = parser.parse_args()

    # Validate playlist URL - check for list= parameter or playlist ID
    if not args.playlist_url:
        logger.error("Playlist URL is required")
        sys.exit(1)

    # Convert playlist ID to full URL if needed
    playlist_url = args.playlist_url
    if args.playlist_url.startswith("PL") and "youtube.com" not in args.playlist_url:
        playlist_url = f"https://www.youtube.com/playlist?list={args.playlist_url}"
        logger.info(f"Converted playlist ID to URL: {playlist_url}")
    elif "list=" not in args.playlist_url.lower():
        logger.error("Invalid playlist URL. Must contain 'list=' parameter or be a playlist ID starting with 'PL'")
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

        logger.info(f"Playlist URL: {playlist_url}")
        logger.info(f"Output directory: {args.output}")
        logger.info(f"Format: {args.format}")
        logger.info(f"Max videos: {args.max or 'all'}")
        logger.info(f"Save metadata: {not args.no_metadata}")

        # Download the playlist
        results = service.download_playlist(
            playlist_url=playlist_url,
            output_path=args.output,
            format_selector=args.format,
            save_metadata=not args.no_metadata,
            max_videos=args.max
        )

        # Display summary
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]

        logger.success(f"\nPlaylist download complete!")
        logger.success(f"Total videos: {len(results)}")
        logger.success(f"Successful: {len(successful)}")

        if failed:
            logger.warning(f"Failed: {len(failed)}")
            logger.warning("\nFailed videos:")
            for r in failed:
                logger.warning(f"  - {r['title']} ({r['video_id']}): {r.get('error', 'Unknown error')}")

        # Save results if requested
        if args.save_results:
            results_path = Path(args.output) / "playlist_download_results.json"
            with results_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"\nResults saved to: {results_path}")

        return 0 if not failed else 1

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info("Please set the required environment variables in .env file")
        return 1
    except Exception as e:
        logger.error(f"\nPlaylist download failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
