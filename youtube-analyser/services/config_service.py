from typing import Dict, Any
import os
from loguru import logger


class ConfigService:
    """Service for managing application configuration and settings."""
    
    def __init__(self):
        self._config = self._load_default_config()
        self._load_environment_overrides()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration values."""
        return {
            'download': {
                'default_output_path': 'source-files',
                'default_resolution': 'best',
                'merge_output_format': 'mp4'
            },
            'transcription': {
                'default_model_size': 'medium',
                'device': 'cuda',
                'compute_type': 'float16',
                'beam_size': 5
            },
            'analysis': {
                'ollama_url': 'http://nvda:30434',
                'model_name': 'gpt-oss:20b',
                'temperature': 0.7,
                'max_tokens': 2048,
                'enable_analysis': True
            },
            'minio': {
                'endpoint': 'localhost:9000',
                'access_key': 'minioadmin',
                'secret_key': 'minioadmin',
                'bucket_name': 'videos',
                'secure': False,
                'enabled': False
            },
            'logging': {
                'level': 'INFO',
                'format': '{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}'
            }
        }
    
    def _load_environment_overrides(self):
        """Load configuration overrides from environment variables."""
        env_mappings = {
            'YT_OUTPUT_PATH': ('download', 'default_output_path'),
            'YT_RESOLUTION': ('download', 'default_resolution'),
            'WHISPER_MODEL_SIZE': ('transcription', 'default_model_size'),
            'WHISPER_DEVICE': ('transcription', 'device'),
            'WHISPER_COMPUTE_TYPE': ('transcription', 'compute_type'),
            'WHISPER_BEAM_SIZE': ('transcription', 'beam_size'),
            'OLLAMA_URL': ('analysis', 'ollama_url'),
            'OLLAMA_MODEL': ('analysis', 'model_name'),
            'OLLAMA_TEMPERATURE': ('analysis', 'temperature'),
            'OLLAMA_MAX_TOKENS': ('analysis', 'max_tokens'),
            'ENABLE_ANALYSIS': ('analysis', 'enable_analysis'),
            'MINIO_ENDPOINT': ('minio', 'endpoint'),
            'MINIO_ACCESS_KEY': ('minio', 'access_key'),
            'MINIO_SECRET_KEY': ('minio', 'secret_key'),
            'MINIO_BUCKET': ('minio', 'bucket_name'),
            'MINIO_SECURE': ('minio', 'secure'),
            'MINIO_ENABLED': ('minio', 'enabled'),
            'LOG_LEVEL': ('logging', 'level')
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                section, key = config_path
                
                # Type conversions for specific config values
                if section == 'transcription' and key == 'beam_size':
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid beam_size value: {value}, using default")
                        continue
                elif section == 'analysis':
                    if key == 'temperature':
                        try:
                            value = float(value)
                        except ValueError:
                            logger.warning(f"Invalid temperature value: {value}, using default")
                            continue
                    elif key == 'max_tokens':
                        try:
                            value = int(value)
                        except ValueError:
                            logger.warning(f"Invalid max_tokens value: {value}, using default")
                            continue
                    elif key == 'enable_analysis':
                        value = value.lower() in ('true', '1', 'yes', 'on')
                elif section == 'minio':
                    if key in ('secure', 'enabled'):
                        value = value.lower() in ('true', '1', 'yes', 'on')

                self._config[section][key] = value
                logger.debug(f"Loaded config override from {env_var}: {key} = {value}")
    
    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            section (str): Configuration section name.
            key (str, optional): Specific key within the section.
            default (Any): Default value if not found.
            
        Returns:
            Any: Configuration value or default.
        """
        if section not in self._config:
            return default
        
        if key is None:
            return self._config[section]
        
        return self._config[section].get(key, default)
    
    def get_download_config(self) -> Dict[str, Any]:
        """Get download service configuration."""
        return self._config['download']
    
    def get_transcription_config(self) -> Dict[str, Any]:
        """Get transcription service configuration."""
        return self._config['transcription']
    
    def get_analysis_config(self) -> Dict[str, Any]:
        """Get analysis service configuration."""
        return self._config['analysis']
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config['logging']

    def get_minio_config(self) -> Dict[str, Any]:
        """Get Minio storage configuration."""
        return self._config['minio']

    def set(self, section: str, key: str, value: Any):
        """
        Set configuration value.
        
        Args:
            section (str): Configuration section name.
            key (str): Configuration key.
            value (Any): Value to set.
        """
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section][key] = value
        logger.debug(f"Set config: {section}.{key} = {value}")
    
    def update_section(self, section: str, updates: Dict[str, Any]):
        """
        Update an entire configuration section.
        
        Args:
            section (str): Configuration section name.
            updates (Dict[str, Any]): Dictionary of updates.
        """
        if section not in self._config:
            self._config[section] = {}
        
        self._config[section].update(updates)
        logger.debug(f"Updated config section: {section} with {len(updates)} values")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()
