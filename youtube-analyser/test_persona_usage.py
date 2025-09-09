#!/usr/bin/env python3
"""
Example usage of the PersonaTranscriptionService for speaker identification
"""

import sys
import os
from loguru import logger
from services import ConfigService
from services.youtube_analyzer import YouTubeAnalyzer


def setup_logging():
    """Configure logging."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )


def main():
    """Example of using persona transcription for speaker identification."""
    setup_logging()
    
    try:
        # Initialize services
        config_service = ConfigService()
        analyzer = YouTubeAnalyzer(config_service)
        
        # Example video ID (replace with your own)
        video_id = "0f642HQfqQQ"
        source_files_dir = "source-files"
        os.makedirs(source_files_dir, exist_ok=True)
        
        logger.info("=== EXAMPLE 1: Standard Transcription ===")
        # Standard transcription without speaker identification
        result_standard = analyzer.analyze_youtube_video(
            video_id=video_id,
            output_path=source_files_dir,
            model_size="small",  # Use smaller model for faster testing
            use_persona_transcription=False  # Standard transcription
        )
        
        if result_standard['success']:
            logger.success(f"Standard transcription completed: {result_standard['transcription_file']}")
        else:
            logger.error(f"Standard transcription failed: {result_standard['error']}")
            return 1
        
        logger.info("=== EXAMPLE 2: Persona Transcription with Speaker Identification ===")
        # Persona transcription with speaker identification
        result_persona = analyzer.analyze_youtube_video(
            video_id=video_id,
            output_path=source_files_dir,
            model_size="small",  # Use smaller model for faster testing
            transcribe_only=True,  # Skip download since we already have the file
            use_persona_transcription=True  # Enable persona transcription
        )
        
        if result_persona['success']:
            logger.success(f"Persona transcription completed: {result_persona['transcription_file']}")
            
            # Compare the outputs
            logger.info("=== COMPARISON ===")
            logger.info(f"Standard transcription: {result_standard['transcription_file']}")
            logger.info(f"Persona transcription: {result_persona['transcription_file']}")
            
            # Show preview of persona transcription
            if os.path.exists(result_persona['transcription_file']):
                with open(result_persona['transcription_file'], 'r', encoding='utf-8') as f:
                    lines = f.read().split('\n')[:15]  # First 15 lines
                    logger.info("Preview of persona transcription:")
                    print("\n" + "="*60)
                    for line in lines:
                        print(line)
                    print("="*60)
        else:
            logger.error(f"Persona transcription failed: {result_persona['error']}")
            return 1
        
        logger.success("Example completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Example failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())