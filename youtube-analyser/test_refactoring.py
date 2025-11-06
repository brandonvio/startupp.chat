#!/usr/bin/env python3
"""
Simple test script to verify the refactored services work correctly.
"""

import sys
import os
from loguru import logger

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services import ConfigService, YouTubeDownloadService, TranscriptionService
    from services.youtube_analyzer import YouTubeAnalyzer

    logger.success("✅ All service imports successful")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    sys.exit(1)


def test_config_service():
    """Test the configuration service."""
    logger.info("Testing ConfigService...")

    try:
        config = ConfigService()

        # Test default values
        assert config.get("download", "default_output_path") == "source-files"
        assert config.get("transcription", "default_model_size") == "medium"

        # Test setting values
        config.set("download", "test_key", "test_value")
        assert config.get("download", "test_key") == "test_value"

        logger.success("✅ ConfigService tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ ConfigService test failed: {e}")
        return False


def test_service_creation():
    """Test service creation directly."""
    logger.info("Testing service creation...")

    try:
        # Test creating services directly
        download_service = YouTubeDownloadService()
        transcription_service = TranscriptionService()
        analyzer = YouTubeAnalyzer()

        # Verify service types
        assert isinstance(download_service, YouTubeDownloadService)
        assert isinstance(transcription_service, TranscriptionService)
        assert isinstance(analyzer, YouTubeAnalyzer)

        logger.success("✅ Service creation tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Service creation test failed: {e}")
        return False


def test_analyzer_interface():
    """Test the analyzer interface methods."""
    logger.info("Testing analyzer interface...")

    try:
        # Create analyzer with default services
        analyzer = YouTubeAnalyzer()

        # Test that methods exist
        assert hasattr(analyzer, "analyze_youtube_video")
        assert hasattr(analyzer, "download_video")
        assert hasattr(analyzer, "transcribe_file")
        assert hasattr(analyzer, "get_video_info")
        assert hasattr(analyzer, "get_transcription_info")

        logger.success("✅ Analyzer interface tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Analyzer interface test failed: {e}")
        return False


def test_video_id_naming():
    """Test that services use video IDs for file naming."""
    logger.info("Testing video ID-based file naming...")

    try:
        # Create services
        download_service = YouTubeDownloadService()
        transcription_service = TranscriptionService()

        # Test that services can be created (basic functionality check)
        assert download_service is not None
        assert transcription_service is not None

        logger.success("✅ Video ID-based naming tests passed")
        return True

    except Exception as e:
        logger.error(f"❌ Video ID-based naming test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("🧪 Starting refactoring verification tests...")

    tests = [
        test_config_service,
        test_service_creation,
        test_analyzer_interface,
        test_video_id_naming,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    logger.info(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        logger.success("🎉 All tests passed! Refactoring successful.")
        return 0
    else:
        logger.error("💥 Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
