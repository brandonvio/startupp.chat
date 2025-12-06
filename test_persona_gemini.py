import whisperx
import gc
import torch
import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

# STRICT GPU-ONLY MODE - NO FALLBACKS
if not torch.cuda.is_available():
    raise RuntimeError("CUDA is not available. GPU is required for this script.")

DEVICE = "cuda"
COMPUTE_TYPE = "float16"
BATCH_SIZE = 16

print(f"Using device: {DEVICE}")
print(f"Compute type: {COMPUTE_TYPE}")
print(f"CUDA devices available: {torch.cuda.device_count()}")
print(f"Current CUDA device: {torch.cuda.current_device()}")
print(f"CUDA device name: {torch.cuda.get_device_name()}")

# Set environment variables to potentially help with cuDNN issues
os.environ["CUDNN_DETERMINISTIC"] = "1"
os.environ["CUDNN_BENCHMARK"] = "0"


def transcribe_and_diarize_whisperx(audio_path: str, language: str = "en"):
    """
    Transcribes an audio file and performs speaker diarization using WhisperX.
    Uses the CORRECT WhisperX API approach - no hacks.

    Args:
        audio_path (str): Path to the audio file
        language (str): Language code (e.g., "en", "es", "fr"). Use "auto" for auto-detection.

    Returns:
        list: List of segments with speaker labels, timestamps, and text
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at: {audio_path}")

    print("Step 1: Loading WhisperX model on GPU...")

    # Force GPU usage - fail if it doesn't work
    try:
        # Test CUDA operations first
        test_tensor = torch.randn(10, 10).cuda()
        print(f"✓ CUDA tensor creation successful on device: {test_tensor.device}")
        del test_tensor
        torch.cuda.empty_cache()

        # 1. Load WhisperX model - MUST be on GPU
        model = whisperx.load_model("medium", DEVICE, compute_type=COMPUTE_TYPE)
        print("✓ WhisperX model loaded successfully on GPU")

    except Exception as e:
        raise RuntimeError(f"Failed to load model on GPU: {e}")

    # 2. Load audio and transcribe
    print("Step 2: Loading and transcribing audio on GPU...")
    try:
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=BATCH_SIZE)
        print("✓ Audio transcribed successfully on GPU")
    except Exception as e:
        raise RuntimeError(f"Failed to transcribe audio on GPU: {e}")

    # Auto-detect language if not specified
    if language == "auto":
        language = result["language"]
        print(f"Detected language: {language}")

    # 3. Align whisper output for better timestamp accuracy
    print("Step 3: Aligning timestamps on GPU...")
    try:
        model_a, metadata = whisperx.load_align_model(
            language_code=language, device=DEVICE
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            DEVICE,
            return_char_alignments=False,
        )
        print("✓ Timestamp alignment completed on GPU")

        # Memory cleanup after alignment
        del model_a
        gc.collect()
        torch.cuda.empty_cache()

    except Exception as e:
        raise RuntimeError(f"Failed to align timestamps on GPU: {e}")

    # 4. Speaker Diarization - THE CORRECT WAY
    print("Step 4: Performing speaker diarization on GPU...")
    try:
        # Load diarization model - this is the correct WhisperX approach
        diarize_model = whisperx.DiarizationPipeline(
            use_auth_token=HF_TOKEN, device=DEVICE
        )
        diarize_segments = diarize_model(audio)
        print("✓ Speaker diarization completed on GPU")

    except AttributeError:
        # If DiarizationPipeline doesn't exist, try the newer API
        print("  - Trying alternative diarization API...")
        try:
            from pyannote.audio import Pipeline

            diarize_model = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", use_auth_token=HF_TOKEN
            )
            diarize_model.to(torch.device(DEVICE))

            # For pyannote, we need to pass the audio file path
            diarize_segments = diarize_model(audio_path)
            print("✓ Speaker diarization completed using pyannote directly")

        except Exception as e:
            raise RuntimeError(f"Failed to perform diarization: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to perform diarization on GPU: {e}")

    # 5. Assign speaker labels - FIXED FOR WHISPERX 3.4.2
    print("Step 5: Assigning speakers to segments...")
    try:
        # Fix for WhisperX 3.4.2 bug: convert pyannote Annotation to DataFrame
        import pandas as pd

        def annotation_to_df(annotation):
            segments = []
            for segment, _, speaker in annotation.itertracks(yield_label=True):
                segments.append(
                    {"start": segment.start, "end": segment.end, "speaker": speaker}
                )
            return pd.DataFrame(segments)

        # Convert annotation to DataFrame format expected by assign_word_speakers
        diarization_df = annotation_to_df(diarize_segments)
        print(f"  - Converted {len(diarization_df)} speaker segments to DataFrame")

        # Now assign speakers using the DataFrame
        result = whisperx.assign_word_speakers(diarization_df, result)
        print("✓ Speaker assignment completed")

        # Verify assignment worked
        speakers_found = set()
        for segment in result["segments"]:
            speaker = segment.get("speaker")
            if speaker and speaker != "UNKNOWN":
                speakers_found.add(speaker)

        print(
            f"✓ Successfully assigned {len(speakers_found)} speakers: {speakers_found}"
        )

    except Exception as e:
        raise RuntimeError(f"Failed to assign speakers: {e}")

    # Memory cleanup
    try:
        del model, diarize_model
        gc.collect()
        torch.cuda.empty_cache()
        print("✓ GPU memory cleaned up successfully")
    except Exception as e:
        print(f"Warning: GPU memory cleanup had issues: {e}")

    # 6. Format the final output
    final_output = []
    for segment in result["segments"]:
        # Get speaker (may be None for some segments)
        speaker = segment.get("speaker", "UNKNOWN")

        final_output.append(
            {
                "speaker": speaker,
                "start_time": f"{segment['start']:.2f}s",
                "end_time": f"{segment['end']:.2f}s",
                "text": segment["text"].strip(),
            }
        )

    print("✓ Processing complete - ALL OPERATIONS ON GPU")
    return final_output


def save_transcription(segments, output_path: str):
    """
    Save the transcription to a text file.

    Args:
        segments (list): List of transcribed segments with speaker labels
        output_path (str): Path where to save the transcription
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=== TRANSCRIPTION WITH SPEAKER DIARIZATION (GPU-PROCESSED) ===\n\n")

        current_speaker = None
        for segment in segments:
            # Add a separator when speaker changes
            if segment["speaker"] != current_speaker:
                if current_speaker is not None:
                    f.write("\n")
                f.write(f"--- {segment['speaker']} ---\n")
                current_speaker = segment["speaker"]

            f.write(
                f"[{segment['start_time']} -> {segment['end_time']}] {segment['text']}\n"
            )


def get_speaker_stats(segments):
    """
    Get statistics about speakers in the transcription.

    Args:
        segments (list): List of transcribed segments with speaker labels

    Returns:
        dict: Speaker statistics
    """
    speaker_stats = {}

    for segment in segments:
        speaker = segment["speaker"]
        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                "segment_count": 0,
                "total_duration": 0.0,
                "word_count": 0,
            }

        # Calculate duration
        start = float(segment["start_time"].replace("s", ""))
        end = float(segment["end_time"].replace("s", ""))
        duration = end - start

        speaker_stats[speaker]["segment_count"] += 1
        speaker_stats[speaker]["total_duration"] += duration
        speaker_stats[speaker]["word_count"] += len(segment["text"].split())

    return speaker_stats


if __name__ == "__main__":
    audio_file_path = "source-files/0f642HQfqQQ.wav"
    output_file_path = "transcription_output.txt"

    print("=== GPU-ONLY WHISPERX PROCESSING ===")
    print("Using CORRECT WhisperX API - No Hacks!")
    print()

    try:
        # Process the audio file
        tagged_transcription = transcribe_and_diarize_whisperx(
            audio_file_path,
            language="auto",  # or specify "en", "es", etc.
        )

        # Display results
        print("\n--- Final Tagged Transcription ---")
        for segment in tagged_transcription:
            print(
                f"[{segment['start_time']} -> {segment['end_time']}] "
                f"{segment['speaker']}: {segment['text']}"
            )

        # Save transcription to file
        save_transcription(tagged_transcription, output_file_path)
        print(f"\n✓ Transcription saved to: {output_file_path}")

        # Display speaker statistics
        stats = get_speaker_stats(tagged_transcription)
        print("\n--- Speaker Statistics ---")
        for speaker, data in stats.items():
            print(f"{speaker}:")
            print(f"  - Segments: {data['segment_count']}")
            print(f"  - Total speaking time: {data['total_duration']:.2f} seconds")
            print(f"  - Word count: {data['word_count']}")
            print()

        print("🎉 ALL PROCESSING COMPLETED SUCCESSFULLY ON GPU!")

    except FileNotFoundError as e:
        print(f"❌ File Error: {e}")
        exit(1)
    except RuntimeError as e:
        print(f"❌ GPU Runtime Error: {e}")
        print("\nThis indicates a genuine WhisperX API or setup issue")
        exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
