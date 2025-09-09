import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger
from services.analysis_service import OllamaAnalysisService

# Load environment variables
load_dotenv()


async def test_bluesky_post_generation():
    """
    Test generating a Bluesky post from the test-analysis.txt file.
    
    This test reads the analysis content and generates a post using the
    OllamaAnalysisService, then prints the result to console.
    
    Required .env variables:
    OLLAMA_URL=http://nvda:30434 (optional)
    OLLAMA_MODEL=gptoss:20b (optional)
    """
    
    # Get configuration from environment
    ollama_url = os.getenv("OLLAMA_URL", "http://nvda:30434")
    ollama_model = os.getenv("OLLAMA_MODEL", "gptoss:20b")
    
    # Define file path
    analysis_file_path = Path("downloads/test-analysis.txt")
    
    # Check if file exists
    if not analysis_file_path.exists():
        logger.error(f"Analysis file not found: {analysis_file_path}")
        return False
    
    # Read analysis content from file
    try:
        with open(analysis_file_path, "r", encoding="utf-8") as f:
            analysis_content = f.read().strip()
        
        logger.info(f"Read analysis content ({len(analysis_content)} characters)")
        logger.info(f"First 200 characters: {analysis_content[:200]}...")
        
    except Exception as e:
        logger.error(f"Failed to read analysis file: {e}")
        return False
    
    try:
        # Initialize analysis service
        logger.info(f"Initializing OllamaAnalysisService with {ollama_url} using model {ollama_model}...")
        analysis_service = OllamaAnalysisService(
            ollama_url=ollama_url,
            model_name=ollama_model
        )
        
        # Generate Bluesky post
        logger.info("Generating Bluesky post...")
        video_id = "_TTNGq9djU4"  # Extract from the analysis file
        
        post_content = await analysis_service.generate_bluesky_post(
            video_id=video_id,
            analysis_content=analysis_content
        )
        
        # Print results
        print("\n" + "="*60)
        print("GENERATED BLUESKY POST")
        print("="*60)
        print(f"Character count: {len(post_content)}")
        print(f"Content:\n{post_content}")
        print("="*60)
        
        # Count hashtags
        hashtag_count = post_content.count('#')
        print(f"Hashtag count: {hashtag_count}")
        
        # Validation check
        if len(post_content) <= 290 and hashtag_count >= 2:
            logger.success("✅ Post meets requirements!")
        else:
            logger.warning(f"❌ Post validation issues:")
            if len(post_content) > 290:
                logger.warning(f"   - Too long: {len(post_content)} > 290 characters")
            if hashtag_count < 2:
                logger.warning(f"   - Not enough hashtags: {hashtag_count} < 2")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {type(e).__name__}: {e}")
        return False


def main():
    """Main function to run the test."""
    logger.remove()
    logger.add(
        os.sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        colorize=True,
    )
    
    logger.info("Bluesky Post Generation Test")
    logger.info("=" * 50)
    
    # Check if .env exists
    if not Path(".env").exists():
        logger.warning("No .env file found. Using default configuration.")
        logger.info("Optional .env configuration:")
        logger.info("OLLAMA_URL=http://nvda:30434")
        logger.info("OLLAMA_MODEL=gptoss:20b")
    
    # Run the test
    success = asyncio.run(test_bluesky_post_generation())
    
    if success:
        logger.success("\n🎉 Post generation test completed successfully!")
    else:
        logger.error("\n❌ Post generation test failed. Check the output above for details.")


if __name__ == "__main__":
    main()