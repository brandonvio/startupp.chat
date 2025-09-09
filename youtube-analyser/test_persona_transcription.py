#!/usr/bin/env python3
"""
Test script for PersonaTranscriptionService
"""

import sys
import os
from loguru import logger
from services import PersonaTranscriptionService

def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

def test_persona_transcription():
    """Test the PersonaTranscriptionService with a sample file."""
    
    # Find a test audio/video file in the source-files directory
    source_files_dir = "source-files"
    test_files = []
    
    if os.path.exists(source_files_dir):
        for file in os.listdir(source_files_dir):
            if file.lower().endswith(('.mp4', '.mp3', '.wav', '.m4a', '.avi', '.mov')):
                test_files.append(os.path.join(source_files_dir, file))
    
    if not test_files:
        logger.error("No audio/video files found in source-files directory for testing")
        logger.info("Please ensure you have a test file (mp4, mp3, wav, m4a, avi, mov) in the source-files directory")
        return False
    
    test_file = test_files[0]
    logger.info(f"Testing with file: {test_file}")
    
    try:
        # Create PersonaTranscriptionService instance
        persona_service = PersonaTranscriptionService(
            default_model_size="small",  # Use smaller model for faster testing
            device="cuda" if os.system("nvidia-smi > /dev/null 2>&1") == 0 else "cpu"
        )
        
        # Perform persona transcription
        logger.info("Starting persona transcription test...")
        output_file = persona_service.transcribe_file(test_file, model_size="small")
        
        logger.success(f"Persona transcription completed successfully!")
        logger.info(f"Output file: {output_file}")
        
        # Display a preview of the results
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                preview_lines = lines[:20]  # Show first 20 lines
                
                logger.info("Preview of transcription with personas:")
                print("\n" + "="*60)
                for line in preview_lines:
                    print(line)
                if len(lines) > 20:
                    print(f"\n... and {len(lines) - 20} more lines")
                print("="*60)
        
        return True
        
    except Exception as e:
        logger.error(f"Persona transcription test failed: {str(e)}")
        return False

def main():
    setup_logging()
    logger.info("Starting PersonaTranscriptionService test...")
    
    success = test_persona_transcription()
    
    if success:
        logger.success("All tests passed!")
        return 0
    else:
        logger.error("Tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())