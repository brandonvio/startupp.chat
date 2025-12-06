from typing import Optional
from loguru import logger
from .youtube_download_service import YouTubeDownloadService
from .transcription_service import TranscriptionService, PersonaTranscriptionService
from .audio_service import AudioService
from .analysis_service import OllamaAnalysisService
from .config_service import ConfigService
from .minio_service import MinIOService


class YouTubeAnalyzer:
    """
    Main application class that orchestrates YouTube video download and transcription.
    """

    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        minio_service: Optional[MinIOService] = None,
    ):
        """
        Initialize the YouTube analyzer with default services.

        Args:
            config_service: Optional configuration service. If None, creates a default one.
            minio_service: Optional MinIO service for uploading prepared videos.
        """
        self.config_service = config_service or ConfigService()
        self.minio_service = minio_service

        # Initialize services directly with configuration
        download_config = self.config_service.get_download_config()
        transcription_config = self.config_service.get_transcription_config()
        analysis_config = self.config_service.get_analysis_config()

        self.download_service = YouTubeDownloadService(
            default_output_path=download_config["default_output_path"],
            default_resolution="best",
        )

        self.transcription_service = TranscriptionService(
            default_model_size=transcription_config["default_model_size"],
            device=transcription_config["device"],
            compute_type=transcription_config["compute_type"],
            beam_size=transcription_config["beam_size"],
        )

        self.persona_transcription_service = PersonaTranscriptionService(
            default_model_size=transcription_config["default_model_size"],
            device=transcription_config["device"],
            compute_type=transcription_config["compute_type"],
            beam_size=transcription_config["beam_size"],
        )

        self.audio_service = AudioService(sample_rate=16000, channels=1)

        self.analysis_service = OllamaAnalysisService(
            ollama_url=analysis_config["ollama_url"],
            model_name=analysis_config["model_name"],
            temperature=analysis_config["temperature"],
            max_tokens=analysis_config["max_tokens"],
        )

        logger.info("YouTube analyzer initialized with all services")

    async def analyze_youtube_video(
        self,
        video_id: str,
        output_path: str = ".",
        resolution: str = "best",
        model_size: str = "medium",
        download_only: bool = False,
        transcribe_only: bool = False,
        use_persona_transcription: bool = False,
        enable_analysis: bool = True,
        enable_linkedin_post: bool = True,
    ) -> dict:
        """
        Complete workflow: download YouTube video and transcribe it.

        Args:
            video_id (str): YouTube video ID to analyze.
            output_path (str): Directory to save downloaded video and transcription.
            resolution (str): Video quality for download.
            model_size (str): Whisper model size for transcription.
            download_only (bool): If True, only download the video.
            transcribe_only (bool): If True, only transcribe (assumes video exists).
            use_persona_transcription (bool): If True, use PersonaTranscriptionService for speaker identification.
            enable_analysis (bool): If True, generate analysis summary using Ollama.
            enable_linkedin_post (bool): If True, generate LinkedIn post using Ollama.

        Returns:
            dict: Analysis results containing file paths and metadata.
        """
        result = {
            "video_id": video_id,
            "video_file": None,
            "audio_file": None,
            "transcription_file": None,
            "analysis_file": None,
            "linkedin_post_file": None,
            "language": None,
            "language_probability": None,
            "success": False,
            "error": None,
        }

        try:
            # Download video (unless transcribe_only is True)
            if not transcribe_only:
                logger.info(f"Starting analysis of YouTube video: {video_id}")
                video_file = self.download_service.download_video(
                    video_id, output_path, resolution
                )
                result["video_file"] = video_file
                logger.success(f"Video downloaded successfully: {video_file}")

                # Upload video to MinIO if service is available
                if self.minio_service:
                    await self._upload_video_to_minio(video_file, video_id, output_path)
            else:
                # For transcribe_only, construct expected filename
                video_file = f"{video_id}.mp4"
                if output_path != ".":
                    video_file = f"{output_path}/{video_file}"
                result["video_file"] = video_file

            # Extract audio from video (unless download_only is True)
            if not download_only:
                logger.info("Extracting audio from video file")
                audio_file = self.audio_service.extract_audio(video_file)
                result["audio_file"] = audio_file
                logger.success(f"Audio extracted: {audio_file}")

                # Choose transcription service based on parameter
                if use_persona_transcription and self.persona_transcription_service:
                    logger.info(
                        "Using persona transcription service with speaker identification"
                    )
                    transcription_file = (
                        self.persona_transcription_service.transcribe_file(
                            audio_file, model_size, video_id
                        )
                    )
                    transcription_info = (
                        self.persona_transcription_service.get_transcription_info(
                            audio_file
                        )
                    )
                elif (
                    use_persona_transcription and not self.persona_transcription_service
                ):
                    logger.warning(
                        "Persona transcription requested but service not available, using default transcription"
                    )
                    transcription_file = self.transcription_service.transcribe_file(
                        audio_file, model_size, video_id
                    )
                    transcription_info = (
                        self.transcription_service.get_transcription_info(audio_file)
                    )
                else:
                    logger.info("Using standard transcription service")
                    transcription_file = self.transcription_service.transcribe_file(
                        audio_file, model_size, video_id
                    )
                    transcription_info = (
                        self.transcription_service.get_transcription_info(audio_file)
                    )

                result["transcription_file"] = transcription_file
                result["language"] = transcription_info["language"]
                result["language_probability"] = transcription_info[
                    "language_probability"
                ]

                logger.success(f"Transcription completed: {transcription_file}")

                # Generate analysis if enabled and service is available
                if enable_analysis and self.analysis_service:
                    try:
                        logger.info("Starting analysis generation using Ollama")
                        analysis_file = (
                            await self.analysis_service.analyze_transcription(
                                transcription_file, video_id
                            )
                        )
                        result["analysis_file"] = analysis_file
                        logger.success(f"Analysis completed: {analysis_file}")
                    except Exception as analysis_error:
                        logger.warning(
                            f"Analysis generation failed: {str(analysis_error)}"
                        )
                        # Don't fail the entire process if just analysis fails
                        result["analysis_file"] = None
                elif enable_analysis and not self.analysis_service:
                    logger.warning(
                        "Analysis requested but no analysis service available"
                    )

                # Generate LinkedIn post if enabled and service is available
                if enable_linkedin_post and self.analysis_service:
                    try:
                        logger.info("Starting LinkedIn post generation using Ollama")
                        linkedin_post_file = (
                            await self.analysis_service.generate_linkedin_post(
                                transcription_file, video_id
                            )
                        )
                        result["linkedin_post_file"] = linkedin_post_file
                        logger.success(f"LinkedIn post completed: {linkedin_post_file}")
                    except Exception as linkedin_error:
                        logger.warning(
                            f"LinkedIn post generation failed: {str(linkedin_error)}"
                        )
                        # Don't fail the entire process if just LinkedIn post fails
                        result["linkedin_post_file"] = None
                elif enable_linkedin_post and not self.analysis_service:
                    logger.warning(
                        "LinkedIn post requested but no analysis service available"
                    )

            result["success"] = True
            logger.success(f"Analysis completed successfully for video: {video_id}")

        except Exception as e:
            error_msg = f"Analysis failed for video {video_id}: {str(e)}"
            result["error"] = error_msg
            logger.error(error_msg)

        return result

    def download_video(
        self, video_id: str, output_path: str = ".", resolution: str = "best"
    ) -> str:
        """
        Download a YouTube video only.

        Args:
            video_id (str): YouTube video ID.
            output_path (str): Directory to save the video.
            resolution (str): Video quality.

        Returns:
            str: Path to downloaded video file.
        """
        return self.download_service.download_video(video_id, output_path, resolution)

    def transcribe_file(
        self, file_path: str, model_size: str = "medium", video_id: Optional[str] = None
    ) -> str:
        """
        Transcribe an existing audio/video file.

        Args:
            file_path (str): Path to the file to transcribe.
            model_size (str): Whisper model size.
            video_id (str, optional): Video ID to use for output filename.

        Returns:
            str: Path to transcription output file.
        """
        return self.transcription_service.transcribe_file(
            file_path, model_size, video_id
        )

    def get_video_info(self, video_id: str) -> dict:
        """
        Get YouTube video information without downloading.

        Args:
            video_id (str): YouTube video ID.

        Returns:
            dict: Video metadata.
        """
        return self.download_service.get_video_info(video_id)

    def get_transcription_info(self, file_path: str) -> dict:
        """
        Get transcription information without saving to file.

        Args:
            file_path (str): Path to audio/video file.

        Returns:
            dict: Transcription metadata and segments.
        """
        return self.transcription_service.get_transcription_info(file_path)

    async def _upload_video_to_minio(
        self, video_file: str, video_id: str, output_path: str
    ) -> bool:
        """
        Upload the downloaded video file to MinIO.

        Args:
            video_file: Path to the downloaded video file
            video_id: YouTube video ID
            output_path: Local output directory path

        Returns:
            bool: True if upload successful, False otherwise
        """
        try:
            import os

            logger.info(f"Uploading video to MinIO: {video_file}")

            # Determine the MinIO folder path based on output_path
            if output_path == "." or output_path == "":
                folder = "downloads"  # Default folder for videos
            else:
                # Use the output_path as the folder, but ensure it's clean
                folder = output_path.strip("/")
                if not folder:
                    folder = "downloads"

            # Get file info for metadata
            file_size = os.path.getsize(video_file)
            filename = f"{video_id}.mp4"

            # Create metadata
            metadata = {
                "video_id": video_id,
                "source": "youtube",
                "original_filename": os.path.basename(video_file),
                "content_type": "video/mp4",
            }

            # Upload the file
            success = self.minio_service.save_file(
                file_path=video_file,
                folder=folder,
                filename=filename,
                metadata=metadata,
            )

            if success:
                minio_path = f"{folder}/{filename}" if folder else filename
                logger.success(
                    f"Video uploaded to MinIO: {minio_path} ({file_size:,} bytes)"
                )
            else:
                logger.error(f"Failed to upload video to MinIO: {video_file}")

            return success

        except Exception as e:
            logger.error(f"Error uploading video to MinIO: {type(e).__name__}: {e}")
            return False
