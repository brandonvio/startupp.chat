from typing import Optional, List, Dict
from faster_whisper import WhisperModel
from loguru import logger
import os
import torch
import whisperx
import logging
import gc
import pandas as pd
from dotenv import load_dotenv
import warnings
from pyannote.audio.utils.reproducibility import ReproducibilityWarning

warnings.filterwarnings("ignore", message=".*torchaudio.*deprecated.*")
warnings.filterwarnings("ignore", message=".*TorchCodec.*")
warnings.filterwarnings("ignore", message=".*pyannote.*")
warnings.filterwarnings("ignore", category=ReproducibilityWarning)
os.environ["PYTORCH_LIGHTNING_QUIET"] = "1"
os.environ["PYANNOTE_VERBOSITY"] = "0"

# Suppress lightning/pytorch logging
logging.getLogger("pytorch_lightning").setLevel(logging.ERROR)
logging.getLogger("lightning").setLevel(logging.ERROR)
logging.getLogger("whisperx").setLevel(logging.ERROR)

# Set environment variables to reduce noise
os.environ["PYTORCH_LIGHTNING_QUIET"] = "1"


class TranscriptionService:
    """Service for transcribing audio/video files using Whisper."""

    def __init__(
        self,
        default_model_size: str = "medium",
        device: str = "cuda",
        compute_type: str = "float16",
        beam_size: int = 5,
    ):
        self.default_model_size = default_model_size
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size

        # Load model immediately during initialization
        logger.info(f"Loading Whisper model: {default_model_size}")
        self._model = WhisperModel(
            default_model_size, device=self.device, compute_type=self.compute_type
        )
        logger.success(f"Whisper model {default_model_size} loaded successfully")

    def _get_model(self) -> WhisperModel:
        """Get the loaded Whisper model instance."""
        return self._model

    def transcribe_file(
        self,
        file_path: str,
        video_id: Optional[str] = None,
    ) -> str:
        """
        Transcribe an audio/video file using Whisper.

        Args:
            file_path (str): Path to the audio/video file to transcribe.
            video_id (str, optional): Video ID to use for output filename. If not provided, extracts from file_path.

        Returns:
            str: Path to the output transcription file.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            Exception: If transcription fails.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.lower().endswith(
            (".mp4", ".mp3", ".wav", ".m4a", ".avi", ".mov")
        ):
            raise ValueError(f"Unsupported file format: {file_path}")

        try:
            model = self._get_model()
            logger.info(f"Starting transcription of: {file_path}")

            segments, info = model.transcribe(file_path, beam_size=self.beam_size)

            # Generate output filename using video ID
            if video_id:
                output_file = f"{os.path.dirname(file_path) or '.'}/{video_id}.txt"
            else:
                # Extract video ID from filename if not provided
                base_name = os.path.basename(file_path)
                video_id_from_file = os.path.splitext(base_name)[0]
                output_file = (
                    f"{os.path.dirname(file_path) or '.'}/{video_id_from_file}.txt"
                )

            # Write transcription to text file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"Transcription of: {file_path}\n")
                f.write(
                    f"Detected language: {info.language} (probability: {info.language_probability:.2f})\n"
                )
                f.write("=" * 50 + "\n\n")

                for segment in segments:
                    timestamp = f"[{segment.start:.2f}s -> {segment.end:.2f}s]"
                    f.write(f"{timestamp} {segment.text}\n")
                    logger.debug(f"{timestamp} {segment.text}")

            logger.success(f"Transcription completed and saved to: {output_file}")
            logger.info(
                f"Detected language: {info.language} (probability: {info.language_probability:.2f})"
            )

            return output_file

        except Exception as e:
            logger.error(f"Transcription failed for {file_path}: {str(e)}")
            raise Exception(f"Transcription failed for {file_path}: {str(e)}")

    def get_transcription_info(self, file_path: str) -> dict:
        """
        Get transcription information without saving to file.

        Args:
            file_path (str): Path to the audio/video file.

        Returns:
            dict: Dictionary containing transcription info and segments.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            model = self._get_model()
            segments, info = model.transcribe(file_path, beam_size=self.beam_size)

            # Convert segments to list for easier handling
            segments_list = []
            for segment in segments:
                segments_list.append(
                    {"start": segment.start, "end": segment.end, "text": segment.text}
                )

            return {
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": segments_list,
            }

        except Exception as e:
            logger.error(f"Failed to get transcription info for {file_path}: {str(e)}")
            raise Exception(
                f"Failed to get transcription info for {file_path}: {str(e)}"
            )


class PersonaTranscriptionService:
    def __init__(
        self,
        default_model_size: str = "medium",
        device: str = "cuda",
        compute_type: str = "float16",
        batch_size: int = 16,
        hf_token: Optional[str] = None,
    ):
        # STRICT GPU-ONLY MODE - NO FALLBACKS
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available. GPU is required for PersonaTranscriptionService."
            )

        self.default_model_size = default_model_size
        self.device = device
        self.compute_type = compute_type
        self.batch_size = batch_size

        # Load environment variables if not provided
        if hf_token is None:
            load_dotenv()
            self.hf_token = os.getenv("HF_TOKEN")
        else:
            self.hf_token = hf_token

        # Set environment variables to help with cuDNN issues
        os.environ["CUDNN_DETERMINISTIC"] = "1"
        os.environ["CUDNN_BENCHMARK"] = "0"

        logger.info(f"Using device: {self.device}")
        logger.info(f"Compute type: {self.compute_type}")
        logger.info(f"CUDA devices available: {torch.cuda.device_count()}")
        logger.info(f"Current CUDA device: {torch.cuda.current_device()}")
        logger.info(f"CUDA device name: {torch.cuda.get_device_name()}")

        # Pre-load WhisperX model during initialization
        logger.info(f"Loading WhisperX model: {default_model_size}")
        try:
            # Test CUDA operations first
            test_tensor = torch.randn(10, 10).cuda()
            logger.debug(
                f"✓ CUDA tensor creation successful on device: {test_tensor.device}"
            )
            del test_tensor
            torch.cuda.empty_cache()

            # Load WhisperX model - MUST be on GPU
            self._whisperx_model = whisperx.load_model(
                default_model_size, self.device, compute_type=self.compute_type
            )
            logger.success("✓ WhisperX model loaded successfully on GPU during init")

        except Exception as e:
            raise RuntimeError(f"Failed to load WhisperX model on GPU during init: {e}")

        # Pre-load alignment models for common languages
        self._align_models = {}

        # Pre-load diarization model during initialization
        logger.info("Loading speaker diarization model...")
        try:
            # Try WhisperX DiarizationPipeline first
            try:
                self._diarization_model = whisperx.DiarizationPipeline(
                    use_auth_token=self.hf_token, device=self.device
                )
                logger.success("✓ WhisperX DiarizationPipeline loaded successfully")
            except AttributeError:
                # Fall back to pyannote Pipeline
                from pyannote.audio import Pipeline

                self._diarization_model = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1", use_auth_token=self.hf_token
                )
                self._diarization_model.to(torch.device(self.device))
                logger.success("✓ PyAnnote diarization pipeline loaded successfully")

        except Exception as e:
            raise RuntimeError(f"Failed to load diarization model during init: {e}")

    def _transcribe_and_diarize_whisperx(
        self, audio_path: str, language: str = "auto"
    ) -> List[Dict]:
        """
        Transcribes an audio file and performs speaker diarization using WhisperX.
        Uses the CORRECT WhisperX API approach - no hacks.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found at: {audio_path}")

        logger.info("Step 1: Loading WhisperX model on GPU...")

        # Use pre-loaded WhisperX model
        model = self._whisperx_model
        logger.debug("Using pre-loaded WhisperX model")

        # 2. Load audio and transcribe
        logger.info("Step 2: Loading and transcribing audio on GPU...")
        try:
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, batch_size=self.batch_size)
            logger.success("✓ Audio transcribed successfully on GPU")
        except Exception as e:
            raise RuntimeError(f"Failed to transcribe audio on GPU: {e}")

        # Auto-detect language if not specified
        if language == "auto":
            language = result["language"]
            logger.info(f"Detected language: {language}")

        # 3. Align whisper output for better timestamp accuracy
        logger.info("Step 3: Aligning timestamps on GPU...")
        try:
            # Load or reuse alignment model for this language
            if language not in self._align_models:
                logger.debug(f"Loading alignment model for language: {language}")
                model_a, metadata = whisperx.load_align_model(
                    language_code=language, device=self.device
                )
                self._align_models[language] = (model_a, metadata)
            else:
                logger.debug(f"Reusing cached alignment model for language: {language}")
                model_a, metadata = self._align_models[language]

            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False,
            )
            logger.success("✓ Timestamp alignment completed on GPU")

        except Exception as e:
            raise RuntimeError(f"Failed to align timestamps on GPU: {e}")

        # 4. Speaker Diarization using pre-loaded model
        logger.info("Step 4: Performing speaker diarization on GPU...")
        try:
            # Use pre-loaded diarization model
            if hasattr(self._diarization_model, "__call__"):
                # WhisperX DiarizationPipeline or PyAnnote Pipeline
                if "DiarizationPipeline" in str(type(self._diarization_model)):
                    diarize_segments = self._diarization_model(audio)
                else:
                    # PyAnnote pipeline - needs audio file path
                    diarize_segments = self._diarization_model(audio_path)
            else:
                raise RuntimeError("Invalid diarization model loaded")

            logger.success(
                "✓ Speaker diarization completed on GPU using pre-loaded model"
            )

        except Exception as e:
            raise RuntimeError(f"Failed to perform diarization on GPU: {e}")

        # 5. Assign speaker labels - FIXED FOR WHISPERX 3.4.2
        logger.info("Step 5: Assigning speakers to segments...")
        try:
            # Fix for WhisperX 3.4.2 bug: convert pyannote Annotation to DataFrame
            def annotation_to_df(annotation):
                segments = []
                for segment, _, speaker in annotation.itertracks(yield_label=True):
                    segments.append(
                        {"start": segment.start, "end": segment.end, "speaker": speaker}
                    )
                return pd.DataFrame(segments)

            # Convert annotation to DataFrame format expected by assign_word_speakers
            diarization_df = annotation_to_df(diarize_segments)
            logger.debug(
                f"  - Converted {len(diarization_df)} speaker segments to DataFrame"
            )

            # Now assign speakers using the DataFrame
            result = whisperx.assign_word_speakers(diarization_df, result)
            logger.success("✓ Speaker assignment completed")

            # Verify assignment worked
            speakers_found = set()
            for segment in result["segments"]:
                speaker = segment.get("speaker")
                if speaker and speaker != "UNKNOWN":
                    speakers_found.add(speaker)

            logger.success(
                f"✓ Successfully assigned {len(speakers_found)} speakers: {speakers_found}"
            )

        except Exception as e:
            raise RuntimeError(f"Failed to assign speakers: {e}")

        # Memory cleanup (keeping models loaded for reuse)
        try:
            gc.collect()
            torch.cuda.empty_cache()
            logger.debug("✓ GPU memory cleaned up successfully (models retained)")
        except Exception as e:
            logger.warning(f"Warning: GPU memory cleanup had issues: {e}")

        # 6. Format the final output
        final_output = []
        for segment in result["segments"]:
            # Get speaker (may be None for some segments)
            speaker = segment.get("speaker", "UNKNOWN")

            final_output.append(
                {
                    "speaker": speaker,
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                }
            )

        logger.success("✓ Processing complete - ALL OPERATIONS ON GPU")
        return final_output

    def transcribe_file(
        self,
        file_path: str,
        video_id: Optional[str] = None,
    ) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.lower().endswith(
            (".mp4", ".mp3", ".wav", ".m4a", ".avi", ".mov")
        ):
            raise ValueError(f"Unsupported file format: {file_path}")

        try:
            logger.info(f"Starting persona transcription of: {file_path}")

            # Use WhisperX implementation for transcription and diarization
            transcription_with_speakers = self._transcribe_and_diarize_whisperx(
                file_path, language="auto"
            )

            # Generate output filename
            if video_id:
                output_file = f"{os.path.dirname(file_path) or '.'}/{video_id}.txt"
            else:
                base_name = os.path.basename(file_path)
                video_id_from_file = os.path.splitext(base_name)[0]
                output_file = (
                    f"{os.path.dirname(file_path) or '.'}/{video_id_from_file}.txt"
                )

            # Get unique speakers for summary
            unique_speakers = set(
                seg["speaker"]
                for seg in transcription_with_speakers
                if seg["speaker"] != "UNKNOWN"
            )

            # Write to file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"Persona Transcription of: {file_path}\n")
                f.write(f"Identified speakers: {', '.join(sorted(unique_speakers))}\n")
                f.write("=" * 50 + "\n\n")

                current_speaker = None
                for segment in transcription_with_speakers:
                    # Add a separator when speaker changes
                    if segment["speaker"] != current_speaker:
                        if current_speaker is not None:
                            f.write("\n")
                        f.write(f"--- {segment['speaker']} ---\n")
                        current_speaker = segment["speaker"]

                    timestamp = f"[{segment['start']:.2f}s -> {segment['end']:.2f}s]"
                    f.write(f"{timestamp} {segment['text']}\n")
                    logger.debug(
                        f"{timestamp} [{segment['speaker']}] {segment['text']}"
                    )

            logger.success(
                f"Persona transcription completed and saved to: {output_file}"
            )
            logger.info(f"Identified {len(unique_speakers)} unique speakers")

            return output_file

        except Exception as e:
            logger.error(f"Persona transcription failed for {file_path}: {str(e)}")
            raise Exception(f"Persona transcription failed for {file_path}: {str(e)}")
