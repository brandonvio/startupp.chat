#!/usr/bin/env python3
"""
Basic Usage Example for YouTube Analyzer Services

This example demonstrates how to use the refactored services
with different configurations and use cases.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from services import ConfigService
from services.youtube_analyzer import YouTubeAnalyzer


def example_basic_usage():
    """Example of basic usage with default configuration."""
    logger.info("=== Basic Usage Example ===")

    # Create analyzer with default configuration
    analyzer = YouTubeAnalyzer()

    # Analyze a YouTube video (download + transcribe)
    video_id = "3MZS5gNElZM"
    result = analyzer.analyze_youtube_video(video_id)

    if result["success"]:
        logger.success(f"Analysis completed for {video_id}")
        logger.info(f"Video: {result['video_file']}")
        logger.info(f"Transcription: {result['transcription_file']}")
    else:
        logger.error(f"Analysis failed: {result['error']}")


def example_custom_configuration():
    """Example of using custom configuration."""
    logger.info("=== Custom Configuration Example ===")

    # Create custom configuration
    config = ConfigService()
    config.set("download", "default_output_path", "./source-files/custom")
    config.set("transcription", "default_model_size", "small")
    config.set("transcription", "device", "cpu")  # Use CPU instead of CUDA

    # Create analyzer with custom config
    analyzer = YouTubeAnalyzer(config)

    # Use custom settings
    video_id = "3MZS5gNElZM"
    result = analyzer.analyze_youtube_video(
        video_id=video_id, output_path="./downloads", model_size="small"
    )

    if result["success"]:
        logger.success("Custom configuration analysis completed")


def example_individual_services():
    """Example of using services individually."""
    logger.info("=== Individual Services Example ===")

    # For individual services, you would need to use them directly
    # or create a custom configuration
    config = ConfigService()
    config.set("download", "default_output_path", "./source-files/individual")
    config.set("transcription", "default_model_size", "base")
    config.set("transcription", "device", "cpu")

    analyzer = YouTubeAnalyzer(config)

    # Download only
    video_id = "3MZS5gNElZM"
    try:
        video_file = analyzer.download_video(video_id)
        logger.success(f"Video downloaded: {video_file}")

        # Transcribe the downloaded file
        transcription_file = analyzer.transcribe_file(video_file, video_id=video_id)
        logger.success(f"Transcription completed: {transcription_file}")

    except Exception as e:
        logger.error(f"Error: {e}")


def example_environment_configuration():
    """Example of using environment variables for configuration."""
    logger.info("=== Environment Configuration Example ===")

    # Set environment variables (in real usage, these would be set in your shell)
    os.environ["YT_OUTPUT_PATH"] = "./source-files/env"
    os.environ["WHISPER_MODEL_SIZE"] = "tiny"
    os.environ["WHISPER_DEVICE"] = "cpu"

    # Create config service (will automatically load environment variables)
    config = ConfigService()

    # Show loaded configuration
    logger.info(f"Download config: {config.get_download_config()}")
    logger.info(f"Transcription config: {config.get_transcription_config()}")

    # Use the configuration
    analyzer = YouTubeAnalyzer(config)

    video_id = "3MZS5gNElZM"
    result = analyzer.analyze_youtube_video(video_id)

    if result["success"]:
        logger.success("Environment-based configuration analysis completed")


def main():
    """Run all examples."""
    try:
        # Create source-files directories if they don't exist
        os.makedirs("./source-files", exist_ok=True)
        os.makedirs("./source-files/custom", exist_ok=True)
        os.makedirs("./source-files/individual", exist_ok=True)
        os.makedirs("./source-files/env", exist_ok=True)

        # Run examples
        example_basic_usage()
        print()

        example_custom_configuration()
        print()

        example_individual_services()
        print()

        example_environment_configuration()

        logger.success("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Example failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
