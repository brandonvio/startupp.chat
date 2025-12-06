#!/usr/bin/env python3
"""Test the AI post generation with updated prompt."""

import asyncio
from dotenv import load_dotenv
from loguru import logger
from services.analysis_service import OllamaAnalysisService

load_dotenv()


async def test_ai_post_generation():
    """Test the AI post generation with a sample analysis."""

    # Sample analysis content for testing
    sample_analysis = """
    **Video Summary:**
    This video covers advanced machine learning techniques for computer vision, 
    specifically focusing on convolutional neural networks and their applications in 
    image recognition. The presenter discusses various architectures including ResNet, 
    VGG, and modern transformer-based approaches.

    **Key Takeaways:**
    1. CNNs are essential for image processing tasks
    2. Transfer learning can dramatically reduce training time
    3. Attention mechanisms are becoming crucial in modern architectures
    4. Data augmentation is critical for robust models

    **Technical Insights:**
    The video demonstrates practical implementation of these concepts using PyTorch,
    with code examples showing how to build and train state-of-the-art models.
    """

    video_id = "dQw4w9WgXcQ"  # Sample video ID

    try:
        # Initialize analysis service
        analysis_service = OllamaAnalysisService()

        logger.info("Testing AI post generation with updated prompt...")
        logger.info(f"Sample analysis content: {len(sample_analysis)} characters")

        # Generate Bluesky post using the AI
        post_content = await analysis_service.generate_bluesky_post(
            video_id=video_id, analysis_content=sample_analysis
        )

        logger.success(f"Generated post ({len(post_content)} characters):")
        logger.info(f"📝 {post_content}")

        # Validate the post
        logger.info("\n" + "=" * 50)
        logger.info("VALIDATING GENERATED POST")
        logger.info("=" * 50)

        # Check if it contains YouTube URLs (should not)
        if "youtube.com" in post_content or "youtu.be" in post_content:
            logger.error("❌ Post contains YouTube URLs (should not)")
        else:
            logger.success("✅ Post does not contain YouTube URLs")

        # Count hashtags
        hashtag_count = post_content.count("#")
        if hashtag_count >= 2:
            logger.success(
                f"✅ Post contains {hashtag_count} hashtags (meets requirement)"
            )
        else:
            logger.warning(
                f"⚠️  Post contains only {hashtag_count} hashtags (needs at least 2)"
            )

        # Check character count
        if len(post_content) <= 250:
            logger.success(
                f"✅ Post is within 250 character limit ({len(post_content)} chars)"
            )
        else:
            logger.warning(
                f"⚠️  Post exceeds 250 character limit ({len(post_content)} chars)"
            )

        # Overall assessment
        has_urls = "youtube.com" in post_content or "youtu.be" in post_content
        meets_criteria = (
            (not has_urls) and (hashtag_count >= 2) and (len(post_content) <= 250)
        )

        if meets_criteria:
            logger.success("🎉 POST MEETS ALL CRITERIA!")
        else:
            logger.warning(
                "⚠️  Post does not meet all criteria, but iterative system should have improved it."
            )

        return post_content

    except Exception as e:
        logger.error(f"Test failed: {type(e).__name__}: {e}")
        return None


async def main():
    """Main test function."""
    logger.info("AI Post Generation Test")
    logger.info("=" * 50)

    post_content = await test_ai_post_generation()

    if post_content:
        logger.success("\n🎉 AI post generation test completed!")
    else:
        logger.error("\n❌ AI post generation test failed.")


if __name__ == "__main__":
    asyncio.run(main())
