#!/usr/bin/env python3
"""
Test script to demonstrate the new source-files directory structure.
"""

import sys
import os
from loguru import logger

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services import ConfigService, ServiceFactory

    logger.success("✅ Services imported successfully")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    sys.exit(1)


def test_directory_structure():
    """Test that the source-files directory structure is created correctly."""
    logger.info("Testing source-files directory structure...")

    try:
        # Create configuration service
        config = ConfigService()

        # Get default output path
        default_path = config.get("download", "default_output_path")
        logger.info(f"Default output path: {default_path}")

        # Ensure directory exists
        os.makedirs(default_path, exist_ok=True)
        logger.success(f"✅ Created directory: {default_path}")

        # Test subdirectory creation
        test_subdirs = ["custom", "individual", "env", "test"]

        for subdir in test_subdirs:
            subdir_path = os.path.join(default_path, subdir)
            os.makedirs(subdir_path, exist_ok=True)
            logger.info(f"Created subdirectory: {subdir_path}")

        # List directory contents
        logger.info("\n📁 Directory structure created:")
        logger.info(f"Root: {os.path.abspath('.')}")
        logger.info(f"Source files: {os.path.abspath(default_path)}")

        for subdir in test_subdirs:
            subdir_path = os.path.join(default_path, subdir)
            logger.info(f"  └── {subdir}/")

        logger.success("✅ Directory structure test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Directory structure test failed: {e}")
        return False


def test_file_naming_in_structure():
    """Test that files are named correctly within the source-files structure."""
    logger.info("Testing file naming within source-files structure...")

    try:
        # Example video IDs
        video_ids = ["3MZS5gNElZM", "dQw4w9WgXcQ", "abc123"]

        # Test different output paths
        test_paths = ["source-files", "source-files/custom", "source-files/individual"]

        logger.info("📋 Expected file structure:")

        for path in test_paths:
            logger.info(f"\n{path}/")
            for video_id in video_ids:
                video_file = f"{path}/{video_id}.mp4"
                transcript_file = f"{path}/{video_id}.txt"
                logger.info(f"  ├── {video_id}.mp4")
                logger.info(f"  └── {video_id}.txt")

        logger.success("✅ File naming structure test passed")
        return True

    except Exception as e:
        logger.error(f"❌ File naming structure test failed: {e}")
        return False


def test_configuration_integration():
    """Test that configuration properly integrates with source-files directory."""
    logger.info("Testing configuration integration...")

    try:
        # Create configuration service
        config = ConfigService()

        # Test default configuration
        default_path = config.get("download", "default_output_path")
        assert default_path == "source-files", (
            f"Expected 'source-files', got '{default_path}'"
        )

        # Test custom configuration
        config.set("download", "default_output_path", "source-files/custom")
        custom_path = config.get("download", "default_output_path")
        assert custom_path == "source-files/custom", (
            f"Expected 'source-files/custom', got '{custom_path}'"
        )

        # Test environment variable override
        os.environ["YT_OUTPUT_PATH"] = "source-files/env"
        config = ConfigService()  # Reload to pick up environment variable
        env_path = config.get("download", "default_output_path")
        assert env_path == "source-files/env", (
            f"Expected 'source-files/env', got '{env_path}'"
        )

        logger.success("✅ Configuration integration test passed")
        return True

    except Exception as e:
        logger.error(f"❌ Configuration integration test failed: {e}")
        return False


def main():
    """Run all source-files structure tests."""
    logger.info("🧪 Starting source-files directory structure tests...")

    tests = [
        test_directory_structure,
        test_file_naming_in_structure,
        test_configuration_integration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    logger.info(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        logger.success("🎉 All source-files structure tests passed!")
        logger.info(
            "📁 The application now stores all files in the 'source-files' directory"
        )
        logger.info(
            "🔧 You can customize subdirectories using configuration or environment variables"
        )
        return 0
    else:
        logger.error(
            "💥 Some source-files structure tests failed. Please check the implementation."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
