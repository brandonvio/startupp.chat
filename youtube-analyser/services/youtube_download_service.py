from typing import Optional
import yt_dlp
from loguru import logger


class YouTubeDownloadService:
    """Service for downloading YouTube videos using yt-dlp."""
    
    def __init__(self, default_output_path: str = ".", default_resolution: str = "best"):
        self.default_output_path = default_output_path
        self.default_resolution = default_resolution
    
    def _get_format_selector(self, resolution: str) -> str:
        """
        Get a robust format selector with fallbacks.
        
        Args:
            resolution (str): Requested resolution.
            
        Returns:
            str: Format selector string for yt-dlp.
        """
        if resolution == "best":
            # Try best video+audio, fallback to best available
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
        elif resolution in ["720p", "1080p", "480p", "360p"]:
            # Try specific resolution, fallback to best
            height = resolution.replace("p", "")
            return f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
        else:
            # Fallback for any other format specification
            return f"{resolution}/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
    
    def download_video(
        self, 
        video_id: str, 
        output_path: Optional[str] = None, 
        resolution: Optional[str] = None
    ) -> str:
        """
        Downloads a YouTube video by ID using yt-dlp.

        Args:
            video_id (str): The YouTube video ID.
            output_path (str, optional): The folder where the video will be saved.
            resolution (str, optional): Format selector (e.g., 'best', 'bestvideo[height<=720]+bestaudio').

        Returns:
            str: The file path of the downloaded video.
            
        Raises:
            Exception: If download fails or video ID is invalid.
        """
        if not video_id:
            raise ValueError("Video ID cannot be empty")
        
        output_path = output_path or self.default_output_path
        resolution = resolution or self.default_resolution
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        # Use more flexible format selection with fallbacks
        format_selector = self._get_format_selector(resolution)
        
        ydl_opts = {
            'outtmpl': f'{output_path}/{video_id}.%(ext)s',
            'format': format_selector,
            'merge_output_format': 'mp4',
        }
        
        try:
            logger.info(f"Starting download of video: {video_id}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                logger.success(f"Successfully downloaded video to: {filename}")
                return filename
                
        except Exception as e:
            logger.error(f"Failed to download video {video_id}: {str(e)}")
            raise Exception(f"Download failed for video {video_id}: {str(e)}")
    
    def get_video_info(self, video_id: str) -> dict:
        """
        Get video information without downloading.
        
        Args:
            video_id (str): The YouTube video ID.
            
        Returns:
            dict: Video information dictionary.
        """
        if not video_id:
            raise ValueError("Video ID cannot be empty")
            
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'quiet': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            logger.error(f"Failed to get video info for {video_id}: {str(e)}")
            raise Exception(f"Failed to get video info for {video_id}: {str(e)}")
