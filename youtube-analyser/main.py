#!/usr/bin/env python3
"""
MinIO MP4 to WAV and Transcription Processor Script

This script downloads an MP4 file from MinIO, converts it to WAV format using ffmpeg,
transcribes the WAV file to TXT using Whisper, generates an analysis using Ollama,
and uploads the WAV, TXT, and analysis files back to MinIO.

Usage:
    python main.py "folder/path/video.mp4"
    python main.py --playlist "playlist.json"

Process Flow:
    1. Download MP4 from MinIO
    2. Convert MP4 to WAV (16kHz, mono, PCM 16-bit)
    3. Upload WAV back to MinIO
    4. Transcribe WAV to TXT using Whisper
    5. Upload TXT back to MinIO
    6. Download and upload thumbnail as {videoid}.webp to MinIO
    7. Generate small video with thumbnail intro as {videoid}-sm.mp4 and upload to MinIO
    8. Generate analysis of transcription using Ollama
    9. Upload analysis TXT back to MinIO
    10. Generate LinkedIn post from transcription using Ollama
    11. Upload LinkedIn post TXT back to MinIO
    12. Generate Bluesky post from transcription using Ollama
    13. Upload Bluesky post TXT back to MinIO
    14. Post to Bluesky

Output Files:
    - original.mp4 → original.wav (audio conversion)
    - original.mp4 → original.txt (transcription)
    - original.mp4 → original.webp (thumbnail image)
    - original.mp4 → original-sm.mp4 (small video with thumbnail intro)
    - original.mp4 → original-analysis.txt (AI analysis)
    - original.mp4 → original-linkedin.txt (LinkedIn post)
    - original.mp4 → original-bluesky.txt (Bluesky post)

Environment Variables (loaded from .env file or system environment):
    MINIO_ENDPOINT - MinIO server endpoint (e.g., 'localhost:9000')
    MINIO_ACCESS_KEY - Access key for authentication
    MINIO_SECRET_KEY - Secret key for authentication
    MINIO_BUCKET - Bucket name to use
    MINIO_SECURE - Whether to use HTTPS (default: True, set to 'false' for HTTP)
    MINIO_REGION - Optional region name
    BLUESKY_HANDLE - Bluesky handle for posting
    BLUESKY_PASSWORD - Bluesky app password for posting
"""

import os
import sys
import tempfile
import argparse
import asyncio
import json
from pathlib import Path
from loguru import logger
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from services.minio_service import MinIOService
from services.audio_service import AudioService
from services.video_service import VideoService
from services.transcription_service import (
    TranscriptionService,
    PersonaTranscriptionService,
)
from services.analysis_service import OllamaAnalysisService
from services.bluesky_service import BlueskyService
from services.bluesky_post_builder import BlueskyPostBuilder


class VideoProcessor:
    """Main video processing service that coordinates all sub-services."""

    def __init__(
        self,
        minio_service: MinIOService,
        audio_service: AudioService,
        video_service: VideoService,
        transcription_service: TranscriptionService,
        analysis_service: OllamaAnalysisService,
        bluesky_builder: BlueskyPostBuilder,
    ):
        self.minio = minio_service
        self.audio = audio_service
        self.video = video_service
        self.transcription = transcription_service
        self.analysis = analysis_service
        self.bluesky = bluesky_builder

    def check_files_exist(self, folder: str, base_filename: str) -> Dict[str, bool]:
        """Check which output files already exist in MinIO."""
        files_to_check = {
            "wav": f"{base_filename}.wav",
            "txt": f"{base_filename}.txt",
            "analysis": f"{base_filename}-analysis.txt",
            "linkedin": f"{base_filename}-linkedin.txt",
            "bluesky": f"{base_filename}-bluesky.txt",
            "json": f"{base_filename}.json",
            "thumbnail": f"{base_filename}.webp",
            "small_video": f"{base_filename}-sm.mp4",
        }

        existence_status = {}
        for file_type, filename in files_to_check.items():
            exists = self.minio.object_exists(folder, filename)
            existence_status[file_type] = exists
            full_path = f"{folder}/{filename}" if folder else filename

            if exists:
                logger.info(f"✓ {file_type.upper()} file already exists: {full_path}")
            else:
                logger.info(f"✗ {file_type.upper()} file missing: {full_path}")

        return existence_status

    async def convert_audio(
        self,
        temp_mp4_path: str,
        temp_wav_path: str,
        folder: str,
        wav_filename: str,
        mp4_filename: str,
    ) -> bool:
        """Convert MP4 to WAV and upload to MinIO."""
        logger.info("Converting MP4 to WAV...")

        try:
            converted_wav_path = self.audio.extract_audio(temp_mp4_path, temp_wav_path)
            logger.success(f"Audio conversion completed: {converted_wav_path}")
        except Exception as e:
            logger.error(f"Audio conversion failed: {str(e)}")
            return False

        # Upload WAV file to MinIO
        wav_full_path = f"{folder}/{wav_filename}" if folder else wav_filename
        logger.info(f"Uploading WAV file to MinIO: {wav_full_path}")

        wav_size = os.path.getsize(temp_wav_path)
        metadata = {
            "source_file": mp4_filename,
            "conversion_tool": "ffmpeg",
            "audio_format": "wav",
            "sample_rate": "16000",
            "channels": "1",
        }

        success = self.minio.save_file(
            file_path=temp_wav_path,
            folder=folder,
            filename=wav_filename,
            metadata=metadata,
        )

        if success:
            logger.success(
                f"WAV file uploaded successfully to {wav_full_path} ({wav_size:,} bytes)"
            )
        else:
            logger.error(f"Failed to upload WAV file to MinIO")

        return success

    async def transcribe_audio(
        self,
        temp_wav_path: str,
        folder: str,
        txt_filename: str,
        base_filename: str,
        wav_filename: str,
        mp4_filename: str,
    ) -> Optional[str]:
        """Transcribe WAV file and upload to MinIO."""
        logger.info("Starting transcription of WAV file...")

        try:
            transcription_output_path = self.transcription.transcribe_file(
                file_path=temp_wav_path, video_id=base_filename
            )
            logger.success(f"Transcription completed: {transcription_output_path}")
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return None

        # Upload TXT file to MinIO
        txt_full_path = f"{folder}/{txt_filename}" if folder else txt_filename
        logger.info(f"Uploading TXT file to MinIO: {txt_full_path}")

        with open(transcription_output_path, "rb") as txt_file:
            txt_data = txt_file.read()

        txt_size = os.path.getsize(transcription_output_path)
        txt_metadata = {
            "source_file": wav_filename,
            "original_source": mp4_filename,
            "transcription_tool": "whisper",
            "model_size": "medium",
            "content_type": "text/plain",
        }

        txt_object_name = f"{folder}/{txt_filename}" if folder else txt_filename
        success = self.minio.save(
            data=txt_data,
            filename=txt_object_name,
            content_type="text/plain",
            metadata=txt_metadata,
        )

        if success:
            logger.success(
                f"TXT file uploaded successfully to {txt_full_path} ({txt_size:,} bytes)"
            )
            return transcription_output_path
        else:
            logger.error(f"Failed to upload TXT file to MinIO")
            return None

    async def generate_analysis(
        self,
        transcription_path: str,
        folder: str,
        analysis_filename: str,
        base_filename: str,
        txt_filename: str,
        mp4_filename: str,
    ) -> bool:
        """Generate analysis and upload to MinIO."""
        logger.info("Starting analysis of transcription...")

        try:
            analysis_output_path = await self.analysis.analyze_transcription(
                transcription_file=transcription_path,
                video_id=base_filename,
            )
            logger.success(f"Analysis completed: {analysis_output_path}")
        except Exception as e:
            logger.error(f"Analysis generation failed: {str(e)}")
            return False

        # Upload analysis file to MinIO
        analysis_full_path = (
            f"{folder}/{analysis_filename}" if folder else analysis_filename
        )
        logger.info(f"Uploading analysis file to MinIO: {analysis_full_path}")

        with open(analysis_output_path, "rb") as analysis_file:
            analysis_data = analysis_file.read()

        analysis_size = os.path.getsize(analysis_output_path)
        analysis_metadata = {
            "source_file": txt_filename,
            "original_source": mp4_filename,
            "analysis_tool": "ollama",
            "model_name": "gpt-oss:20b",
            "content_type": "text/plain",
        }

        analysis_object_name = (
            f"{folder}/{analysis_filename}" if folder else analysis_filename
        )
        success = self.minio.save(
            data=analysis_data,
            filename=analysis_object_name,
            content_type="text/plain",
            metadata=analysis_metadata,
        )

        if success:
            logger.success(
                f"Analysis file uploaded successfully to {analysis_full_path} ({analysis_size:,} bytes)"
            )
        else:
            logger.error(f"Failed to upload analysis file to MinIO")

        return success

    async def generate_linkedin_post(
        self,
        transcription_path: str,
        folder: str,
        linkedin_filename: str,
        base_filename: str,
        txt_filename: str,
        mp4_filename: str,
    ) -> bool:
        """Generate LinkedIn post and upload to MinIO."""
        logger.info("Starting LinkedIn post generation...")

        try:
            linkedin_output_path = await self.analysis.generate_linkedin_post(
                transcription_file=transcription_path,
                video_id=base_filename,
            )
            logger.success(
                f"LinkedIn post generation completed: {linkedin_output_path}"
            )
        except Exception as e:
            logger.error(f"LinkedIn post generation failed: {str(e)}")
            return False

        # Upload LinkedIn post file to MinIO
        linkedin_full_path = (
            f"{folder}/{linkedin_filename}" if folder else linkedin_filename
        )
        logger.info(f"Uploading LinkedIn post file to MinIO: {linkedin_full_path}")

        with open(linkedin_output_path, "rb") as linkedin_file:
            linkedin_data = linkedin_file.read()

        linkedin_size = os.path.getsize(linkedin_output_path)
        linkedin_metadata = {
            "source_file": txt_filename,
            "original_source": mp4_filename,
            "generation_tool": "ollama",
            "model_name": "gpt-oss:20b",
            "content_type": "text/plain",
            "post_type": "linkedin",
        }

        linkedin_object_name = (
            f"{folder}/{linkedin_filename}" if folder else linkedin_filename
        )
        success = self.minio.save(
            data=linkedin_data,
            filename=linkedin_object_name,
            content_type="text/plain",
            metadata=linkedin_metadata,
        )

        if success:
            logger.success(
                f"LinkedIn post file uploaded successfully to {linkedin_full_path} ({linkedin_size:,} bytes)"
            )
        else:
            logger.error(f"Failed to upload LinkedIn post file to MinIO")

        return success

    async def generate_and_post_bluesky(
        self,
        transcription_path: str,
        temp_dir: str,
        folder: str,
        bluesky_filename: str,
        base_filename: str,
        txt_filename: str,
        mp4_filename: str,
        small_video_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> bool:
        """Generate Bluesky post, upload to MinIO, and post to Bluesky."""
        logger.info("Starting Bluesky post generation...")

        # Read transcription content
        with open(transcription_path, "r", encoding="utf-8") as f:
            transcription_content = f.read()

        try:
            bluesky_post_content = await self.analysis.generate_bluesky_post(
                video_id=base_filename, analysis_content=transcription_content
            )
            logger.success(
                f"Bluesky post generation completed ({len(bluesky_post_content)} characters)"
            )
            logger.info(f"Post content: {bluesky_post_content}")
        except Exception as e:
            logger.error(f"Bluesky post generation failed: {str(e)}")
            return False

        # Save Bluesky post to temporary file
        bluesky_temp_path = os.path.join(temp_dir, bluesky_filename)
        with open(bluesky_temp_path, "w", encoding="utf-8") as f:
            f.write(bluesky_post_content)

        # Upload Bluesky post file to MinIO
        bluesky_full_path = (
            f"{folder}/{bluesky_filename}" if folder else bluesky_filename
        )
        logger.info(f"Uploading Bluesky post file to MinIO: {bluesky_full_path}")

        with open(bluesky_temp_path, "rb") as bluesky_file:
            bluesky_data = bluesky_file.read()

        bluesky_size = os.path.getsize(bluesky_temp_path)
        bluesky_metadata = {
            "source_file": txt_filename,
            "original_source": mp4_filename,
            "generation_tool": "ollama",
            "model_name": "gpt-oss:20b",
            "content_type": "text/plain",
            "post_type": "bluesky",
        }

        bluesky_object_name = (
            f"{folder}/{bluesky_filename}" if folder else bluesky_filename
        )
        success = self.minio.save(
            data=bluesky_data,
            filename=bluesky_object_name,
            content_type="text/plain",
            metadata=bluesky_metadata,
        )

        if not success:
            logger.error(f"Failed to upload Bluesky post file to MinIO")
            return False

        logger.success(
            f"Bluesky post file uploaded successfully to {bluesky_full_path} ({bluesky_size:,} bytes)"
        )

        # Post to Bluesky with provided media
        logger.info("Posting to Bluesky...")
        try:
            # Use clean post content without video URLs
            post_content = bluesky_post_content

            bluesky_post_success = await self.bluesky.post_content_with_media(
                text=post_content,
                video_path=small_video_path,
                thumbnail_path=thumbnail_path,
                video_title=f"Video: {base_filename}",
                youtube_url=video_url,
                use_youtube_facets=True,  # Enable YouTube facets by default
            )
            if bluesky_post_success:
                logger.success("Successfully posted to Bluesky!")
            else:
                logger.error(
                    "Bluesky posting failed - post_content_with_media returned False"
                )
                return False
        except Exception as e:
            logger.error(
                f"Bluesky posting failed with exception: {type(e).__name__}: {e}"
            )
            return False

        return True

    async def download_and_upload_thumbnail(
        self,
        temp_dir: str,
        folder: str,
        base_filename: str,
        mp4_filename: str,
    ) -> bool:
        """Download thumbnail and upload to MinIO."""
        thumbnail_filename = f"{base_filename}.webp"
        thumbnail_full_path = (
            f"{folder}/{thumbnail_filename}" if folder else thumbnail_filename
        )

        logger.info("Starting thumbnail download...")

        # Step 1: Check if JSON metadata file exists
        json_filename = f"{base_filename}.json"
        if not self.minio.object_exists(folder, json_filename):
            logger.error(
                f"JSON metadata file not found in MinIO: {folder}/{json_filename}"
            )
            return False

        # Step 2: Retrieve JSON metadata from MinIO
        try:
            json_data = self.minio.retrieve(folder, json_filename)
            if not json_data:
                logger.error(
                    f"Failed to retrieve JSON metadata file: {folder}/{json_filename}"
                )
                return False

            video_metadata = json.loads(json_data.decode("utf-8"))
            logger.success(
                f"Retrieved video metadata: {video_metadata.get('title', 'Unknown Title')}"
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON metadata file {folder}/{json_filename}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Failed to retrieve JSON metadata file {folder}/{json_filename}: {type(e).__name__}: {e}"
            )
            return False

        # Step 3: Download thumbnail using VideoService
        temp_thumbnail_path = os.path.join(temp_dir, thumbnail_filename)
        thumbnail_path = self.video.download_thumbnail(
            video_metadata, base_filename, temp_thumbnail_path
        )

        if not thumbnail_path:
            logger.error("Failed to download thumbnail")
            return False

        # Step 4: Upload thumbnail to MinIO
        logger.info(f"Uploading thumbnail to MinIO: {thumbnail_full_path}")

        thumbnail_size = os.path.getsize(temp_thumbnail_path)
        metadata = {
            "source_file": mp4_filename,
            "content_type": "image/webp",
            "thumbnail_type": "youtube_maxres",
        }

        success = self.minio.save_file(
            file_path=temp_thumbnail_path,
            folder=folder,
            filename=thumbnail_filename,
            metadata=metadata,
        )

        if success:
            logger.success(
                f"Thumbnail uploaded successfully to {thumbnail_full_path} ({thumbnail_size:,} bytes)"
            )
        else:
            logger.error(f"Failed to upload thumbnail to MinIO")

        return success

    async def generate_and_upload_small_video(
        self,
        temp_dir: str,
        folder: str,
        base_filename: str,
        mp4_filename: str,
    ) -> Optional[str]:
        """Generate small video with thumbnail intro and upload to MinIO."""
        small_video_filename = f"{base_filename}-sm.mp4"
        small_video_full_path = (
            f"{folder}/{small_video_filename}" if folder else small_video_filename
        )

        logger.info("Starting small video generation...")

        # Step 1: Get paths for input files
        temp_mp4_path = os.path.join(temp_dir, mp4_filename)
        thumbnail_filename = f"{base_filename}.webp"
        temp_thumbnail_path = os.path.join(temp_dir, thumbnail_filename)

        # Step 2: Check if thumbnail exists (should have been downloaded already)
        if not os.path.exists(temp_thumbnail_path):
            # Download thumbnail from MinIO if not in temp directory
            if not self.minio.retrieve_to_file(
                folder, thumbnail_filename, temp_thumbnail_path
            ):
                logger.error(f"Failed to retrieve thumbnail for small video generation")
                return None

        # Step 3: Generate small video using VideoService
        temp_small_video_path = os.path.join(temp_dir, small_video_filename)
        small_video_path = self.video.prepare_video(temp_mp4_path, temp_thumbnail_path)

        if not small_video_path:
            logger.error("Failed to generate small video")
            return None

        # Step 4: Move the generated video to expected temp location
        if small_video_path != temp_small_video_path:
            os.rename(small_video_path, temp_small_video_path)

        # Step 5: Upload small video to MinIO
        logger.info(f"Uploading small video to MinIO: {small_video_full_path}")

        small_video_size = os.path.getsize(temp_small_video_path)
        metadata = {
            "source_file": mp4_filename,
            "content_type": "video/mp4",
            "video_type": "small_with_thumbnail_intro",
            "processing_tool": "ffmpeg_moviepy",
        }

        success = self.minio.save_file(
            file_path=temp_small_video_path,
            folder=folder,
            filename=small_video_filename,
            metadata=metadata,
        )

        if success:
            logger.success(
                f"Small video uploaded successfully to {small_video_full_path} ({small_video_size:,} bytes)"
            )
            return temp_small_video_path
        else:
            logger.error(f"Failed to upload small video to MinIO")
            return None

    async def process_video(self, minio_path: str, force: bool = False) -> bool:
        """Process a single video through the complete pipeline."""
        folder, mp4_filename = self.parse_minio_path(minio_path)

        # Validate file extension
        if not mp4_filename.lower().endswith(".mp4"):
            logger.error(f"File must have .mp4 extension, got: {mp4_filename}")
            return False

        # Generate output filenames
        base_filename = mp4_filename[:-4]  # Remove .mp4 extension
        wav_filename = f"{base_filename}.wav"
        txt_filename = f"{base_filename}.txt"
        analysis_filename = f"{base_filename}-analysis.txt"
        linkedin_filename = f"{base_filename}-linkedin.txt"
        bluesky_filename = f"{base_filename}-bluesky.txt"

        logger.info(f"Processing: {minio_path}")
        logger.info(f"Folder: '{folder}', Base: {base_filename}")

        # Check which files already exist (unless force is True)
        if not force:
            logger.info("Checking which output files already exist...")
            file_status = self.check_files_exist(folder, base_filename)

            # If all files exist, skip processing
            if all(file_status.values()):
                logger.success("All output files already exist. Skipping processing.")
                logger.info("Use --force flag to regenerate all files.")
                return True

            # Log what will be processed
            to_process = [
                file_type for file_type, exists in file_status.items() if not exists
            ]
            logger.info(f"Will process: {', '.join(to_process)}")
        else:
            logger.info("Force mode enabled - will regenerate all files")
            file_status = {
                "wav": False,
                "txt": False,
                "analysis": False,
                "linkedin": False,
                "bluesky": False,
                "json": False,
                "thumbnail": False,
                "small_video": False,
            }

        # Check if MP4 file exists in MinIO
        if not self.minio.object_exists(folder, mp4_filename):
            logger.error(f"MP4 file not found in MinIO: {minio_path}")
            return False

        logger.success(f"MP4 file found in MinIO: {minio_path}")

        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_mp4_path = os.path.join(temp_dir, mp4_filename)
            temp_wav_path = os.path.join(temp_dir, wav_filename)

            try:
                # Step 1: Download MP4 from MinIO
                logger.info("Downloading MP4 from MinIO...")
                if not self.minio.retrieve_to_file(folder, mp4_filename, temp_mp4_path):
                    logger.error("Failed to download MP4 file from MinIO!")
                    return False
                logger.success(f"Downloaded MP4 to temporary file: {temp_mp4_path}")

                # Step 2: Convert MP4 to WAV (if needed)
                if not file_status["wav"]:
                    if not await self.convert_audio(
                        temp_mp4_path, temp_wav_path, folder, wav_filename, mp4_filename
                    ):
                        return False
                else:
                    logger.info("Skipping WAV conversion - file already exists")
                    # Download existing WAV file if needed for subsequent steps
                    if not all(
                        [
                            file_status["txt"],
                            file_status["analysis"],
                            file_status["linkedin"],
                            file_status["bluesky"],
                        ]
                    ):
                        if not self.minio.retrieve_to_file(
                            folder, wav_filename, temp_wav_path
                        ):
                            logger.error("Failed to download existing WAV file")
                            return False

                # Step 3: Transcribe WAV to TXT (if needed)
                transcription_output_path = None
                if not file_status["txt"]:
                    transcription_output_path = await self.transcribe_audio(
                        temp_wav_path,
                        folder,
                        txt_filename,
                        base_filename,
                        wav_filename,
                        mp4_filename,
                    )
                    if not transcription_output_path:
                        return False
                else:
                    logger.info("Skipping transcription - file already exists")
                    # Download existing transcription if needed
                    if not all(
                        [
                            file_status["analysis"],
                            file_status["linkedin"],
                            file_status["bluesky"],
                        ]
                    ):
                        transcription_output_path = os.path.join(temp_dir, txt_filename)
                        if not self.minio.retrieve_to_file(
                            folder, txt_filename, transcription_output_path
                        ):
                            logger.error(
                                "Failed to download existing transcription file"
                            )
                            return False

                # Step 3.5: Download and upload thumbnail (if needed)
                if not file_status["thumbnail"]:
                    if not await self.download_and_upload_thumbnail(
                        temp_dir,
                        folder,
                        base_filename,
                        mp4_filename,
                    ):
                        return False
                else:
                    logger.info("Skipping thumbnail download - file already exists")

                # Step 3.75: Generate and upload small video (if needed)
                small_video_path = None
                # DO NOT UNCOMMENT THIS UNLESS REQUESTD!!!
                # if not file_status["small_video"]:
                #     small_video_path = await self.generate_and_upload_small_video(
                #         temp_dir,
                #         folder,
                #         base_filename,
                #         mp4_filename,
                #     )
                #     if not small_video_path:
                #         return False
                # else:
                #     logger.info("Skipping small video generation - file already exists")
                #     # Get path to existing small video
                #     small_video_filename = f"{base_filename}-sm.mp4"
                #     existing_small_video_path = os.path.join(
                #         temp_dir, small_video_filename
                #     )
                #     if self.minio.retrieve_to_file(
                #         folder, small_video_filename, existing_small_video_path
                #     ):
                #         small_video_path = existing_small_video_path

                # Step 4: Generate analysis (if needed)
                if not file_status["analysis"]:
                    if not await self.generate_analysis(
                        transcription_output_path,
                        folder,
                        analysis_filename,
                        base_filename,
                        txt_filename,
                        mp4_filename,
                    ):
                        return False
                else:
                    logger.info("Skipping analysis generation - file already exists")

                # Step 5: Generate LinkedIn post (if needed)
                if not file_status["linkedin"]:
                    if not await self.generate_linkedin_post(
                        transcription_output_path,
                        folder,
                        linkedin_filename,
                        base_filename,
                        txt_filename,
                        mp4_filename,
                    ):
                        return False
                else:
                    logger.info(
                        "Skipping LinkedIn post generation - file already exists"
                    )

                # Step 6: Generate and post to Bluesky (if needed)
                if not file_status["bluesky"] and False:
                    # Prepare paths for Bluesky posting
                    thumbnail_path = None
                    thumbnail_filename = f"{base_filename}.webp"
                    temp_thumbnail_path = os.path.join(temp_dir, thumbnail_filename)

                    if os.path.exists(temp_thumbnail_path):
                        thumbnail_path = temp_thumbnail_path
                    elif self.minio.retrieve_to_file(
                        folder, thumbnail_filename, temp_thumbnail_path
                    ):
                        thumbnail_path = temp_thumbnail_path

                    # Generate video URL (you might want to customize this)
                    video_url = f"https://youtube.com/watch?v={base_filename}"

                    if not await self.generate_and_post_bluesky(
                        transcription_output_path,
                        temp_dir,
                        folder,
                        bluesky_filename,
                        base_filename,
                        txt_filename,
                        mp4_filename,
                        small_video_path=small_video_path,
                        thumbnail_path=thumbnail_path,
                        video_url=video_url,
                    ):
                        return False
                else:
                    logger.info(
                        "Skipping Bluesky post generation and posting - file already exists"
                    )

                return True

            except Exception as e:
                logger.error(f"Unexpected error during conversion process: {str(e)}")
                return False

    @staticmethod
    def parse_minio_path(minio_path: str) -> tuple[str, str]:
        """Parse MinIO path into folder and filename components."""
        path = Path(minio_path)

        if str(path.parent) == "." or path.parent == Path("."):
            folder = ""
        else:
            folder = str(path.parent)

        filename = path.name
        return folder, filename


class PlaylistProcessor:
    """Service for processing playlists."""

    def __init__(self, minio_service: MinIOService, video_processor: VideoProcessor):
        self.minio = minio_service
        self.video_processor = video_processor

    async def load_playlist(self, playlist_name: str) -> Optional[Dict[str, Any]]:
        """Load playlist JSON from MinIO playlists folder."""
        try:
            logger.info(f"Loading playlist from MinIO: playlists/{playlist_name}")

            playlist_data = self.minio.retrieve("playlists", playlist_name)
            if not playlist_data:
                logger.error(f"Failed to load playlist: playlists/{playlist_name}")
                return None

            playlist = json.loads(playlist_data.decode("utf-8"))
            logger.success(
                f"Successfully loaded playlist with {len(playlist.get('videos', []))} videos"
            )

            return playlist

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse playlist JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading playlist: {str(e)}")
            return None

    async def process_playlist(
        self, playlist: Dict[str, Any], force: bool = False
    ) -> bool:
        """Process all videos in a playlist."""
        videos = playlist.get("videos", [])
        if not videos:
            logger.warning("No videos found in playlist")
            return True

        # Reverse the list to start with oldest videos first (bottom to top)
        videos = list(reversed(videos))

        logger.info(
            f"Processing {len(videos)} videos from playlist (starting with oldest)"
        )

        success_count = 0
        error_count = 0

        for i, video in enumerate(videos, 1):
            video_id = video.get("id")
            if not video_id:
                logger.warning(f"Video {i} has no ID, skipping")
                error_count += 1
                continue

            video_title = video.get("title", "Unknown Title")
            logger.info(f"Processing video {i}/{len(videos)}: {video_title[:50]}...")

            video_path = f"downloads/{video_id}.mp4"

            try:
                success = await self.video_processor.process_video(
                    video_path, force=force
                )

                if success:
                    success_count += 1
                    logger.success(
                        f"✓ Successfully processed video {i}/{len(videos)}: {video_id}"
                    )
                else:
                    error_count += 1
                    logger.error(
                        f"✗ Failed to process video {i}/{len(videos)}: {video_id}"
                    )

            except Exception as e:
                error_count += 1
                logger.error(
                    f"✗ Error processing video {i}/{len(videos)} ({video_id}): {str(e)}"
                )

        logger.info(
            f"Playlist processing complete: {success_count} successful, {error_count} failed"
        )
        return error_count == 0


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

    secure = os.getenv("MINIO_SECURE", "true").lower() in ("true", "1", "yes", "on")
    region = os.getenv("MINIO_REGION")

    return {
        "endpoint": os.getenv("MINIO_ENDPOINT"),
        "access_key": os.getenv("MINIO_ACCESS_KEY"),
        "secret_key": os.getenv("MINIO_SECRET_KEY"),
        "bucket_name": os.getenv("MINIO_BUCKET"),
        "secure": secure,
        "region": region,
    }


def create_services() -> tuple[VideoProcessor, PlaylistProcessor]:
    """Create and wire up all services with dependency injection."""
    # Load MinIO configuration
    logger.info("Loading MinIO configuration from environment variables...")
    minio_config = get_minio_config()
    logger.info(f"MinIO endpoint: {minio_config['endpoint']}")
    logger.info(f"MinIO bucket: {minio_config['bucket_name']}")

    # Initialize MinIO service
    logger.info("Initializing MinIO service...")
    minio_service = MinIOService(**minio_config)
    logger.success("MinIO service initialized successfully")

    # Initialize other services
    audio_service = AudioService(sample_rate=16000, channels=1)
    video_service = VideoService()
    transcription_service = PersonaTranscriptionService(
        default_model_size="medium",
        device="cuda",
        compute_type="float16",
        batch_size=16,
    )
    analysis_service = OllamaAnalysisService(
        ollama_url=os.getenv("OLLAMA_URL", "http://nvda:30434"),
        model_name=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        temperature=0.7,
        max_tokens=200000,
    )

    # Initialize Bluesky services
    bluesky_handle = os.getenv("BLUESKY_HANDLE")
    bluesky_password = os.getenv("BLUESKY_PASSWORD")
    bluesky_service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")

    if not bluesky_handle or not bluesky_password:
        logger.error(
            "Missing required Bluesky credentials (BLUESKY_HANDLE, BLUESKY_PASSWORD)"
        )
        sys.exit(1)

    try:
        bluesky_service = BlueskyService(
            handle=bluesky_handle,
            password=bluesky_password,
            service_url=bluesky_service_url,
        )

        bluesky_builder = BlueskyPostBuilder(
            bluesky_service=bluesky_service,
        )
        logger.success("Bluesky posting enabled")
    except Exception as e:
        logger.error(f"Failed to initialize Bluesky services: {e}")
        sys.exit(1)

    # Create main processors
    video_processor = VideoProcessor(
        minio_service=minio_service,
        audio_service=audio_service,
        video_service=video_service,
        transcription_service=transcription_service,
        analysis_service=analysis_service,
        bluesky_builder=bluesky_builder,
    )

    playlist_processor = PlaylistProcessor(
        minio_service=minio_service,
        video_processor=video_processor,
    )

    return video_processor, playlist_processor


async def main():
    """Main function to handle command line arguments and orchestrate the conversion."""
    parser = argparse.ArgumentParser(
        description="Download MP4 from MinIO, convert to WAV, transcribe to TXT, generate analysis, and upload all back. Supports single files or playlists.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process single video
    python main.py "videos/my-video.mp4"
    python main.py "folder/subfolder/video.mp4"
    python main.py "3MZS5gNElZM.mp4"
    
    # Process playlist
    python main.py --playlist "rl-conference.json"

Process:
    1. Downloads MP4 from MinIO
    2. Converts to WAV (16kHz, mono)
    3. Transcribes WAV to TXT using Whisper
    4. Downloads and uploads thumbnail as {videoid}.webp to MinIO
    5. Generates small video with thumbnail intro as {videoid}-sm.mp4 and uploads to MinIO
    6. Generates analysis of transcription using Ollama
    7. Generates LinkedIn post from transcription using Ollama
    8. Generates Bluesky post from transcription using Ollama
    9. Posts to Bluesky
    
File Existence Checking:
    - By default, skips processing if output files already exist
    - Use --force flag to regenerate all files regardless

Playlist Mode:
    - Use --playlist flag with playlist filename (e.g., "rl-conference.json")
    - Playlist is loaded from MinIO "playlists" folder
    - Processes all videos in the playlist from "downloads/{video_id}.mp4"

Environment Variables (from .env file or system):
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
    BLUESKY_HANDLE, BLUESKY_PASSWORD
    
Optional Environment Variables:
    MINIO_SECURE=true/false (default: true)
    MINIO_REGION=us-east-1 (optional)
    BLUESKY_SERVICE_URL=https://bsky.social (optional)
    OLLAMA_URL=http://nvda:30434 (optional)
    OLLAMA_MODEL=gpt-oss:20b (optional)
    
Create a .env file in the project root with these variables.
        """,
    )

    # Create mutually exclusive group for single file vs playlist
    input_group = parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        "minio_path",
        nargs="?",
        help='Path to the MP4 file in MinIO (e.g., "folder/video.mp4")',
    )

    input_group.add_argument(
        "--playlist",
        help='Name of playlist file in MinIO playlists folder (e.g., "rl-conference.json")',
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of all files, skipping existence checks",
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level=args.log_level,
        colorize=True,
    )

    try:
        # Initialize services
        video_processor, playlist_processor = create_services()

        # Process either single file or playlist
        if args.playlist:
            # Playlist mode
            logger.info(f"Starting playlist processing for: {args.playlist}")

            playlist = await playlist_processor.load_playlist(args.playlist)
            if not playlist:
                logger.error(f"Failed to load playlist: {args.playlist}")
                sys.exit(1)

            success = await playlist_processor.process_playlist(
                playlist, force=args.force
            )

            if success:
                logger.success("Playlist processing completed successfully!")
                sys.exit(0)
            else:
                logger.error("Playlist processing completed with errors!")
                sys.exit(1)

        else:
            # Single file mode
            logger.info(f"Starting MP4 processing for: {args.minio_path}")
            success = await video_processor.process_video(
                args.minio_path, force=args.force
            )

            if success:
                logger.success("MP4 processing completed successfully!")
                sys.exit(0)
            else:
                logger.error("MP4 processing failed!")
                sys.exit(1)

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info(
            "Please set the required environment variables. See --help for details."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
