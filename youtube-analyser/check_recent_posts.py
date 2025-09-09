import os
from dotenv import load_dotenv
from loguru import logger
from services.bluesky_service import BlueskyService

load_dotenv()

def check_recent_posts():
    """Check recent posts to verify the video post was created."""
    
    handle = os.getenv("BLUESKY_HANDLE")
    password = os.getenv("BLUESKY_PASSWORD")
    service_url = os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social")
    
    if not handle or not password:
        logger.error("Missing Bluesky credentials")
        return
    
    try:
        # Initialize and authenticate
        service = BlueskyService(handle, password, service_url)
        if not service.authenticate():
            logger.error("Authentication failed")
            return
        
        logger.info(f"Checking recent posts for {handle}...")
        
        # Get user's profile to check recent posts
        user_did = service.client.me.did
        logger.info(f"User DID: {user_did}")
        
        # Get recent posts from the user's feed
        response = service.client.com.atproto.repo.list_records({
            "repo": user_did,
            "collection": "app.bsky.feed.post",
            "limit": 10,  # Check last 10 posts
        })
        
        logger.info(f"Found {len(response.records)} recent posts:")
        
        for i, record in enumerate(response.records[:5], 1):  # Show last 5
            post_data = record.value
            text = post_data.get('text', '')[:100]  # First 100 chars
            created_at = post_data.get('createdAt', '')
            has_embed = 'embed' in post_data
            embed_type = post_data.get('embed', {}).get('$type', 'none') if has_embed else 'none'
            
            logger.info(f"Post {i}:")
            logger.info(f"  Created: {created_at}")
            logger.info(f"  Text: {text}...")
            logger.info(f"  Has Embed: {has_embed}")
            logger.info(f"  Embed Type: {embed_type}")
            
            # Check if this might be our video post
            if 'MIT' in text or 'deep' in text or 'neural' in text:
                logger.success(f"🎯 Found potential MIT post!")
                if embed_type == 'app.bsky.embed.video':
                    logger.success(f"✅ Post has video embed!")
                else:
                    logger.warning(f"⚠️ Post found but no video embed (type: {embed_type})")
            
            logger.info("")
    
    except Exception as e:
        logger.error(f"Failed to check posts: {type(e).__name__}: {e}")

if __name__ == "__main__":
    check_recent_posts()