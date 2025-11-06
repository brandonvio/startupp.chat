#!/usr/bin/env python3
"""
MinIO MP4 to WAV and Transcription Processor Script

This script downloads an MP4 file from MinIO, converts it to WAV format using ffmpeg,
transcribes the WAV file to TXT using Whisper, generates an analysis using Ollama,
and uploads the WAV, TXT, and analysis files back to MinIO.

Usage:
    python test_minio.py "folder/path/video.mp4"

Process Flow:
    1. Download MP4 from MinIO
    2. Convert MP4 to WAV (16kHz, mono, PCM 16-bit)
    3. Upload WAV back to MinIO
    4. Transcribe WAV to TXT using Whisper
    5. Upload TXT back to MinIO
    6. Generate analysis of transcription using Ollama
    7. Upload analysis TXT back to MinIO
    8. Generate LinkedIn post from transcription using Ollama
    9. Upload LinkedIn post TXT back to MinIO

Output Files:
    - original.mp4 → original.wav (audio conversion)
    - original.mp4 → original.txt (transcription)
    - original.mp4 → original-analysis.txt (AI analysis)
    - original.mp4 → original-linkedin.txt (LinkedIn post)

Environment Variables (loaded from .env file or system environment):
    MINIO_ENDPOINT - MinIO server endpoint (e.g., 'localhost:9000')
    MINIO_ACCESS_KEY - Access key for authentication
    MINIO_SECRET_KEY - Secret key for authentication
    MINIO_BUCKET - Bucket name to use
    MINIO_SECURE - Whether to use HTTPS (default: True, set to 'false' for HTTP)
    MINIO_REGION - Optional region name
"""

import os
import sys
import tempfile
import argparse
import asyncio
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from services.minio_service import MinIOService
from services.audio_service import AudioService
from services.transcription_service import TranscriptionService
from services.analysis_service import OllamaAnalysisService


def get_minio_config() -> dict:
    """
    Load MinIO configuration from environment variables.

    First loads from .env file if it exists, then checks environment variables.

    Returns:
        dict: MinIO configuration parameters

    Raises:
        ValueError: If required environment variables are missing
    """
    # Load environment variables from .env file if it exists
    env_file_loaded = load_dotenv()
    if env_file_loaded:
        logger.info("Loaded environment variables from .env file")
    else:
        logger.info("No .env file found, using system environment variables")

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

    # Get optional variables with defaults
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


def parse_minio_path(minio_path: str) -> tuple[str, str]:
    """
    Parse MinIO path into folder and filename components.

    Args:
        minio_path (str): Full path to the file in MinIO (e.g., "folder/subfolder/video.mp4")

    Returns:
        tuple[str, str]: (folder_path, filename)
    """
    path = Path(minio_path)

    # If there's no parent directory, use empty string as folder
    if str(path.parent) == "." or path.parent == Path("."):
        folder = ""
    else:
        folder = str(path.parent)

    filename = path.name

    return folder, filename


def check_files_exist(
    minio_service: MinIOService, folder: str, base_filename: str
) -> dict:
    """
    Check which output files already exist in MinIO.

    Args:
        minio_service (MinIOService): Initialized MinIO service
        folder (str): Folder path in MinIO
        base_filename (str): Base filename without extension (e.g., "video")

    Returns:
        dict: Dictionary with existence status for each file type
    """
    files_to_check = {
        "wav": f"{base_filename}.wav",
        "txt": f"{base_filename}.txt",
        "analysis": f"{base_filename}-analysis.txt",
        "linkedin": f"{base_filename}-linkedin.txt",
    }

    existence_status = {}

    for file_type, filename in files_to_check.items():
        exists = minio_service.object_exists(folder, filename)
        existence_status[file_type] = exists
        full_path = f"{folder}/{filename}" if folder else filename

        if exists:
            logger.info(f"✓ {file_type.upper()} file already exists: {full_path}")
        else:
            logger.info(f"✗ {file_type.upper()} file missing: {full_path}")

    return existence_status


async def convert_mp4_to_wav_and_transcribe(
    minio_service: MinIOService, minio_path: str, force: bool = False
) -> bool:
    """
    Download MP4 from MinIO, convert to WAV, transcribe to TXT, generate analysis and LinkedIn post, and upload all back to MinIO.

    Args:
        minio_service (MinIOService): Initialized MinIO service
        minio_path (str): Path to the MP4 file in MinIO
        force (bool): If True, skip file existence checks and regenerate all files

    Returns:
        bool: True if successful, False otherwise
    """
    folder, mp4_filename = parse_minio_path(minio_path)

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

    logger.info(f"Processing: {minio_path}")
    logger.info(f"Folder: '{folder}', Base: {base_filename}")
    logger.info(
        f"Output files: {wav_filename}, {txt_filename}, {analysis_filename}, {linkedin_filename}"
    )

    # Check which files already exist (unless force is True)
    if not force:
        logger.info("Checking which output files already exist...")
        file_status = check_files_exist(minio_service, folder, base_filename)

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
        file_status = {"wav": False, "txt": False, "analysis": False, "linkedin": False}

    # Check if MP4 file exists in MinIO
    full_object_path = f"{folder}/{mp4_filename}" if folder else mp4_filename
    logger.info("Checking if file exists in MinIO...")
    logger.info(f"  Bucket: {minio_service.bucket_name}")
    logger.info(f"  Full object path: {full_object_path}")
    logger.info(f"  Folder: '{folder}'")
    logger.info(f"  Filename: '{mp4_filename}'")

    if not minio_service.object_exists(folder, mp4_filename):
        logger.error("MP4 file not found in MinIO!")
        logger.error(f"  Searched for: {full_object_path}")
        logger.error(f"  In bucket: {minio_service.bucket_name}")
        logger.error(f"  Using folder: '{folder}' and filename: '{mp4_filename}'")

        # List objects in the folder to help debug
        logger.info("Listing objects in the folder for debugging...")
        try:
            objects = minio_service.list_objects(folder, recursive=False)
            if objects:
                logger.info(f"Found {len(objects)} objects in folder '{folder}':")
                for obj in objects[:10]:  # Show first 10 objects
                    logger.info(f"  - {obj}")
                if len(objects) > 10:
                    logger.info(f"  ... and {len(objects) - 10} more objects")
            else:
                logger.info(f"No objects found in folder '{folder}'")
        except Exception as e:
            logger.warning(f"Could not list objects in folder: {str(e)}")

        return False

    logger.success(f"MP4 file found in MinIO: {full_object_path}")

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_mp4_path = os.path.join(temp_dir, mp4_filename)
        temp_wav_path = os.path.join(temp_dir, wav_filename)

        try:
            # Step 1: Download MP4 from MinIO (always needed for processing)
            logger.info("Downloading MP4 from MinIO...")
            logger.info(f"  Source: {full_object_path}")
            logger.info(f"  Destination: {temp_mp4_path}")
            logger.info(f"  Bucket: {minio_service.bucket_name}")

            if not minio_service.retrieve_to_file(folder, mp4_filename, temp_mp4_path):
                logger.error("Failed to download MP4 file from MinIO!")
                logger.error(f"  Attempted to download: {full_object_path}")
                logger.error(f"  From bucket: {minio_service.bucket_name}")
                logger.error(f"  To local path: {temp_mp4_path}")
                return False

            logger.success(f"Downloaded MP4 to temporary file: {temp_mp4_path}")

            # Step 2: Convert MP4 to WAV using AudioService (if needed)
            if not file_status["wav"]:
                logger.info("Converting MP4 to WAV...")
                audio_service = AudioService(sample_rate=16000, channels=1)

                try:
                    converted_wav_path = audio_service.extract_audio(
                        temp_mp4_path, temp_wav_path
                    )
                    logger.success(f"Audio conversion completed: {converted_wav_path}")
                except Exception as e:
                    logger.error(f"Audio conversion failed: {str(e)}")
                    return False

                # Step 3: Upload WAV file back to MinIO
                wav_full_path = f"{folder}/{wav_filename}" if folder else wav_filename
                logger.info("Uploading WAV file to MinIO...")
                logger.info(f"  Source: {temp_wav_path}")
                logger.info(f"  Destination: {wav_full_path}")
                logger.info(f"  Bucket: {minio_service.bucket_name}")

                # Get file size for metadata
                wav_size = os.path.getsize(temp_wav_path)
                metadata = {
                    "source_file": mp4_filename,
                    "conversion_tool": "ffmpeg",
                    "audio_format": "wav",
                    "sample_rate": "16000",
                    "channels": "1",
                }

                if not minio_service.save_file(
                    file_path=temp_wav_path,
                    folder=folder,
                    filename=wav_filename,
                    metadata=metadata,
                ):
                    logger.error("Failed to upload WAV file to MinIO!")
                    logger.error(f"  Attempted to upload to: {wav_full_path}")
                    logger.error(f"  In bucket: {minio_service.bucket_name}")
                    logger.error(f"  From local path: {temp_wav_path}")
                    return False

                logger.success("WAV file uploaded successfully!")
                logger.success(f"  Uploaded to: {wav_full_path}")
                logger.success(f"  In bucket: {minio_service.bucket_name}")
                logger.info(f"  File size: {wav_size:,} bytes")

                # Log the final result
                wav_info = minio_service.get_object_info(folder, wav_filename)
                if wav_info:
                    logger.info(f"MinIO object info: {wav_info}")
            else:
                logger.info("Skipping WAV conversion - file already exists")
                # Still need WAV file for transcription, so download it if needed for later steps
                if (
                    not file_status["txt"]
                    or not file_status["analysis"]
                    or not file_status["linkedin"]
                ):
                    logger.info("Downloading existing WAV file for transcription...")
                    if not minio_service.retrieve_to_file(
                        folder, wav_filename, temp_wav_path
                    ):
                        logger.error(
                            "Failed to download existing WAV file for transcription"
                        )
                        return False

            # Step 4: Transcribe WAV file to TXT (if needed)
            txt_full_path = f"{folder}/{txt_filename}" if folder else txt_filename

            if not file_status["txt"]:
                logger.info("Starting transcription of WAV file...")
                logger.info(f"  Source WAV: {temp_wav_path}")
                logger.info(f"  Output TXT will be uploaded to: {txt_full_path}")

                try:
                    # Initialize transcription service
                    transcription_service = TranscriptionService(
                        default_model_size="medium",
                        device="cuda",
                        compute_type="float16",
                        beam_size=5,
                    )

                    # Generate video ID from filename for transcription
                    video_id = base_filename

                    # Transcribe the WAV file (this creates a local TXT file)
                    transcription_output_path = transcription_service.transcribe_file(
                        file_path=temp_wav_path, video_id=video_id
                    )

                    logger.success(
                        f"Transcription completed: {transcription_output_path}"
                    )

                    # Step 5: Upload TXT file to MinIO
                    logger.info("Uploading TXT file to MinIO...")
                    logger.info(f"  Source: {transcription_output_path}")
                    logger.info(f"  Destination: {txt_full_path}")
                    logger.info(f"  Bucket: {minio_service.bucket_name}")

                    # Get transcription file size for metadata
                    txt_size = os.path.getsize(transcription_output_path)
                    txt_metadata = {
                        "source_file": wav_filename,
                        "original_source": mp4_filename,
                        "transcription_tool": "whisper",
                        "model_size": "medium",
                        "content_type": "text/plain",
                    }

                    # Read the TXT file content and upload with proper content type
                    with open(transcription_output_path, "rb") as txt_file:
                        txt_data = txt_file.read()

                    # Create the full object name for the TXT file
                    txt_object_name = (
                        f"{folder}/{txt_filename}" if folder else txt_filename
                    )

                    # Upload TXT file with proper content type
                    success = minio_service.save(
                        data=txt_data,
                        filename=txt_object_name,
                        content_type="text/plain",
                        metadata=txt_metadata,
                    )

                    if not success:
                        logger.error("Failed to upload TXT file to MinIO!")
                        logger.error(f"  Attempted to upload to: {txt_full_path}")
                        logger.error(f"  In bucket: {minio_service.bucket_name}")
                        logger.error(f"  From local path: {transcription_output_path}")
                        return False

                    logger.success("TXT file uploaded successfully!")
                    logger.success(f"  Uploaded to: {txt_full_path}")
                    logger.success(f"  In bucket: {minio_service.bucket_name}")
                    logger.info(f"  File size: {txt_size:,} bytes")

                    # Log the final transcription result
                    txt_info = minio_service.get_object_info(folder, txt_filename)
                    if txt_info:
                        logger.info(f"MinIO TXT object info: {txt_info}")

                except Exception as e:
                    logger.error(f"Transcription failed: {str(e)}")
                    return False
            else:
                logger.info("Skipping transcription - file already exists")
                # Download existing transcription for analysis and LinkedIn post generation
                if not file_status["analysis"] or not file_status["linkedin"]:
                    transcription_output_path = os.path.join(temp_dir, txt_filename)
                    logger.info(
                        "Downloading existing transcription file for analysis..."
                    )
                    if not minio_service.retrieve_to_file(
                        folder, txt_filename, transcription_output_path
                    ):
                        logger.error("Failed to download existing transcription file")
                        return False

            # Step 6: Generate analysis of transcription using Ollama (if needed)
            analysis_full_path = (
                f"{folder}/{analysis_filename}" if folder else analysis_filename
            )

            if not file_status["analysis"]:
                logger.info("Starting analysis of transcription...")
                logger.info(f"  Source transcription: {transcription_output_path}")
                logger.info(
                    f"  Output analysis will be uploaded to: {analysis_full_path}"
                )

                try:
                    # Initialize analysis service
                    analysis_service = OllamaAnalysisService(
                        ollama_url="http://nvda:30434",
                        model_name="gpt-oss:20b",
                        temperature=0.7,
                        max_tokens=200000,
                    )

                    # Generate analysis (this creates a local analysis file)
                    analysis_output_path = await analysis_service.analyze_transcription(
                        transcription_file=transcription_output_path,
                        video_id=base_filename,
                    )

                    logger.success(f"Analysis completed: {analysis_output_path}")

                    # Step 7: Upload analysis TXT file to MinIO
                    logger.info("Uploading analysis file to MinIO...")
                    logger.info(f"  Source: {analysis_output_path}")
                    logger.info(f"  Destination: {analysis_full_path}")
                    logger.info(f"  Bucket: {minio_service.bucket_name}")

                    # Read the analysis file content and upload with proper content type
                    with open(analysis_output_path, "rb") as analysis_file:
                        analysis_data = analysis_file.read()

                    # Create the full object name for the analysis file
                    analysis_object_name = (
                        f"{folder}/{analysis_filename}" if folder else analysis_filename
                    )

                    # Get analysis file size for metadata
                    analysis_size = os.path.getsize(analysis_output_path)
                    analysis_metadata = {
                        "source_file": txt_filename,
                        "original_source": mp4_filename,
                        "analysis_tool": "ollama",
                        "model_name": "gpt-oss:20b",
                        "content_type": "text/plain",
                    }

                    # Upload analysis file with proper content type
                    success = minio_service.save(
                        data=analysis_data,
                        filename=analysis_object_name,
                        content_type="text/plain",
                        metadata=analysis_metadata,
                    )

                    if not success:
                        logger.error("Failed to upload analysis file to MinIO!")
                        logger.error(f"  Attempted to upload to: {analysis_full_path}")
                        logger.error(f"  In bucket: {minio_service.bucket_name}")
                        logger.error(f"  From local path: {analysis_output_path}")
                        return False

                    logger.success("Analysis file uploaded successfully!")
                    logger.success(f"  Uploaded to: {analysis_full_path}")
                    logger.success(f"  In bucket: {minio_service.bucket_name}")
                    logger.info(f"  File size: {analysis_size:,} bytes")

                    # Log the final analysis result
                    analysis_info = minio_service.get_object_info(
                        folder, analysis_filename
                    )
                    if analysis_info:
                        logger.info(f"MinIO analysis object info: {analysis_info}")

                except Exception as e:
                    logger.error(f"Analysis generation failed: {str(e)}")
                    return False
            else:
                logger.info("Skipping analysis generation - file already exists")

            # Step 8: Generate LinkedIn post from transcription using Ollama (if needed)
            linkedin_full_path = (
                f"{folder}/{linkedin_filename}" if folder else linkedin_filename
            )

            if not file_status["linkedin"]:
                logger.info("Starting LinkedIn post generation...")
                logger.info(f"  Source transcription: {transcription_output_path}")
                logger.info(
                    f"  Output LinkedIn post will be uploaded to: {linkedin_full_path}"
                )

                try:
                    # Initialize analysis service (reuse the same service for LinkedIn post)
                    if "analysis_service" not in locals():
                        analysis_service = OllamaAnalysisService(
                            ollama_url="http://nvda:30434",
                            model_name="gpt-oss:20b",
                            temperature=0.7,
                            max_tokens=200000,
                        )

                    # Generate LinkedIn post (this creates a local LinkedIn post file)
                    linkedin_output_path = (
                        await analysis_service.generate_linkedin_post(
                            transcription_file=transcription_output_path,
                            video_id=base_filename,
                        )
                    )

                    logger.success(
                        f"LinkedIn post generation completed: {linkedin_output_path}"
                    )

                    # Step 9: Upload LinkedIn post TXT file to MinIO
                    logger.info("Uploading LinkedIn post file to MinIO...")
                    logger.info(f"  Source: {linkedin_output_path}")
                    logger.info(f"  Destination: {linkedin_full_path}")
                    logger.info(f"  Bucket: {minio_service.bucket_name}")

                    # Read the LinkedIn post file content and upload with proper content type
                    with open(linkedin_output_path, "rb") as linkedin_file:
                        linkedin_data = linkedin_file.read()

                    # Create the full object name for the LinkedIn post file
                    linkedin_object_name = (
                        f"{folder}/{linkedin_filename}" if folder else linkedin_filename
                    )

                    # Get LinkedIn post file size for metadata
                    linkedin_size = os.path.getsize(linkedin_output_path)
                    linkedin_metadata = {
                        "source_file": txt_filename,
                        "original_source": mp4_filename,
                        "generation_tool": "ollama",
                        "model_name": "gpt-oss:20b",
                        "content_type": "text/plain",
                        "post_type": "linkedin",
                    }

                    # Upload LinkedIn post file with proper content type
                    success = minio_service.save(
                        data=linkedin_data,
                        filename=linkedin_object_name,
                        content_type="text/plain",
                        metadata=linkedin_metadata,
                    )

                    if not success:
                        logger.error("Failed to upload LinkedIn post file to MinIO!")
                        logger.error(f"  Attempted to upload to: {linkedin_full_path}")
                        logger.error(f"  In bucket: {minio_service.bucket_name}")
                        logger.error(f"  From local path: {linkedin_output_path}")
                        return False

                    logger.success("LinkedIn post file uploaded successfully!")
                    logger.success(f"  Uploaded to: {linkedin_full_path}")
                    logger.success(f"  In bucket: {minio_service.bucket_name}")
                    logger.info(f"  File size: {linkedin_size:,} bytes")

                    # Log the final LinkedIn post result
                    linkedin_info = minio_service.get_object_info(
                        folder, linkedin_filename
                    )
                    if linkedin_info:
                        logger.info(f"MinIO LinkedIn post object info: {linkedin_info}")

                except Exception as e:
                    logger.error(f"LinkedIn post generation failed: {str(e)}")
                    return False
            else:
                logger.info("Skipping LinkedIn post generation - file already exists")

            return True

        except Exception as e:
            logger.error(f"Unexpected error during conversion process: {str(e)}")
            return False


async def main():
    """Main function to handle command line arguments and orchestrate the conversion."""
    parser = argparse.ArgumentParser(
        description="Download MP4 from MinIO, convert to WAV, transcribe to TXT, generate analysis, and upload all back",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_minio.py "videos/my-video.mp4"
    python test_minio.py "folder/subfolder/video.mp4"
    python test_minio.py "3MZS5gNElZM.mp4"

Process:
    1. Downloads MP4 from MinIO
    2. Converts to WAV (16kHz, mono)
    3. Transcribes WAV to TXT using Whisper
    4. Generates analysis of transcription using Ollama
    5. Generates LinkedIn post from transcription using Ollama
    6. Uploads WAV, TXT, analysis, and LinkedIn post back to MinIO
    
File Existence Checking:
    - By default, skips processing if output files already exist
    - Use --force flag to regenerate all files regardless

Environment Variables (from .env file or system):
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
    
Optional Environment Variables:
    MINIO_SECURE=true/false (default: true)
    MINIO_REGION=us-east-1 (optional)
    
Create a .env file in the project root with these variables.
        """,
    )

    parser.add_argument(
        "minio_path", help='Path to the MP4 file in MinIO (e.g., "folder/video.mp4")'
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
        # Load MinIO configuration
        logger.info("Loading MinIO configuration from environment variables...")
        minio_config = get_minio_config()
        logger.info(f"MinIO endpoint: {minio_config['endpoint']}")
        logger.info(f"MinIO bucket: {minio_config['bucket_name']}")
        logger.info(f"MinIO secure: {minio_config['secure']}")

        # Initialize MinIO service
        logger.info("Initializing MinIO service...")
        minio_service = MinIOService(**minio_config)
        logger.success("MinIO service initialized successfully")

        # Perform the conversion, transcription, analysis, and LinkedIn post generation
        logger.info(
            f"Starting MP4 processing (WAV, transcription, analysis, LinkedIn post) for: {args.minio_path}"
        )
        success = await convert_mp4_to_wav_and_transcribe(
            minio_service, args.minio_path, force=args.force
        )

        if success:
            logger.success(
                "MP4 processing completed successfully! (WAV, transcription, analysis, LinkedIn post)"
            )
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
