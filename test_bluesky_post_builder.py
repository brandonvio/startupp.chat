import os
import json
import requests
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from services.minio_service import MinIOService
from services.bluesky_service import BlueskyService
from services.analysis_service import OllamaAnalysisService
import asyncio

load_dotenv()


async def test_bluesky_post_builder():
    """
    Complete workflow test for building and posting Bluesky posts with video analysis and thumbnails.

    This script:
    1. Retrieves video analysis and JSON metadata from MinIO
    2. Downloads the high-resolution thumbnail
    3. Generates a Bluesky post using the analysis service
    4. Posts to Bluesky with text and image

    Required .env variables:
    - MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET_NAME
    - BLUESKY_HANDLE, BLUESKY_PASSWORD, BLUESKY_SERVICE_URL (optional)
    - OLLAMA_URL, OLLAMA_MODEL (optional)
    """

    # Configuration from environment
    video_id = "kb-faWxsdZ0"  # Test video ID

    # MinIO configuration
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket = os.getenv("MINIO_BUCKET_NAME")

    # Bluesky configuration
    bluesky_handle = os.getenv("BLUESKY_HANDLE")
    bluesky_password = os.getenv("BLUESKY_PASSWORD")
    bluesky_service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")

    # Ollama configuration
    ollama_url = os.getenv("OLLAMA_URL", "http://nvda:30434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

    # Validate required environment variables
    required_vars = {
        "MINIO_ENDPOINT": minio_endpoint,
        "MINIO_ACCESS_KEY": minio_access_key,
        "MINIO_SECRET_KEY": minio_secret_key,
        "MINIO_BUCKET_NAME": minio_bucket,
        "BLUESKY_HANDLE": bluesky_handle,
        "BLUESKY_PASSWORD": bluesky_password,
    }

    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        print(
            f"Error: Missing required environment variables: {', '.join(missing_vars)}"
        )
        print("\nExample .env configuration:")
        print("MINIO_ENDPOINT=localhost:9000")
        print("MINIO_ACCESS_KEY=your-access-key")
        print("MINIO_SECRET_KEY=your-secret-key")
        print("MINIO_BUCKET_NAME=your-bucket-name")
        print("BLUESKY_HANDLE=your.handle.bsky.social")
        print("BLUESKY_PASSWORD=your-app-password")
        print("BLUESKY_SERVICE_URL=https://bsky.social  # Optional")
        print("OLLAMA_URL=http://nvda:30434  # Optional")
        print("OLLAMA_MODEL=llama3.2  # Optional")
        return False

    try:
        # Initialize services
        print("🔧 Initializing services...")
        minio_service = MinIOService(
            endpoint=minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            bucket_name=minio_bucket,
            secure=False,  # Adjust based on your MinIO setup
        )

        bluesky_service = BlueskyService(
            handle=bluesky_handle,
            password=bluesky_password,
            service_url=bluesky_service_url,
        )

        analysis_service = OllamaAnalysisService(
            ollama_url=ollama_url, model_name=ollama_model
        )

        # Step 1: Retrieve analysis file from MinIO
        print(f"📥 Retrieving analysis file for video {video_id} from MinIO...")
        analysis_filename = f"{video_id}-analysis.txt"
        analysis_data = minio_service.retrieve("downloads", analysis_filename)

        if not analysis_data:
            print(f"❌ Analysis file not found: {analysis_filename}")
            return False

        analysis_content = analysis_data.decode("utf-8")
        print(f"✅ Retrieved analysis file ({len(analysis_content)} characters)")

        # Step 2: Retrieve JSON metadata from MinIO
        print(f"📥 Retrieving JSON metadata for video {video_id} from MinIO...")
        json_filename = f"{video_id}.json"
        json_data = minio_service.retrieve("downloads", json_filename)

        if not json_data:
            print(f"❌ JSON file not found: {json_filename}")
            return False

        video_metadata = json.loads(json_data.decode("utf-8"))
        print("✅ Retrieved video metadata")

        # Step 3: Extract high-resolution thumbnail URL
        print("🔍 Extracting thumbnail URL...")
        thumbnails = video_metadata.get("thumbnails", [])

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
        print(
            f"✅ Found thumbnail: {thumbnail_url} ({high_res_thumbnail['width']}x{high_res_thumbnail['height']})"
        )

        # Step 4: Download thumbnail
        print("📥 Downloading thumbnail...")
        response = requests.get(thumbnail_url)
        response.raise_for_status()

        # Save thumbnail to temporary file
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as temp_file:
            temp_file.write(response.content)
            thumbnail_path = temp_file.name

        print(
            f"✅ Downloaded thumbnail to {thumbnail_path} ({len(response.content)} bytes)"
        )

        # Step 5: Generate Bluesky post using analysis service
        print("🤖 Generating Bluesky post...")
        bluesky_post_content = await analysis_service.generate_bluesky_post(
            video_id, analysis_content
        )

        print(f"✅ Generated Bluesky post ({len(bluesky_post_content)} characters):")
        print(f"📝 Post content: {bluesky_post_content}")

        # Step 6: Authenticate with Bluesky
        print("🔐 Authenticating with Bluesky...")
        if not bluesky_service.authenticate():
            print("❌ Failed to authenticate with Bluesky")
            return False

        print(f"✅ Authenticated with Bluesky as {bluesky_handle}")

        # Step 7: Post to Bluesky with image
        print("📤 Posting to Bluesky...")
        success = bluesky_service.post_with_image(
            text=bluesky_post_content,
            image_path=thumbnail_path,
            alt_text=f"Thumbnail for YouTube video: {video_metadata.get('title', video_id)}",
        )

        if success:
            print("🎉 Successfully posted to Bluesky!")
        else:
            print("❌ Failed to post to Bluesky")
            return False

        # Cleanup temporary file
        try:
            os.unlink(thumbnail_path)
            print(f"🧹 Cleaned up temporary file: {thumbnail_path}")
        except Exception as e:
            print(f"⚠️ Warning: Could not delete temporary file {thumbnail_path}: {e}")

        print("\n🎉 Bluesky post workflow completed successfully!")
        print("📊 Summary:")
        print(f"   • Video ID: {video_id}")
        print(f"   • Video Title: {video_metadata.get('title', 'Unknown')}")
        print(f"   • Post Length: {len(bluesky_post_content)} characters")
        print(
            f"   • Thumbnail Resolution: {high_res_thumbnail['width']}x{high_res_thumbnail['height']}"
        )
        print(f"   • Analysis Length: {len(analysis_content)} characters")

        return True

    except Exception as e:
        print(f"❌ Workflow failed with error: {e}")
        # Cleanup temporary file if it exists
        if "thumbnail_path" in locals():
            try:
                os.unlink(thumbnail_path)
            except:
                pass
        return False


def create_sample_env():
    """Create a sample .env file template for the workflow."""
    env_content = """# MinIO Configuration
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your-minio-access-key
MINIO_SECRET_KEY=your-minio-secret-key
MINIO_BUCKET_NAME=your-bucket-name

# Bluesky Configuration
# Your Bluesky handle (username)
BLUESKY_HANDLE=your.handle.bsky.social

# Your app password (generate at https://bsky.app/settings/app-passwords)
# DO NOT use your account password - create an app password for security
BLUESKY_PASSWORD=your-app-password-here

# Bluesky service URL (optional, defaults to https://bsky.social)
BLUESKY_SERVICE_URL=https://bsky.social

# Ollama Configuration (optional)
OLLAMA_URL=http://nvda:30434
OLLAMA_MODEL=llama3.2
"""

    env_path = Path(".env.bluesky_workflow_example")
    with open(env_path, "w") as f:
        f.write(env_content)

    print(f"Created {env_path} with example configuration")
    print("Copy this to .env and fill in your actual credentials")


if __name__ == "__main__":
    print("Bluesky Post Builder Workflow Test")
    print("=" * 50)

    # Check if .env exists
    if not Path(".env").exists():
        print("No .env file found.")
        create_sample_env()
        print("\nPlease create a .env file with your credentials and run again.")
    else:
        # Run the complete workflow
        success = asyncio.run(test_bluesky_post_builder())
        if success:
            print("\n🎉 Workflow completed successfully!")
        else:
            print("\n❌ Workflow failed. Check the output above for details.")
