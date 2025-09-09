from typing import Optional, Dict, Any
import asyncio
import os
from pathlib import Path
from loguru import logger
from ollama import AsyncClient, ChatResponse


class OllamaAnalysisService:
    """Analysis service that uses Ollama to generate summaries and insights from transcriptions."""

    def __init__(
        self,
        ollama_url: str = "http://nvda:30434",
        model_name: str = "llama3.2",
        temperature: float = 0.7,
        max_tokens: int = 200000,
        prompts_dir: Optional[str] = None,
    ):
        """
        Initialize the Ollama analysis service.

        Args:
            ollama_url (str): URL of the Ollama server.
            model_name (str): Name of the model to use for analysis.
            temperature (float): Temperature for text generation.
            max_tokens (int): Maximum number of tokens to generate.
            prompts_dir (str, optional): Directory containing prompt files. Defaults to services/prompts/.
        """
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = AsyncClient(host=ollama_url)

        # Set up prompts directory
        if prompts_dir is None:
            # Default to prompts directory relative to this file
            self.prompts_dir = Path(__file__).parent / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)

        # Load prompts from files
        self._load_prompts()

        logger.info(
            f"Initialized Ollama analysis service with {ollama_url} using model {model_name}"
        )

    def _load_prompts(self) -> None:
        """Load prompt templates from text files."""
        # Load analysis prompt
        analysis_prompt_file = self.prompts_dir / "analysis-prompt.txt"
        with open(analysis_prompt_file, "r", encoding="utf-8") as f:
            self.analysis_prompt_template = f.read().strip()
        logger.info(f"Loaded analysis prompt from {analysis_prompt_file}")

        # Load LinkedIn prompt
        linkedin_prompt_file = self.prompts_dir / "linkedin-prompt.txt"
        with open(linkedin_prompt_file, "r", encoding="utf-8") as f:
            self.linkedin_prompt_template = f.read().strip()
        logger.info(f"Loaded LinkedIn prompt from {linkedin_prompt_file}")

        # Load Bluesky prompt
        bluesky_prompt_file = self.prompts_dir / "bluesky-prompt.txt"
        with open(bluesky_prompt_file, "r", encoding="utf-8") as f:
            self.bluesky_prompt_template = f.read().strip()
        logger.info(f"Loaded Bluesky prompt from {bluesky_prompt_file}")

        # Load Bluesky validation prompt
        bluesky_validation_prompt_file = (
            self.prompts_dir / "bluesky-validation-prompt.txt"
        )
        with open(bluesky_validation_prompt_file, "r", encoding="utf-8") as f:
            self.bluesky_validation_prompt_template = f.read().strip()
        logger.info(
            f"Loaded Bluesky validation prompt from {bluesky_validation_prompt_file}"
        )

    def _create_analysis_prompt(self, transcription_text: str) -> str:
        """
        Create a comprehensive prompt for analyzing the transcription.

        Args:
            transcription_text (str): The transcription content to analyze.

        Returns:
            str: Formatted prompt for the LLM.
        """
        return self.analysis_prompt_template.format(
            transcription_text=transcription_text
        )

    def _create_linkedin_prompt(self, transcription_text: str) -> str:
        """
        Create a prompt for generating an engaging LinkedIn post.

        Args:
            transcription_text (str): The transcription content to create a post from.

        Returns:
            str: Formatted prompt for the LLM.
        """
        return self.linkedin_prompt_template.format(
            transcription_text=transcription_text
        )

    def _create_bluesky_prompt(
        self, analysis_content: str, video_id: str, improvement_guidance: str = ""
    ) -> str:
        """
        Create a prompt for generating a Bluesky post.

        Args:
            analysis_content (str): The analysis content to create a post from.
            video_id (str): The video ID for the YouTube URL.
            improvement_guidance (str): Optional feedback for improving the post.

        Returns:
            str: Formatted prompt for the LLM.
        """
        return self.bluesky_prompt_template.format(
            analysis_content=analysis_content,
            video_id=video_id,
            improvement_guidance=improvement_guidance
            or "No previous feedback - create your best post.",
        )

    def _create_bluesky_validation_prompt(self, post_content: str) -> str:
        """
        Create a prompt for validating a Bluesky post.

        Args:
            post_content (str): The post content to validate.

        Returns:
            str: Formatted validation prompt for the LLM.
        """
        return self.bluesky_validation_prompt_template.format(post_content=post_content)

    async def _validate_bluesky_post(self, post_content: str) -> tuple[bool, str]:
        """
        Validate a Bluesky post using LLM with fallback to manual validation.

        Args:
            post_content (str): The post content to validate.

        Returns:
            tuple[bool, str]: (meets_requirements, improvement_guidance)
        """
        try:
            validation_prompt = self._create_bluesky_validation_prompt(post_content)

            logger.info("Validating Bluesky post with LLM")
            response: ChatResponse = await self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": validation_prompt}],
                options={
                    "temperature": 0.1,  # Very low temperature for consistent validation
                    "num_predict": 200,  # Shorter response for structured output
                },
            )

            validation_response = response["message"]["content"].strip()
            logger.info(f"Raw validation response: {validation_response}")

            # Fallback to manual validation if LLM response is empty or malformed
            if not validation_response or len(validation_response) < 10:
                logger.warning("LLM validation response is empty/invalid, using manual validation")
                return self._manual_validate_post(post_content)

            # Parse the validation response more robustly
            lines = [line.strip() for line in validation_response.split("\n") if line.strip()]
            meets_requirements = False
            improvement_guidance = ""
            character_count = None
            hashtag_count = None

            for line in lines:
                if "MEETS_REQUIREMENTS:" in line:
                    meets_requirements = "YES" in line.upper()
                    logger.info(f"Parsed MEETS_REQUIREMENTS: {'YES' if meets_requirements else 'NO'}")
                elif "IMPROVEMENT_GUIDANCE:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        improvement_guidance = parts[1].strip()
                        logger.info(f"Parsed IMPROVEMENT_GUIDANCE: {improvement_guidance}")
                elif "CHARACTER_COUNT:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        try:
                            character_count = int(parts[1].strip())
                            logger.info(f"Parsed CHARACTER_COUNT: {character_count}")
                        except ValueError:
                            logger.warning(f"Could not parse character count from: {parts[1]}")
                elif "HASHTAG_COUNT:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        try:
                            hashtag_count = int(parts[1].strip())
                            logger.info(f"Parsed HASHTAG_COUNT: {hashtag_count}")
                        except ValueError:
                            logger.warning(f"Could not parse hashtag count from: {parts[1]}")

            # If we couldn't parse critical values, fall back to manual validation
            if character_count is None or hashtag_count is None:
                logger.warning("Could not parse LLM validation response, using manual validation")
                return self._manual_validate_post(post_content)

            # Log detailed validation results
            if not meets_requirements:
                logger.warning("🔍 VALIDATION FAILED - Detailed breakdown:")
                logger.warning(f"   📏 Character count: {character_count} (limit: 290)")
                logger.warning(f"   #️⃣  Hashtag count: {hashtag_count} (minimum: 2)")
                logger.warning(f"   💬 Feedback: {improvement_guidance}")
                
                # Add specific failure reasons if parsing worked
                failure_reasons = []
                if character_count and character_count > 290:
                    failure_reasons.append(f"exceeds character limit ({character_count}/290)")
                if hashtag_count is not None and hashtag_count < 2:
                    failure_reasons.append(f"insufficient hashtags ({hashtag_count}/2 minimum)")
                
                if failure_reasons:
                    logger.warning(f"   🚨 Specific issues: {', '.join(failure_reasons)}")
            else:
                logger.success("✅ VALIDATION PASSED - Post meets all requirements")
                logger.info(f"   📏 Character count: {character_count}/290")
                logger.info(f"   #️⃣  Hashtag count: {hashtag_count}")

            return meets_requirements, improvement_guidance

        except Exception as e:
            logger.error(f"LLM validation failed: {str(e)}, falling back to manual validation")
            return self._manual_validate_post(post_content)

    def _manual_validate_post(self, post_content: str) -> tuple[bool, str]:
        """
        Manual validation as fallback when LLM validation fails.
        
        Args:
            post_content (str): The post content to validate.
            
        Returns:
            tuple[bool, str]: (meets_requirements, improvement_guidance)
        """
        logger.info("🔧 Using manual validation")
        
        # Count characters and hashtags
        character_count = len(post_content)
        hashtag_count = post_content.count('#')
        
        logger.info(f"Manual validation results:")
        logger.info(f"   📏 Character count: {character_count}/290")
        logger.info(f"   #️⃣  Hashtag count: {hashtag_count}")
        
        # Check requirements
        meets_requirements = character_count <= 290 and hashtag_count >= 2
        
        if meets_requirements:
            logger.success("✅ MANUAL VALIDATION PASSED")
            return True, "APPROVED"
        else:
            # Build specific feedback
            issues = []
            if character_count > 290:
                issues.append(f"Too long ({character_count}/290 characters)")
            if hashtag_count < 2:
                issues.append(f"Need more hashtags ({hashtag_count}/2 minimum)")
            
            feedback = f"Manual validation failed: {', '.join(issues)}"
            logger.warning(f"❌ MANUAL VALIDATION FAILED: {feedback}")
            return False, feedback

    def reload_prompts(self) -> None:
        """
        Reload prompt templates from files.

        Useful for updating prompts without restarting the service.
        """
        logger.info("Reloading prompt templates from files...")
        self._load_prompts()
        logger.success("Prompt templates reloaded successfully")

    def get_prompts_info(self) -> Dict[str, Any]:
        """
        Get information about loaded prompts.

        Returns:
            dict: Information about prompts directory and loaded templates
        """
        return {
            "prompts_directory": str(self.prompts_dir),
            "analysis_prompt_length": (
                len(self.analysis_prompt_template)
                if hasattr(self, "analysis_prompt_template")
                else 0
            ),
            "linkedin_prompt_length": (
                len(self.linkedin_prompt_template)
                if hasattr(self, "linkedin_prompt_template")
                else 0
            ),
            "bluesky_prompt_length": (
                len(self.bluesky_prompt_template)
                if hasattr(self, "bluesky_prompt_template")
                else 0
            ),
            "analysis_prompt_file": str(self.prompts_dir / "analysis-prompt.txt"),
            "linkedin_prompt_file": str(self.prompts_dir / "linkedin-prompt.txt"),
            "bluesky_prompt_file": str(self.prompts_dir / "bluesky-prompt.txt"),
        }

    async def analyze_transcription(
        self, transcription_file: str, video_id: Optional[str] = None
    ) -> str:
        """
        Analyze a transcription file and generate a summary analysis.

        Args:
            transcription_file (str): Path to the transcription file to analyze.
            video_id (str, optional): Video ID for naming the output file.

        Returns:
            str: Path to the generated analysis file.
        """
        try:
            # Read transcription file
            if not os.path.exists(transcription_file):
                raise FileNotFoundError(
                    f"Transcription file not found: {transcription_file}"
                )

            with open(transcription_file, "r", encoding="utf-8") as f:
                transcription_content = f.read()

            if not transcription_content.strip():
                raise ValueError("Transcription file is empty")

            logger.info(f"Starting analysis of transcription: {transcription_file}")

            # Create analysis prompt
            prompt = self._create_analysis_prompt(transcription_content)

            # Generate analysis using Ollama
            logger.info(f"Sending analysis request to Ollama at {self.ollama_url}")
            response: ChatResponse = await self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            analysis_content = response["message"]["content"]

            # Generate output filename
            if video_id:
                base_name = video_id
            else:
                # Extract base name from transcription file
                base_name = os.path.splitext(os.path.basename(transcription_file))[0]

            # Use same directory as transcription file
            transcription_dir = os.path.dirname(transcription_file)
            analysis_file = os.path.join(transcription_dir, f"{base_name}-analysis.txt")

            # Write analysis to file
            with open(analysis_file, "w", encoding="utf-8") as f:
                f.write(f"# Video Analysis Report\n")
                f.write(f"**Video ID:** {video_id or 'Unknown'}\n")
                f.write(
                    f"**Transcription File:** {os.path.basename(transcription_file)}\n"
                )
                f.write(f"**Analysis Generated:** {asyncio.get_event_loop().time()}\n")
                f.write(f"**Model Used:** {self.model_name}\n\n")
                f.write("---\n\n")
                f.write(analysis_content)

            logger.success(f"Analysis completed and saved: {analysis_file}")
            return analysis_file

        except Exception as e:
            error_msg = (
                f"Failed to analyze transcription {transcription_file}: {str(e)}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    async def get_analysis_info(self, transcription_file: str) -> Dict[str, Any]:
        """
        Get analysis information without saving to file.

        Args:
            transcription_file (str): Path to transcription file.

        Returns:
            dict: Analysis metadata and content.
        """
        try:
            # Read transcription file
            if not os.path.exists(transcription_file):
                raise FileNotFoundError(
                    f"Transcription file not found: {transcription_file}"
                )

            with open(transcription_file, "r", encoding="utf-8") as f:
                transcription_content = f.read()

            # Create analysis prompt
            prompt = self._create_analysis_prompt(transcription_content)

            # Generate analysis using Ollama
            response: ChatResponse = await self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            print("########################################################")
            logger.info(f"Analysis response: {response}")
            print("########################################################")

            return {
                "analysis_content": response["message"]["content"],
                "model_used": self.model_name,
                "transcription_length": len(transcription_content),
                "word_count": len(transcription_content.split()),
                "ollama_url": self.ollama_url,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

        except Exception as e:
            error_msg = (
                f"Failed to get analysis info for {transcription_file}: {str(e)}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_sync_analysis_info(self, transcription_file: str) -> Dict[str, Any]:
        """
        Synchronous wrapper for get_analysis_info.

        Args:
            transcription_file (str): Path to transcription file.

        Returns:
            dict: Analysis metadata and content.
        """
        return asyncio.run(self.get_analysis_info(transcription_file))

    async def generate_linkedin_post(
        self, transcription_file: str, video_id: Optional[str] = None
    ) -> str:
        """
        Generate a LinkedIn post from a transcription file.

        Args:
            transcription_file (str): Path to the transcription file.
            video_id (str, optional): Video ID for naming the output file.

        Returns:
            str: Path to the generated LinkedIn post file.
        """
        try:
            # Read transcription file
            if not os.path.exists(transcription_file):
                raise FileNotFoundError(
                    f"Transcription file not found: {transcription_file}"
                )

            with open(transcription_file, "r", encoding="utf-8") as f:
                transcription_content = f.read()

            if not transcription_content.strip():
                raise ValueError("Transcription file is empty")

            logger.info(
                f"Generating LinkedIn post for transcription: {transcription_file}"
            )

            # Create LinkedIn post prompt
            prompt = self._create_linkedin_prompt(transcription_content)

            # Generate post using Ollama
            logger.info(f"Sending LinkedIn post request to Ollama at {self.ollama_url}")
            response: ChatResponse = await self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.8,  # Slightly higher for more creative posts
                    "num_predict": 1000,  # Shorter for LinkedIn posts
                },
            )

            post_content = response["message"]["content"]

            # Generate output filename
            if video_id:
                base_name = video_id
            else:
                # Extract base name from transcription file
                base_name = os.path.splitext(os.path.basename(transcription_file))[0]

            # Use same directory as transcription file
            transcription_dir = os.path.dirname(transcription_file)
            post_file = os.path.join(
                transcription_dir, f"{base_name}-linkedin-post.txt"
            )

            # Write LinkedIn post to file
            with open(post_file, "w", encoding="utf-8") as f:
                f.write(f"# LinkedIn Post - {video_id or 'Unknown'}\n")
                f.write(f"**Generated from:** {os.path.basename(transcription_file)}\n")
                f.write(f"**Model Used:** {self.model_name}\n\n")
                f.write("---\n\n")
                f.write(post_content)

            logger.success(f"LinkedIn post generated and saved: {post_file}")
            return post_file

        except Exception as e:
            error_msg = (
                f"Failed to generate LinkedIn post for {transcription_file}: {str(e)}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    async def generate_bluesky_post(self, video_id: str, analysis_content: str) -> str:
        """
        Generate a Bluesky post from video analysis content with iterative improvement.

        Args:
            video_id (str): The YouTube video ID.
            analysis_content (str): The full analysis content of the video.

        Returns:
            str: The complete Bluesky post content ready to post.
        """
        try:
            if not analysis_content.strip():
                raise ValueError("Analysis content is empty")

            logger.info(f"Generating Bluesky post for video ID: {video_id}")

            max_iterations = 5
            improvement_guidance = ""

            for iteration in range(1, max_iterations + 1):
                logger.info(
                    f"Bluesky post generation attempt {iteration}/{max_iterations}"
                )

                # Create Bluesky post prompt with improvement guidance
                prompt = self._create_bluesky_prompt(
                    analysis_content, video_id, improvement_guidance
                )

                # Generate post using Ollama
                logger.info(
                    f"Sending Bluesky post request to Ollama at {self.ollama_url}"
                )
                response: ChatResponse = await self.client.chat(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": 0.7,
                        "num_predict": 5000,
                    },
                )

                post_content = response["message"]["content"].strip()
                logger.info(
                    f"Generated post ({len(post_content)} characters): {post_content}"
                )

                # Validate the post with LLM
                meets_requirements, validation_feedback = (
                    await self._validate_bluesky_post(post_content)
                )

                if meets_requirements:
                    logger.success(
                        f"✅ Bluesky post approved on attempt {iteration} ({len(post_content)} characters)"
                    )
                    return post_content
                else:
                    logger.warning(
                        f"❌ Attempt {iteration} failed validation: {validation_feedback}"
                    )
                    improvement_guidance = validation_feedback

                    if iteration == max_iterations:
                        logger.warning(
                            f"Max iterations reached. Using last generated post with truncation if needed."
                        )
                        # Apply basic truncation if over 290 characters
                        if len(post_content) > 290:
                            post_content = post_content[:287] + "..."
                            logger.info(f"Truncated post to {len(post_content)} characters")
                        return post_content

            # Should not reach here, but just in case
            return post_content

        except Exception as e:
            error_msg = (
                f"Failed to generate Bluesky post for video {video_id}: {str(e)}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)
