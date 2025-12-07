#!/usr/bin/env python3
"""
Gradio Web App for Video Processing Pipeline.

Provides a web interface for:
- Downloading YouTube videos by video ID
- Transcribing videos with speaker diarization
- Generating LinkedIn posts
- Generating and posting Bluesky posts

Usage:
    python gradio_app.py

Environment Variables (loaded from .env file):
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
    BLUESKY_HANDLE, BLUESKY_PASSWORD
    OLLAMA_URL, OLLAMA_MODEL
"""

import ctypes
import os
import sys

# Fix cuDNN library conflict - preload venv's cuDNN before torch loads system cuDNN
# This MUST happen before any torch imports, hence the E402 suppressions below
_cudnn_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".venv/lib/python3.10/site-packages/nvidia/cudnn/lib",
)
if os.path.exists(_cudnn_path):
    _cudnn_lib = os.path.join(_cudnn_path, "libcudnn.so.9")
    if os.path.exists(_cudnn_lib):
        ctypes.CDLL(_cudnn_lib, mode=ctypes.RTLD_GLOBAL)

import tempfile  # noqa: E402
import threading  # noqa: E402
from collections import deque  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Optional  # noqa: E402

import gradio as gr  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from loguru import logger  # noqa: E402


class LogCapture:
    """Thread-safe log buffer for capturing loguru output."""

    def __init__(self, max_lines: int = 500):
        self._buffer: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def write(self, message: str) -> None:
        """Write a log message to the buffer."""
        with self._lock:
            # Strip trailing newline if present
            msg = message.rstrip("\n")
            if msg:
                self._buffer.append(msg)

    def get_logs(self) -> str:
        """Get all logs as a single string."""
        with self._lock:
            return "\n".join(self._buffer)

    def clear(self) -> None:
        """Clear the log buffer."""
        with self._lock:
            self._buffer.clear()


# Global log capture instance
log_capture = LogCapture()

from services.analysis_service import OllamaAnalysisService  # noqa: E402
from services.audio_service import AudioService  # noqa: E402
from services.bluesky_post_builder import BlueskyPostBuilder  # noqa: E402
from services.bluesky_service import BlueskyService  # noqa: E402
from services.minio_service import MinIOService  # noqa: E402
from services.transcription_service import PersonaTranscriptionService  # noqa: E402
from services.youtube_download_service import YouTubeDownloadService  # noqa: E402


@dataclass
class ProcessingResult:
    """Result of a processing step."""

    success: bool
    message: str
    data: Optional[str] = None


class GradioVideoProcessor:
    """Video processing service for Gradio interface."""

    def __init__(
        self,
        minio_service: MinIOService,
        download_service: YouTubeDownloadService,
        audio_service: AudioService,
        transcription_service: PersonaTranscriptionService,
        analysis_service: OllamaAnalysisService,
        bluesky_builder: BlueskyPostBuilder,
    ):
        self.minio = minio_service
        self.downloader = download_service
        self.audio = audio_service
        self.transcription = transcription_service
        self.analysis = analysis_service
        self.bluesky = bluesky_builder

    def download_video(self, video_id: str) -> ProcessingResult:
        """Download a YouTube video and save to MinIO."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        video_id = video_id.strip()
        logger.info(f"Downloading video: {video_id}")

        try:
            result = self.downloader.download_video(video_id=video_id)

            if result.get("skipped") and result.get("already_exists_in_minio"):
                return ProcessingResult(
                    success=True,
                    message=f"Video already exists in MinIO: {result.get('minio_video_path')}",
                    data=result.get("minio_video_path"),
                )

            minio_path = result.get("minio_video_path", "")
            return ProcessingResult(
                success=True,
                message=f"Video downloaded and uploaded to MinIO: {minio_path}",
                data=minio_path,
            )

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return ProcessingResult(success=False, message=f"Download failed: {e}")

    def transcribe_video(self, video_id: str) -> ProcessingResult:
        """Transcribe a video from MinIO."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        video_id = video_id.strip()
        folder = f"downloads/{video_id}"
        mp4_filename = f"{video_id}.mp4"
        txt_filename = f"{video_id}-transcription.txt"

        # Check if transcription already exists
        if self.minio.object_exists(folder, txt_filename):
            return ProcessingResult(
                success=True,
                message=f"Transcription already exists: {folder}/{txt_filename}",
                data=f"{folder}/{txt_filename}",
            )

        # Check if video exists
        if not self.minio.object_exists(folder, mp4_filename):
            return ProcessingResult(
                success=False,
                message=f"Video not found in MinIO: {folder}/{mp4_filename}",
            )

        logger.info(f"Transcribing video: {video_id}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_mp4_path = os.path.join(temp_dir, mp4_filename)

            # Download video from MinIO
            if not self.minio.retrieve_to_file(folder, mp4_filename, temp_mp4_path):
                return ProcessingResult(
                    success=False, message="Failed to download video from MinIO"
                )

            try:
                # Transcribe
                temp_output = self.transcription.transcribe_file(temp_mp4_path)

                # Upload transcription to MinIO
                with open(temp_output, "rb") as f:
                    transcription_data = f.read()

                transcription_path = f"{folder}/{txt_filename}"
                success = self.minio.save(
                    data=transcription_data,
                    filename=transcription_path,
                    content_type="text/plain",
                    metadata={
                        "source_file": mp4_filename,
                        "type": "persona_transcription",
                    },
                )

                if success:
                    return ProcessingResult(
                        success=True,
                        message=f"Transcription completed and uploaded: {transcription_path}",
                        data=transcription_path,
                    )
                return ProcessingResult(
                    success=False, message="Failed to upload transcription to MinIO"
                )

            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                return ProcessingResult(
                    success=False, message=f"Transcription failed: {e}"
                )

    def get_transcription(self, video_id: str) -> ProcessingResult:
        """Get transcription content from MinIO."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        video_id = video_id.strip()
        folder = f"downloads/{video_id}"
        txt_filename = f"{video_id}-transcription.txt"

        if not self.minio.object_exists(folder, txt_filename):
            return ProcessingResult(
                success=False,
                message=f"Transcription not found: {folder}/{txt_filename}",
            )

        data = self.minio.retrieve(folder, txt_filename)
        if data:
            return ProcessingResult(
                success=True,
                message="Transcription retrieved",
                data=data.decode("utf-8"),
            )
        return ProcessingResult(
            success=False, message="Failed to retrieve transcription"
        )

    async def generate_linkedin_post(self, video_id: str) -> ProcessingResult:
        """Generate a LinkedIn post from transcription."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        video_id = video_id.strip()
        folder = f"downloads/{video_id}"
        txt_filename = f"{video_id}-transcription.txt"
        linkedin_filename = f"{video_id}-linkedin.txt"

        # Check if LinkedIn post already exists
        if self.minio.object_exists(folder, linkedin_filename):
            data = self.minio.retrieve(folder, linkedin_filename)
            if data:
                return ProcessingResult(
                    success=True,
                    message="LinkedIn post already exists",
                    data=data.decode("utf-8"),
                )

        # Get transcription
        transcription_result = self.get_transcription(video_id)
        if not transcription_result.success:
            return transcription_result

        with tempfile.TemporaryDirectory() as temp_dir:
            # Write transcription to temp file
            temp_txt = os.path.join(temp_dir, txt_filename)
            with open(temp_txt, "w", encoding="utf-8") as f:
                f.write(transcription_result.data or "")

            try:
                linkedin_path = await self.analysis.generate_linkedin_post(
                    transcription_file=temp_txt,
                    video_id=video_id,
                )

                with open(linkedin_path, "r", encoding="utf-8") as f:
                    linkedin_content = f.read()

                # Upload to MinIO
                linkedin_object_path = f"{folder}/{linkedin_filename}"
                self.minio.save(
                    data=linkedin_content.encode("utf-8"),
                    filename=linkedin_object_path,
                    content_type="text/plain",
                    metadata={"source_file": txt_filename, "type": "linkedin_post"},
                )

                return ProcessingResult(
                    success=True,
                    message=f"LinkedIn post generated and saved to {linkedin_object_path}",
                    data=linkedin_content,
                )

            except Exception as e:
                logger.error(f"LinkedIn post generation failed: {e}")
                return ProcessingResult(
                    success=False, message=f"LinkedIn post generation failed: {e}"
                )

    async def generate_bluesky_post(self, video_id: str) -> ProcessingResult:
        """Generate a Bluesky post for review."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        video_id = video_id.strip()
        folder = f"downloads/{video_id}"
        txt_filename = f"{video_id}-transcription.txt"
        bluesky_filename = f"{video_id}-bluesky.txt"

        # Get transcription
        transcription_result = self.get_transcription(video_id)
        if not transcription_result.success:
            return transcription_result

        try:
            # Generate Bluesky post
            bluesky_content = await self.analysis.generate_bluesky_post(
                video_id=video_id,
                analysis_content=transcription_result.data or "",
            )

            # Save to MinIO
            bluesky_object_path = f"{folder}/{bluesky_filename}"
            self.minio.save(
                data=bluesky_content.encode("utf-8"),
                filename=bluesky_object_path,
                content_type="text/plain",
                metadata={"source_file": txt_filename, "type": "bluesky_post"},
            )

            return ProcessingResult(
                success=True,
                message="Bluesky post generated! Review and edit below, then click 'Post to Bluesky'.",
                data=bluesky_content,
            )

        except Exception as e:
            logger.error(f"Bluesky post generation failed: {e}")
            return ProcessingResult(
                success=False, message=f"Bluesky post generation failed: {e}"
            )

    async def publish_to_bluesky(
        self, video_id: str, post_content: str
    ) -> ProcessingResult:
        """Publish content to Bluesky."""
        if not video_id or not video_id.strip():
            return ProcessingResult(success=False, message="Video ID is required")

        if not post_content or not post_content.strip():
            return ProcessingResult(
                success=False, message="Post content is required. Generate a post first."
            )

        video_id = video_id.strip()
        post_content = post_content.strip()

        try:
            video_url = f"https://youtube.com/watch?v={video_id}"
            post_success = await self.bluesky.post_content_with_media(
                text=post_content,
                video_path=None,
                thumbnail_path=None,
                video_title=f"Video: {video_id}",
                youtube_url=video_url,
                use_youtube_facets=True,
            )

            if post_success:
                return ProcessingResult(
                    success=True,
                    message="Bluesky post published successfully!",
                    data=post_content,
                )
            return ProcessingResult(
                success=False,
                message="Failed to publish to Bluesky",
                data=post_content,
            )

        except Exception as e:
            logger.error(f"Bluesky publish failed: {e}")
            return ProcessingResult(success=False, message=f"Bluesky publish failed: {e}")


def create_services() -> GradioVideoProcessor:
    """Create and wire up all services with dependency injection."""
    load_dotenv()

    # Validate required environment variables
    required_vars = [
        "MINIO_ENDPOINT",
        "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY",
        "MINIO_BUCKET",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # MinIO configuration
    secure = os.getenv("MINIO_SECURE", "false").lower() in ("true", "1", "yes", "on")
    minio_service = MinIOService(
        endpoint=os.getenv("MINIO_ENDPOINT", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        bucket_name=os.getenv("MINIO_BUCKET", ""),
        secure=secure,
        region=os.getenv("MINIO_REGION"),
    )
    logger.success("MinIO service initialized")

    # Download service
    download_service = YouTubeDownloadService(
        minio_service=minio_service,
        default_output_path="downloads",
        minio_folder="downloads",
        cleanup_local=True,
    )

    # Audio service
    audio_service = AudioService(sample_rate=16000, channels=1)

    # Transcription service
    transcription_service = PersonaTranscriptionService(
        default_model_size="small",
        device="cuda",
        compute_type="float16",
        batch_size=16,
    )
    logger.success("Transcription service initialized")

    # Analysis service
    analysis_service = OllamaAnalysisService(
        ollama_url=os.getenv("OLLAMA_URL", "http://nvda:30434"),
        model_name=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        temperature=0.7,
        max_tokens=200000,
    )

    # Bluesky services
    bluesky_handle = os.getenv("BLUESKY_HANDLE")
    bluesky_password = os.getenv("BLUESKY_PASSWORD")

    if not bluesky_handle or not bluesky_password:
        raise ValueError("Missing BLUESKY_HANDLE or BLUESKY_PASSWORD")

    bluesky_service = BlueskyService(
        handle=bluesky_handle,
        password=bluesky_password,
        service_url=os.getenv("BLUESKY_SERVICE_URL", "https://bsky.social"),
    )
    bluesky_builder = BlueskyPostBuilder(bluesky_service=bluesky_service)
    logger.success("Bluesky service initialized")

    return GradioVideoProcessor(
        minio_service=minio_service,
        download_service=download_service,
        audio_service=audio_service,
        transcription_service=transcription_service,
        analysis_service=analysis_service,
        bluesky_builder=bluesky_builder,
    )


def create_gradio_app(processor: GradioVideoProcessor) -> gr.Blocks:
    """Create the Gradio interface."""

    def download_video(video_id: str) -> str:
        result = processor.download_video(video_id)
        return f"{'✅' if result.success else '❌'} {result.message}"

    def transcribe_video(video_id: str) -> str:
        result = processor.transcribe_video(video_id)
        return f"{'✅' if result.success else '❌'} {result.message}"

    def get_transcription(video_id: str) -> str:
        result = processor.get_transcription(video_id)
        if result.success:
            return result.data or ""
        return f"❌ {result.message}"

    async def generate_linkedin(video_id: str) -> str:
        result = await processor.generate_linkedin_post(video_id)
        if result.success:
            return result.data or ""
        return f"❌ {result.message}"

    async def generate_bluesky(video_id: str) -> tuple[str, str]:
        result = await processor.generate_bluesky_post(video_id)
        status = f"{'✅' if result.success else '❌'} {result.message}"
        content = result.data or ""
        return status, content

    async def publish_bluesky(video_id: str, post_content: str) -> str:
        result = await processor.publish_to_bluesky(video_id, post_content)
        return f"{'✅' if result.success else '❌'} {result.message}"

    def get_logs() -> str:
        return log_capture.get_logs()

    def clear_logs() -> str:
        log_capture.clear()
        return ""

    with gr.Blocks(title="Video Processing Pipeline") as app:
        gr.Markdown("# Video Processing Pipeline")
        gr.Markdown(
            "Download, transcribe, and generate social media posts from YouTube videos."
        )

        with gr.Row():
            video_id_input = gr.Textbox(
                label="YouTube Video ID",
                placeholder="e.g., dQw4w9WgXcQ",
                scale=3,
            )

        with gr.Tab("1. Download"):
            gr.Markdown("Download a YouTube video and save to MinIO storage.")
            download_btn = gr.Button("Download Video", variant="primary")
            download_output = gr.Textbox(label="Result", lines=3)
            download_btn.click(
                download_video, inputs=video_id_input, outputs=download_output
            )

        with gr.Tab("2. Transcribe"):
            gr.Markdown("Transcribe the video with speaker diarization.")
            transcribe_btn = gr.Button("Transcribe Video", variant="primary")
            transcribe_output = gr.Textbox(label="Result", lines=3)
            transcribe_btn.click(
                transcribe_video, inputs=video_id_input, outputs=transcribe_output
            )

            gr.Markdown("### View Transcription")
            view_btn = gr.Button("View Transcription")
            transcription_display = gr.Textbox(label="Transcription Content", lines=20)
            view_btn.click(
                get_transcription, inputs=video_id_input, outputs=transcription_display
            )

        with gr.Tab("3. LinkedIn Post"):
            gr.Markdown("Generate a LinkedIn post from the transcription.")
            linkedin_btn = gr.Button("Generate LinkedIn Post", variant="primary")
            linkedin_output = gr.Textbox(label="LinkedIn Post", lines=15)
            linkedin_btn.click(
                generate_linkedin, inputs=video_id_input, outputs=linkedin_output
            )

        with gr.Tab("4. Bluesky Post"):
            gr.Markdown("Generate a Bluesky post, review/edit it, then publish.")

            with gr.Row():
                generate_bluesky_btn = gr.Button(
                    "Generate Bluesky Post", variant="primary"
                )

            bluesky_status = gr.Textbox(label="Status", lines=2, interactive=False)

            gr.Markdown("### Review & Edit Post")
            bluesky_content = gr.Textbox(
                label="Post Content (edit before publishing)",
                lines=10,
                placeholder="Generated post will appear here. You can edit it before publishing.",
                interactive=True,
            )

            with gr.Row():
                publish_bluesky_btn = gr.Button("Post to Bluesky", variant="stop")

            publish_status = gr.Textbox(label="Publish Result", lines=2, interactive=False)

            generate_bluesky_btn.click(
                generate_bluesky,
                inputs=video_id_input,
                outputs=[bluesky_status, bluesky_content],
            )
            publish_bluesky_btn.click(
                publish_bluesky,
                inputs=[video_id_input, bluesky_content],
                outputs=publish_status,
            )

        # Real-time log panel
        with gr.Accordion("Logs", open=True):
            with gr.Row():
                refresh_logs_btn = gr.Button("Refresh Logs", size="sm")
                clear_logs_btn = gr.Button("Clear Logs", size="sm", variant="secondary")
                auto_refresh = gr.Checkbox(
                    label="Auto-refresh (every 1s)", value=True, scale=0
                )

            log_output = gr.Textbox(
                label="Application Logs",
                lines=15,
                max_lines=30,
                interactive=False,
                autoscroll=True,
            )

            # Manual refresh button
            refresh_logs_btn.click(get_logs, outputs=log_output)

            # Clear logs button
            clear_logs_btn.click(clear_logs, outputs=log_output)

            # Auto-refresh using a timer that checks the checkbox state
            timer = gr.Timer(value=1.0, active=True)

            def conditional_refresh(auto: bool) -> str:
                if auto:
                    return log_capture.get_logs()
                return gr.update()

            timer.tick(conditional_refresh, inputs=auto_refresh, outputs=log_output)

    return app


def main() -> None:
    """Main entry point."""
    logger.remove()

    # Add stderr handler for terminal output
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        colorize=True,
    )

    # Add log capture handler for Gradio UI
    logger.add(
        log_capture.write,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level="INFO",
        colorize=False,
    )

    logger.info("Initializing services...")
    processor = create_services()

    logger.info("Creating Gradio app...")
    app = create_gradio_app(processor)

    logger.info("Launching Gradio app...")
    app.launch(server_name="0.0.0.0", server_port=7860, share=True)


if __name__ == "__main__":
    main()
