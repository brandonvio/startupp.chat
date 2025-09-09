import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from services.bluesky_service import BlueskyService

load_dotenv()

def test_bluesky_service():
    """
    Test the BlueskyService functionality.
    
    Required .env variables:
    BLUESKY_HANDLE=your.handle.bsky.social
    BLUESKY_PASSWORD=your-app-password
    BLUESKY_SERVICE_URL=https://bsky.social (optional, defaults to https://bsky.social)
    """
    
    # Get configuration from environment
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")
    
    if not handle or not password:
        print("Error: BLUESKY_HANDLE and BLUESKY_PASSWORD must be set in .env file")
        print("\nExample .env configuration:")
        print("BLUESKY_HANDLE=your.handle.bsky.social")
        print("BLUESKY_PASSWORD=your-app-password")
        print("BLUESKY_SERVICE_URL=https://bsky.social  # Optional")
        return False
    
    try:
        # Initialize service
        print(f"Initializing BlueskyService for {handle}...")
        service = BlueskyService(handle, password, service_url)
        
        # Test authentication
        print("Testing authentication...")
        if not service.authenticate():
            print("Authentication failed!")
            return False
        
        # Test text-only post
        print("Testing text-only post...")
        test_text = "Test post from Python BlueskyService 🤖"
        if service.post_text_only(test_text):
            print("✓ Text-only post successful")
        else:
            print("✗ Text-only post failed")
            return False
        
        # Test post with YouTube thumbnail image
        print("Testing post with YouTube thumbnail image...")
        youtube_image_url = "https://i.ytimg.com/vi_webp/08mH36_NVos/maxresdefault.webp"
        
        try:
            # Download the image
            print("Downloading YouTube thumbnail...")
            response = requests.get(youtube_image_url)
            response.raise_for_status()
            
            # Save temporarily
            temp_image_path = Path("temp_youtube_thumb.webp")
            with open(temp_image_path, "wb") as f:
                f.write(response.content)
            
            # Post with the downloaded image
            if service.post_with_image(
                text="Sharing a YouTube thumbnail via Python BlueskyService 🎬",
                image_path=temp_image_path,
                alt_text="YouTube video thumbnail"
            ):
                print("✓ Post with YouTube thumbnail successful")
            else:
                print("✗ Post with YouTube thumbnail failed")
            
            # Clean up temporary file
            temp_image_path.unlink(missing_ok=True)
            
        except Exception as e:
            print(f"✗ Failed to download or post YouTube thumbnail: {e}")
        
        # Test general post method
        print("Testing general post method...")
        if service.post("Another test post using the general post method 🚀"):
            print("✓ General post method successful")
        else:
            print("✗ General post method failed")
            return False
        
        print("\nAll tests completed successfully! ✨")
        return True
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return False


def create_sample_env():
    """Create a sample .env file template."""
    env_content = """# Bluesky Configuration
# Your Bluesky handle (username)
BLUESKY_HANDLE=your.handle.bsky.social

# Your app password (generate at https://bsky.app/settings/app-passwords)
# DO NOT use your account password - create an app password for security
BLUESKY_PASSWORD=your-app-password-here

# Bluesky service URL (optional, defaults to https://bsky.social)
BLUESKY_SERVICE_URL=https://bsky.social
"""
    
    env_path = Path(".env.example")
    with open(env_path, "w") as f:
        f.write(env_content)
    
    print(f"Created {env_path} with example configuration")
    print("Copy this to .env and fill in your actual credentials")


if __name__ == "__main__":
    print("Bluesky Service Test")
    print("=" * 50)
    
    # Check if .env exists
    if not Path(".env").exists():
        print("No .env file found.")
        create_sample_env()
        print("\nPlease create a .env file with your Bluesky credentials and run again.")
    else:
        # Run tests
        success = test_bluesky_service()
        if success:
            print("\n🎉 All tests passed!")
        else:
            print("\n❌ Some tests failed. Check the output above for details.")