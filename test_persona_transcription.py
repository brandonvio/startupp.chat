#!/usr/bin/env python3
"""
Test script for PersonaTranscriptionService with MinIO integration.

Downloads an MP4 file from MinIO, saves it to a temp folder, and produces
a persona-based transcription.

Usage:
    python test_persona_transcription.py "folder/path/video.mp4"
    python test_persona_transcription.py "3MZS5gNElZM.mp4"

Environment Variables (loaded from .env file or system environment):
    MINIO_ENDPOINT - MinIO server endpoint (e.g., 'localhost:9000')
    MINIO_ACCESS_KEY - Access key for authentication
    MINIO_SECRET_KEY - Secret key for authentication
    MINIO_BUCKET - Bucket name to use
    MINIO_SECURE - Whether to use HTTPS (default: True, set to 'false' for HTTP)
    MINIO_REGION - Optional region name
"""

import sys
import os
import ctypes

# Fix cuDNN library conflict - preload venv's cuDNN before torch loads system cuDNN
# This must happen before any torch imports
_cudnn_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".venv/lib/python3.10/site-packages/nvidia/cudnn/lib"
)
if os.path.exists(_cudnn_path):
    _cudnn_lib = os.path.join(_cudnn_path, "libcudnn.so.9")
    if os.path.exists(_cudnn_lib):
        ctypes.CDLL(_cudnn_lib, mode=ctypes.RTLD_GLOBAL)

import tempfile
import argparse
import traceback
import faulthandler
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# Enable faulthandler to get tracebacks on segfaults
faulthandler.enable()

from services.minio_service import MinIOService
from services.transcription_service import PersonaTranscriptionService


def setup_logging(log_level: str = "INFO"):
    """Configure logging with the specified level."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )


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


def test_persona_transcription(
    minio_service: MinIOService,
    minio_path: str,
    model_size: str = "small",
) -> bool:
    """
    Download MP4 from MinIO and perform persona transcription.

    Args:
        minio_service: Initialized MinIO service
        minio_path: Path to the MP4 file in MinIO
        model_size: Whisper model size to use (default: small)

    Returns:
        bool: True if successful, False otherwise
    """
    folder, mp4_filename = parse_minio_path(minio_path)

    # Validate file extension
    valid_extensions = (".mp4", ".mp3", ".wav", ".m4a", ".avi", ".mov")
    if not mp4_filename.lower().endswith(valid_extensions):
        logger.error(f"File must have a valid audio/video extension {valid_extensions}, got: {mp4_filename}")
        return False

    full_object_path = f"{folder}/{mp4_filename}" if folder else mp4_filename
    logger.info(f"Processing: {full_object_path}")
    logger.info(f"Folder: '{folder}', Filename: {mp4_filename}")

    # Check if file exists in MinIO
    logger.info("Checking if file exists in MinIO...")
    logger.info(f"  Bucket: {minio_service.bucket_name}")
    logger.info(f"  Full object path: {full_object_path}")

    if not minio_service.object_exists(folder, mp4_filename):
        logger.error("File not found in MinIO!")
        logger.error(f"  Searched for: {full_object_path}")
        logger.error(f"  In bucket: {minio_service.bucket_name}")

        # List objects in the folder to help debug
        logger.info("Listing objects in the folder for debugging...")
        try:
            objects = minio_service.list_objects(folder, recursive=False)
            if objects:
                logger.info(f"Found {len(objects)} objects in folder '{folder}':")
                for obj in objects[:10]:
                    logger.info(f"  - {obj}")
                if len(objects) > 10:
                    logger.info(f"  ... and {len(objects) - 10} more objects")
            else:
                logger.info(f"No objects found in folder '{folder}'")
        except Exception as e:
            logger.warning(f"Could not list objects in folder: {str(e)}")

        return False

    logger.success(f"File found in MinIO: {full_object_path}")

    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, mp4_filename)

        try:
            # Step 1: Download file from MinIO
            logger.info("Downloading file from MinIO...")
            logger.info(f"  Source: {full_object_path}")
            logger.info(f"  Destination: {temp_file_path}")

            if not minio_service.retrieve_to_file(folder, mp4_filename, temp_file_path):
                logger.error("Failed to download file from MinIO!")
                return False

            logger.success(f"Downloaded file to: {temp_file_path}")

            # Step 2: Create PersonaTranscriptionService instance
            device = "cuda" if os.system("nvidia-smi > /dev/null 2>&1") == 0 else "cpu"
            logger.info(f"Using device: {device}")

            persona_service = PersonaTranscriptionService(
                default_model_size=model_size,
                device=device,
            )

            # Step 3: Perform persona transcription
            logger.info(f"Starting persona transcription with model size: {model_size}...")
            temp_output_file = persona_service.transcribe_file(temp_file_path)

            logger.success("Persona transcription completed successfully!")
            logger.info(f"Temp output file: {temp_output_file}")

            # Display a preview of the results
            if os.path.exists(temp_output_file):
                with open(temp_output_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    lines = content.split("\n")
                    preview_lines = lines[:20]

                    logger.info("Preview of transcription with personas:")
                    print("\n" + "=" * 60)
                    for line in preview_lines:
                        print(line)
                    if len(lines) > 20:
                        print(f"\n... and {len(lines) - 20} more lines")
                    print("=" * 60)

            # Step 4: Upload transcription back to MinIO
            base_filename = Path(mp4_filename).stem
            transcription_filename = f"{base_filename}-transcription.txt"
            transcription_object_path = f"{folder}/{transcription_filename}" if folder else transcription_filename

            logger.info("Uploading transcription to MinIO...")
            logger.info(f"  Source: {temp_output_file}")
            logger.info(f"  Destination: {transcription_object_path}")
            logger.info(f"  Bucket: {minio_service.bucket_name}")

            with open(temp_output_file, "rb") as f:
                transcription_data = f.read()

            transcription_metadata = {
                "source_file": mp4_filename,
                "transcription_type": "persona",
                "model_size": model_size,
                "content_type": "text/plain",
            }

            success = minio_service.save(
                data=transcription_data,
                filename=transcription_object_path,
                content_type="text/plain",
                metadata=transcription_metadata,
            )

            if not success:
                logger.error("Failed to upload transcription to MinIO!")
                return False

            logger.success(f"Transcription uploaded to MinIO: {transcription_object_path}")

            return True

        except Exception as e:
            logger.error(f"Persona transcription failed: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            return False


def main():
    """Main function to handle command line arguments and orchestrate the transcription."""
    parser = argparse.ArgumentParser(
        description="Download audio/video from MinIO and perform persona transcription",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_persona_transcription.py "videos/my-video.mp4"
    python test_persona_transcription.py "folder/subfolder/video.mp4"
    python test_persona_transcription.py "3MZS5gNElZM.mp4"
    python test_persona_transcription.py "audio.wav" --model-size medium

Environment Variables (from .env file or system):
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET

Optional Environment Variables:
    MINIO_SECURE=true/false (default: true)
    MINIO_REGION=us-east-1 (optional)

Create a .env file in the project root with these variables.
        """,
    )

    parser.add_argument(
        "minio_path",
        help='Path to the audio/video file in MinIO (e.g., "folder/video.mp4")',
    )

    parser.add_argument(
        "--model-size",
        choices=["tiny", "base", "small", "medium", "large"],
        default="small",
        help="Whisper model size to use (default: small)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    setup_logging(args.log_level)

    logger.info("Starting PersonaTranscriptionService test...")

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

        # Perform the persona transcription
        success = test_persona_transcription(
            minio_service,
            args.minio_path,
            model_size=args.model_size,
        )

        if success:
            logger.success("All tests passed!")
            return 0
        else:
            logger.error("Tests failed!")
            return 1

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        logger.info(
            "Please set the required environment variables. See --help for details."
        )
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
