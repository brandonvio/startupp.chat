from typing import Optional, Dict, List
import json
import os
from pathlib import Path
import yt_dlp
from loguru import logger

from services.minio_service import MinIOService


class YouTubeDownloadService:
    """Service for downloading YouTube videos using yt-dlp with optional Minio storage."""

    def __init__(
        self,
        minio_service: MinIOService,
        default_output_path: str = "downloads",
        default_format: str = "bv*+ba/best",
        minio_folder: str = "downloads",
        cleanup_local: bool = True,
    ):
        """
        Initialize the YouTube download service.

        Args:
            minio_service: MinIOService instance for cloud storage (required)
            default_output_path: Default directory for downloads (default: "downloads")
            default_format: Default format selector (default: "bv*+ba/best")
            minio_folder: Folder in Minio bucket for videos (default: "downloads")
            cleanup_local: Whether to delete local files after Minio upload (default: True)
        """
        self.minio_service = minio_service
        self.default_output_path = default_output_path
        self.default_format = default_format
        self.minio_folder = minio_folder
        self.cleanup_local = cleanup_local

    def _progress_hook(self, d: Dict) -> None:
        """Progress hook for displaying download progress."""
        if d.get("status") == "downloading":
            pct = (d.get("_percent_str") or "").strip()
            spd = (d.get("_speed_str") or "").strip()
            eta = (d.get("_eta_str") or "").strip()
            print(f"\r{pct:>6} {spd:>10} ETA {eta:>6}", end="", flush=True)
        elif d.get("status") == "finished":
            print("\nMerging…", flush=True)

    def download_video(
        self,
        video_id: str,
        output_path: Optional[str] = None,
        format_selector: Optional[str] = None,
        save_metadata: bool = True,
        channel_subfolder: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Downloads a YouTube video by ID using yt-dlp.
        Saves video in subdirectory: {output_path}/{video_id}/{video_id}.mp4
        Optionally saves metadata as: {output_path}/{video_id}/{video_id}.json
        If Minio is configured, uploads to Minio and optionally cleans up local files.

        Args:
            video_id: The YouTube video ID
            output_path: The folder where videos will be saved (default: "downloads")
            format_selector: Format selector (default: "bv*+ba/best")
            save_metadata: Whether to save metadata as JSON (default: True)
            channel_subfolder: Optional channel subfolder (e.g., @channelname) to organize videos in Minio

        Returns:
            Dict with 'video_path', 'metadata_path', and Minio info if applicable

        Raises:
            ValueError: If video ID is invalid
            Exception: If download fails
        """
        if not video_id or not isinstance(video_id, str):
            raise ValueError("Valid video ID is required")

        output_path = output_path or self.default_output_path
        format_selector = format_selector or self.default_format

        # Determine Minio folder path based on channel_subfolder
        if channel_subfolder:
            minio_path = f"{self.minio_folder}/{channel_subfolder}/{video_id}"
        else:
            minio_path = f"{self.minio_folder}/{video_id}"

        # Check if files already exist in Minio
        video_filename = f"{video_id}.mp4"
        metadata_filename = f"{video_id}.json"

        video_exists = self.minio_service.object_exists(minio_path, video_filename)
        metadata_exists = self.minio_service.object_exists(
            minio_path, metadata_filename
        )

        if video_exists and metadata_exists:
            logger.info(
                f"⏭️  Skipping {video_id} - files already exist in Minio storage"
            )
            video_info = self.minio_service.get_object_info(minio_path, video_filename)
            if video_info:
                logger.info(
                    f"☁️  Video: {video_info['object_name']} ({video_info['size'] / 1024 / 1024:.1f} MB)"
                )
            logger.info(f"☁️  Metadata: {minio_path}/{metadata_filename}")

            return {
                "skipped": True,
                "already_exists_in_minio": True,
                "minio_video_path": f"{minio_path}/{video_filename}",
                "minio_metadata_path": f"{minio_path}/{metadata_filename}",
            }

        # Create video-specific subdirectory
        video_dir = Path(output_path) / video_id
        video_dir.mkdir(parents=True, exist_ok=True)

        url = f"https://www.youtube.com/watch?v={video_id}"

        # Force filenames to <videoid>.<ext> in ./downloads/<videoid>/
        base = str(video_dir / video_id)

        ydl_opts = {
            "format": format_selector,
            "merge_output_format": "mp4",
            "outtmpl": {"default": base + ".%(ext)s"},
            "writesubtitles": False,
            "writeautomaticsub": False,
            "writethumbnail": False,
            "writeinfojson": False,  # We'll write our own JSON
            "skip_download": False,
            "progress_hooks": [self._progress_hook],
            "retries": 5,
            "fragment_retries": 5,
            "continuedl": True,
            "overwrites": False,
            "quiet": False,
            "no_warnings": False,
            "concurrent_fragment_downloads": 5,
            # Anti-bot bypass options
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }

        try:
            logger.info(f"Starting download of video: {video_id}")

            # Download the video and capture metadata
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            # Find the downloaded video file
            video_path = next(video_dir.glob(f"{video_id}.*"))
            logger.success(f"Saved video to: {video_path}")

            result = {"video_path": str(video_path)}

            # Save metadata if requested
            metadata_path = None
            if save_metadata and info:
                metadata_path = video_dir / f"{video_id}.json"
                with metadata_path.open("w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2, default=str)
                logger.success(f"Saved metadata to: {metadata_path}")
                result["metadata_path"] = str(metadata_path)

            # Upload to Minio
            logger.info("\n📤 Uploading to Minio storage...")

            # Upload video file
            video_uploaded = self.minio_service.save_file(
                file_path=str(video_path),
                folder=minio_path,
                metadata={
                    "video-id": video_id,
                    "title": info.get("title", ""),
                    "uploader": info.get("uploader", ""),
                    "duration": str(info.get("duration", 0)),
                },
            )

            result["minio_video_uploaded"] = video_uploaded
            result["minio_video_path"] = f"{minio_path}/{video_path.name}"
            logger.success(f"✅ Video uploaded to Minio: {result['minio_video_path']}")

            # Upload metadata file if it exists
            if metadata_path and metadata_path.exists():
                metadata_uploaded = self.minio_service.save_file(
                    file_path=str(metadata_path),
                    folder=minio_path,
                    metadata={
                        "video-id": video_id,
                        "file-type": "metadata",
                    },
                )

                result["minio_metadata_uploaded"] = metadata_uploaded
                result["minio_metadata_path"] = f"{minio_path}/{metadata_path.name}"
                logger.success(
                    f"✅ Metadata uploaded to Minio: {result['minio_metadata_path']}"
                )

            # Clean up local files
            if self.cleanup_local:
                logger.info("🧹 Cleaning up local files...")
                if video_path.exists():
                    os.remove(video_path)
                if metadata_path and metadata_path.exists():
                    os.remove(metadata_path)
                # Remove video directory if empty
                if video_dir.exists() and not any(video_dir.iterdir()):
                    video_dir.rmdir()
                logger.success("✅ Local files cleaned up")
                result["local_files_cleaned"] = True

            return result

        except Exception as e:
            logger.error(f"Failed to download video {video_id}: {str(e)}")
            raise Exception(f"Download failed for video {video_id}: {str(e)}")

    def get_video_info(self, video_id: str) -> Dict:
        """
        Get video information without downloading.

        Args:
            video_id: The YouTube video ID

        Returns:
            Video information dictionary

        Raises:
            ValueError: If video ID is invalid
            Exception: If fetching info fails
        """
        if not video_id:
            raise ValueError("Video ID cannot be empty")

        url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "quiet": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {str(e)}")
            raise Exception(f"Failed to get video info for {video_id}: {str(e)}")

    def get_playlist_videos(self, playlist_url: str) -> List[Dict[str, str]]:
        """
        Get list of video IDs and titles from a YouTube playlist.

        Args:
            playlist_url: URL of the YouTube playlist

        Returns:
            List of dicts with 'id', 'title', 'url' keys

        Raises:
            Exception: If fetching playlist fails
        """
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,  # Don't download, just get metadata
            "force_generic_extractor": False,
        }

        try:
            logger.info(f"Fetching playlist: {playlist_url}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(playlist_url, download=False)

                if "entries" not in playlist_info:
                    raise Exception("No videos found in playlist")

                videos = []
                for entry in playlist_info["entries"]:
                    if entry:  # Some entries might be None if video is unavailable
                        videos.append(
                            {
                                "id": entry.get("id"),
                                "title": entry.get("title", "Unknown"),
                                "url": entry.get("url")
                                or f"https://www.youtube.com/watch?v={entry.get('id')}",
                                "duration": entry.get("duration"),
                                "uploader": entry.get("uploader"),
                            }
                        )

                logger.success(f"Found {len(videos)} videos in playlist")
                return videos

        except Exception as e:
            logger.error(f"Failed to fetch playlist: {str(e)}")
            raise Exception(f"Failed to fetch playlist: {str(e)}")

    def download_playlist(
        self,
        playlist_url: str,
        output_path: Optional[str] = None,
        format_selector: Optional[str] = None,
        save_metadata: bool = True,
        max_videos: Optional[int] = None,
        channel_subfolder: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        Download all videos from a YouTube playlist.

        Args:
            playlist_url: URL of the YouTube playlist
            output_path: The folder where videos will be saved
            format_selector: Format selector
            save_metadata: Whether to save metadata as JSON
            max_videos: Maximum number of videos to download (None for all)
            channel_subfolder: Optional channel subfolder (e.g., @channelname) to organize videos in Minio

        Returns:
            List of download results with status information
        """
        try:
            videos = self.get_playlist_videos(playlist_url)

            if max_videos:
                videos = videos[:max_videos]

            logger.info(f"Starting download of {len(videos)} videos from playlist")

            results = []
            for idx, video in enumerate(videos, 1):
                video_id = video["id"]
                logger.info(
                    f"\n[{idx}/{len(videos)}] Downloading: {video['title']} ({video_id})"
                )

                try:
                    result = self.download_video(
                        video_id=video_id,
                        output_path=output_path,
                        format_selector=format_selector,
                        save_metadata=save_metadata,
                        channel_subfolder=channel_subfolder,
                    )
                    results.append(
                        {
                            "video_id": video_id,
                            "title": video["title"],
                            "status": "success",
                            "paths": result,
                        }
                    )

                except Exception as e:
                    logger.error(f"Failed to download {video_id}: {str(e)}")
                    results.append(
                        {
                            "video_id": video_id,
                            "title": video["title"],
                            "status": "failed",
                            "error": str(e),
                        }
                    )

            # Summary
            successful = sum(1 for r in results if r["status"] == "success")
            failed = sum(1 for r in results if r["status"] == "failed")
            logger.info(
                f"\nPlaylist download complete: {successful} successful, {failed} failed"
            )

            return results

        except Exception as e:
            logger.error(f"Playlist download failed: {str(e)}")
            raise Exception(f"Playlist download failed: {str(e)}")
