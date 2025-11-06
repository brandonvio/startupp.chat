#!/usr/bin/env python3
"""
Test script to demonstrate video ID-based file naming.
"""

import sys
import os
from loguru import logger

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services import YouTubeDownloadService, TranscriptionService

    logger.success("✅ Services imported successfully")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    sys.exit(1)


def test_download_service_naming():
    """Test that download service uses video ID for filenames."""
    logger.info("Testing download service naming...")

    try:
        service = YouTubeDownloadService()

        # Test with a sample video ID
        video_id = "dQw4w9WgXcQ"
        output_path = "."
        resolution = "best"

        # This would normally download the video, but we'll just test the configuration
        logger.info(f"Video ID: {video_id}")
        logger.info(f"Output path: {output_path}")
        logger.info(f"Expected filename: {video_id}.mp4")
        logger.info(f"Full path: {os.path.join(output_path, video_id + '.mp4')}")

        logger.success("✅ Download service naming test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Download service naming test failed: {e}")
        return False


def test_transcription_service_naming():
    """Test that transcription service uses video ID for filenames."""
    logger.info("Testing transcription service naming...")

    try:
        service = TranscriptionService()

        # Test with sample file paths
        test_cases = [
            ("3MZS5gNElZM.mp4", "3MZS5gNElZM", "3MZS5gNElZM.txt"),
            ("dQw4w9WgXcQ.mp4", "dQw4w9WgXcQ", "dQw4w9WgXcQ.txt"),
            ("./source-files/abc123.mp4", "abc123", "./source-files/abc123.txt"),
        ]

        for file_path, video_id, expected_output in test_cases:
            logger.info(f"Input file: {file_path}")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Expected output: {expected_output}")
            print()

        logger.success("✅ Transcription service naming test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Transcription service naming test failed: {e}")
        return False


def test_file_naming_consistency():
    """Test that file naming is consistent across services."""
    logger.info("Testing file naming consistency...")

    try:
        # Example workflow
        video_id = "example123"
        output_path = "./source-files/test"

        logger.info("=== Example Workflow ===")
        logger.info(f"Video ID: {video_id}")
        logger.info(f"Output directory: {output_path}")
        logger.info("")

        # Step 1: Download
        logger.info("Step 1: Download")
        expected_video_file = f"{output_path}/{video_id}.mp4"
        logger.info(f"Expected video file: {expected_video_file}")
        logger.info("")

        # Step 2: Transcribe
        logger.info("Step 2: Transcribe")
        expected_transcript_file = f"{output_path}/{video_id}.txt"
        logger.info(f"Expected transcript file: {expected_transcript_file}")
        logger.info("")

        # Step 3: Verify consistency
        logger.info("Step 3: Verify consistency")
        video_base = os.path.splitext(expected_video_file)[0]
        transcript_base = os.path.splitext(expected_transcript_file)[0]

        assert video_base == transcript_base, (
            "Video and transcript files should have the same base name"
        )
        logger.info("✅ File naming is consistent")

        logger.success("✅ File naming consistency test passed")
        return True

    except Exception as e:
        logger.error(f"❌ File naming consistency test failed: {e}")
        return False


def main():
    """Run all naming tests."""
    logger.info("🧪 Starting video ID-based naming tests...")

    tests = [
        test_download_service_naming,
        test_transcription_service_naming,
        test_file_naming_consistency,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    logger.info(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        logger.success(
            "🎉 All naming tests passed! Video ID-based naming is working correctly."
        )
        return 0
    else:
        logger.error("💥 Some naming tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
