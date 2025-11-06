import subprocess
import tempfile
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from moviepy import VideoFileClip, ImageClip, concatenate_videoclips

MOVIEPY_AVAILABLE = True


class VideoService:
    """
    Service for video processing operations.

    Handles video duration checking and trimming operations using FFmpeg.
    """

    def __init__(self):
        """Initialize VideoService."""
        self._check_ffmpeg_available()

    def _check_ffmpeg_available(self) -> None:
        """Check if FFmpeg is available in the system."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, check=True, timeout=10
            )
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            raise RuntimeError(
                "FFmpeg is not available. Please install FFmpeg to use video processing features."
            )

    def get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get the duration of a video file in seconds.

        Args:
            video_path: Path to the video file

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                video_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            import json

            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])

            logger.debug(f"Video duration: {duration:.2f} seconds for {video_path}")
            return duration

        except Exception as e:
            logger.error(f"Failed to get video duration for {video_path}: {e}")
            return None

    def trim_video_if_needed(self, video_path: str) -> Optional[str]:
        """
        Create a trimmed version of the video if it's longer than 3 minutes.

        If the video is longer than 3 minutes (180 seconds), creates a new version
        that is exactly 2 minutes and 57 seconds (177 seconds) using the same
        filename but with "-small" suffix.

        Args:
            video_path: Path to the original video file

        Returns:
            Path to the trimmed video file if created, or None if no trimming needed/failed
        """
        video_path = Path(video_path)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        # Get video duration
        duration = self.get_video_duration(str(video_path))
        if duration is None:
            logger.error(f"Could not determine duration for {video_path}")
            return None

        # Check if video is longer than 2:50 (170 seconds)
        if duration <= 170:
            logger.info(f"Video is {duration:.2f} seconds, no trimming needed")
            return None

        # Create output path with "-sm" suffix
        output_path = video_path.with_stem(f"{video_path.stem}-sm")

        # Check if trimmed version already exists
        if output_path.exists():
            logger.info(f"Trimmed version already exists: {output_path}")
            return str(output_path)

        logger.info(f"Video is {duration:.2f} seconds, creating trimmed version (2:50)")

        try:
            # Use FFmpeg to trim video to exactly 2 minutes 50 seconds (170 seconds)
            cmd = [
                "ffmpeg",
                "-i",
                str(video_path),
                "-t",
                "170",  # 2 minutes 50 seconds
                "-c",
                "copy",  # Copy streams without re-encoding for speed
                "-avoid_negative_ts",
                "make_zero",
                str(output_path),
            ]

            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,  # 5 minute timeout
            )

            if output_path.exists():
                output_size = output_path.stat().st_size
                logger.success(
                    f"Created trimmed video: {output_path} ({output_size} bytes)"
                )
                return str(output_path)
            else:
                logger.error("FFmpeg completed but output file not found")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed to trim video: {e.stderr}")
            return None
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out while trimming video")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while trimming video: {e}")
            return None

    def add_thumbnail_intro_moviepy(self, video_path: str, thumbnail_path: str) -> bool:
        """
        Add a thumbnail image as a 2-second intro using MoviePy (pure Python).

        Args:
            video_path: Path to the MP4 video file to modify
            thumbnail_path: Path to the thumbnail image file

        Returns:
            bool: True if successful, False otherwise
        """
        if not MOVIEPY_AVAILABLE:
            logger.error("MoviePy is not available. Install with: pip install moviepy")
            return False

        video_path = Path(video_path)
        thumbnail_path = Path(thumbnail_path)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        if not thumbnail_path.exists():
            logger.error(f"Thumbnail file not found: {thumbnail_path}")
            return False

        logger.info(f"Adding 2-second thumbnail intro using MoviePy: {video_path}")

        try:
            # Load video clip
            video_clip = VideoFileClip(str(video_path))

            # Create 2-second thumbnail clip with same size as video
            thumbnail_clip = ImageClip(str(thumbnail_path), duration=2).resized(
                video_clip.size
            )

            # Concatenate thumbnail + video
            final_clip = concatenate_videoclips([thumbnail_clip, video_clip])

            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                temp_output = Path(temp_file.name)

            # Write final video
            final_clip.write_videofile(
                str(temp_output),
                codec="libx264",
                audio_codec="aac",
                logger=None,  # Suppress MoviePy logs
            )

            # Close clips to free memory
            video_clip.close()
            thumbnail_clip.close()
            final_clip.close()

            # Replace original file
            if temp_output.exists() and temp_output.stat().st_size > 0:
                backup_path = video_path.with_suffix(".mp4.backup")
                video_path.rename(backup_path)
                temp_output.rename(video_path)
                backup_path.unlink()

                logger.success(
                    f"Successfully added thumbnail intro with MoviePy: {video_path}"
                )
                return True
            else:
                logger.error("MoviePy output file is empty or missing")
                return False

        except Exception as e:
            logger.error(f"MoviePy failed to add thumbnail intro: {e}")
            return False
        finally:
            # Cleanup temp file if it exists
            try:
                if "temp_output" in locals() and temp_output.exists():
                    temp_output.unlink()
            except:
                pass

    def add_thumbnail_intro_ffmpeg(self, video_path: str, thumbnail_path: str) -> bool:
        """
        Add a thumbnail image as a 2-second intro using FFmpeg (subprocess).

        Args:
            video_path: Path to the MP4 video file to modify
            thumbnail_path: Path to the thumbnail image file (webp, jpg, png, etc.)

        Returns:
            bool: True if successful, False otherwise
        """
        video_path = Path(video_path)
        thumbnail_path = Path(thumbnail_path)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return False

        if not thumbnail_path.exists():
            logger.error(f"Thumbnail file not found: {thumbnail_path}")
            return False

        logger.info(f"Adding 2-second thumbnail intro to video: {video_path}")

        try:
            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                temp_output = Path(temp_file.name)

            # Create thumbnail video then concatenate
            logger.debug("Creating thumbnail video segment...")

            # Step 1: Create 2-second video from thumbnail
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as thumb_temp:
                thumb_video_path = Path(thumb_temp.name)

            thumb_cmd = [
                "ffmpeg",
                "-loop",
                "1",
                "-i",
                str(thumbnail_path),
                "-t",
                "2",  # 2 seconds duration
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,fps=30",  # Ensure even dimensions and 30fps
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",  # No audio for thumbnail segment
                str(thumb_video_path),
            ]

            subprocess.run(
                thumb_cmd, capture_output=True, text=True, check=True, timeout=60
            )

            logger.debug(f"Created thumbnail video: {thumb_video_path}")

            # Step 2: Concatenate thumbnail video with original video
            logger.debug("Concatenating thumbnail with original video...")

            # Create concat file list
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as concat_file:
                concat_file.write(f"file '{thumb_video_path}'\n")
                concat_file.write(f"file '{video_path}'\n")
                concat_file_path = Path(concat_file.name)

            concat_cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file_path),
                "-c",
                "copy",  # Copy streams without re-encoding
                str(temp_output),
            ]

            subprocess.run(
                concat_cmd, capture_output=True, text=True, check=True, timeout=300
            )

            # Step 3: Replace original file with the new one
            if temp_output.exists() and temp_output.stat().st_size > 0:
                # Backup original (optional safety measure)
                backup_path = video_path.with_suffix(".mp4.backup")
                video_path.rename(backup_path)

                # Move temp file to original location
                temp_output.rename(video_path)

                # Remove backup
                backup_path.unlink()

                logger.success(f"Successfully added thumbnail intro to {video_path}")

                # Cleanup temporary files
                try:
                    thumb_video_path.unlink()
                    concat_file_path.unlink()
                except:
                    pass

                return True
            else:
                logger.error("FFmpeg completed but output file is empty or missing")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed to add thumbnail intro: {e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out while adding thumbnail intro")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while adding thumbnail intro: {e}")
            return False
        finally:
            # Cleanup any remaining temporary files
            try:
                if "temp_output" in locals() and temp_output.exists():
                    temp_output.unlink()
                if "thumb_video_path" in locals() and thumb_video_path.exists():
                    thumb_video_path.unlink()
                if "concat_file_path" in locals() and concat_file_path.exists():
                    concat_file_path.unlink()
            except:
                pass

    def add_thumbnail_intro(
        self, video_path: str, thumbnail_path: str, use_moviepy: bool = True
    ) -> bool:
        """
        Add a thumbnail image as a 2-second intro to the beginning of the video.

        Args:
            video_path: Path to the MP4 video file to modify
            thumbnail_path: Path to the thumbnail image file
            use_moviepy: If True, use MoviePy (default). If False, use FFmpeg.

        Returns:
            bool: True if successful, False otherwise
        """
        if use_moviepy:
            return self.add_thumbnail_intro_moviepy(video_path, thumbnail_path)
        else:
            return self.add_thumbnail_intro_ffmpeg(video_path, thumbnail_path)

    def prepare_video(self, video_path: str, thumbnail_path: str) -> Optional[str]:
        """
        Simple video preparation: trim if needed, then add thumbnail, save as -sm.mp4.

        Logic:
        - If video > 2:50 → Trim to 2:50 → Add 2s thumbnail → Save as {filename}-sm.mp4
        - If video ≤ 2:50 → Add 2s thumbnail → Save as {filename}-sm.mp4

        Args:
            video_path: Path to the MP4 video file
            thumbnail_path: Path to the thumbnail image file

        Returns:
            str: Path to the prepared video file ({filename}-sm.mp4)
        """
        video_path = Path(video_path)
        output_path = video_path.with_stem(f"{video_path.stem}-sm")

        # Check if already exists
        if output_path.exists():
            logger.info(f"Prepared video already exists: {output_path}")
            return str(output_path)

        logger.info(f"Preparing video: {video_path}")

        try:
            duration = self.get_video_duration(str(video_path))
            if duration is None:
                return None

            # Determine source video for thumbnail addition
            if duration > 170:  # 2:50 seconds
                logger.info("Video > 2:50, trimming first")
                source_video = self.trim_video_if_needed(str(video_path))
                if not source_video:
                    return None
            else:
                logger.info("Video ≤ 2:50, using original")
                # Copy original to temp location for processing
                import shutil

                with tempfile.NamedTemporaryFile(
                    suffix=".mp4", delete=False
                ) as temp_file:
                    source_video = temp_file.name
                shutil.copy2(video_path, source_video)

            # Add thumbnail to source video
            if not self.add_thumbnail_intro(source_video, thumbnail_path):
                return None

            # Move to final location
            Path(source_video).rename(output_path)
            logger.success(f"Created: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Video preparation failed: {e}")
            return None

    def download_thumbnail(
        self, video_metadata: Dict[str, Any], video_id: str, output_path: str
    ) -> Optional[str]:
        """
        Extract high-resolution thumbnail URL from metadata and download it.

        Args:
            video_metadata: Video metadata containing thumbnail information
            video_id: Video ID for logging purposes
            output_path: Path where thumbnail should be saved (e.g., "/tmp/videoid.webp")

        Returns:
            str: Path to downloaded thumbnail file, or None if failed
        """
        try:
            logger.info(f"Extracting thumbnail URL for video {video_id}...")
            thumbnails = video_metadata.get("thumbnails", [])

            if not thumbnails:
                logger.error("No thumbnails found in video metadata")
                return None

            # Find the highest resolution thumbnail (maxresdefault.webp)
            high_res_thumbnail = None
            for thumbnail in thumbnails:
                if "maxresdefault" in thumbnail.get("url", ""):
                    high_res_thumbnail = thumbnail
                    break

            if not high_res_thumbnail:
                # Fallback to largest available thumbnail
                high_res_thumbnail = max(
                    thumbnails, key=lambda x: x.get("width", 0) * x.get("height", 0)
                )

            thumbnail_url = high_res_thumbnail["url"]
            width = high_res_thumbnail.get("width", "unknown")
            height = high_res_thumbnail.get("height", "unknown")

            logger.success(f"Found thumbnail: {thumbnail_url} ({width}x{height})")

            # Download thumbnail
            logger.info("Downloading thumbnail...")
            response = requests.get(thumbnail_url)
            response.raise_for_status()

            # Save thumbnail to specified path
            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.success(
                f"Downloaded thumbnail to {output_path} ({len(response.content)} bytes)"
            )

            return output_path

        except requests.RequestException as e:
            logger.error(
                f"Failed to download thumbnail from {thumbnail_url}: {type(e).__name__}: {e}"
            )
            return None
        except Exception as e:
            logger.error(
                f"Error processing thumbnail for video {video_id}: {type(e).__name__}: {e}"
            )
            return None
