#!/usr/bin/env python3

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.youtube_download_service import YouTubeDownloadService


def main():
    video_id = "3MZS5gNElZM"
    output_path = "./downloads"

    # Create downloads directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    # Initialize the download service
    download_service = YouTubeDownloadService(
        default_output_path=output_path, default_resolution="best"
    )

    try:
        print(f"Downloading video ID: {video_id}")

        # Get video info first
        print("Getting video information...")
        video_info = download_service.get_video_info(video_id)
        print(f"Title: {video_info.get('title', 'Unknown')}")
        print(f"Duration: {video_info.get('duration', 'Unknown')} seconds")
        print(f"Uploader: {video_info.get('uploader', 'Unknown')}")

        # Download the video
        print("\nStarting download...")
        downloaded_file = download_service.download_video(
            video_id=video_id, output_path=output_path, resolution="best"
        )

        print("\nDownload completed successfully!")
        print(f"File saved to: {downloaded_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
