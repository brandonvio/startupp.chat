from typing import Optional
import os
import ffmpeg
from loguru import logger


class AudioService:
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
    
    def extract_audio(self, video_file_path: str, output_path: Optional[str] = None) -> str:
        if not os.path.exists(video_file_path):
            raise FileNotFoundError(f"Video file not found: {video_file_path}")
        
        if output_path is None:
            base_name = os.path.splitext(video_file_path)[0]
            output_path = f"{base_name}.wav"
        
        try:
            logger.info(f"Extracting audio from {video_file_path} to {output_path}")
            
            (
                ffmpeg
                .input(video_file_path)
                .output(
                    output_path,
                    acodec='pcm_s16le',
                    ac=self.channels,
                    ar=self.sample_rate
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            if not os.path.exists(output_path):
                raise Exception(f"Audio extraction failed - output file not created: {output_path}")
            
            logger.success(f"Audio extracted successfully: {output_path}")
            return output_path
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error during audio extraction: {error_msg}")
            raise Exception(f"Audio extraction failed: {error_msg}")
        except Exception as e:
            logger.error(f"Audio extraction failed: {str(e)}")
            raise Exception(f"Audio extraction failed: {str(e)}")
    
    def get_audio_info(self, audio_file_path: str) -> dict:
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
        
        try:
            probe = ffmpeg.probe(audio_file_path)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            
            if audio_stream is None:
                raise Exception("No audio stream found in file")
            
            return {
                'duration': float(probe['format']['duration']),
                'sample_rate': int(audio_stream['sample_rate']),
                'channels': int(audio_stream['channels']),
                'codec': audio_stream['codec_name'],
                'format': probe['format']['format_name']
            }
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {str(e)}")
            raise Exception(f"Failed to get audio info: {str(e)}")