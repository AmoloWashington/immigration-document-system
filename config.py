import os
import streamlit as st
from pathlib import Path

class Config:
    def __init__(self):
        # Database Configuration
        self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/immigration_docs")
        
        # API Keys
        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")
        
        # Directory Configuration
        self.BASE_DIR = Path(__file__).parent
        self.DOWNLOADS_DIR = self.BASE_DIR / "downloads"
        self.OUTPUTS_DIR = self.BASE_DIR / "outputs"
        
        # Create directories if they don't exist
        self.DOWNLOADS_DIR.mkdir(exist_ok=True)
        self.OUTPUTS_DIR.mkdir(exist_ok=True)
    
    def _get_config_value(self, key: str) -> str:
        """Get configuration value from environment variables or Streamlit secrets"""
        # Try environment variables first
        value = os.getenv(key)
        if value:
            return value
        
        # Try Streamlit secrets
        try:
            return st.secrets[key]
        except (KeyError, FileNotFoundError):
            return ""
    
    def validate_config(self):
        """Validate that required configuration is present"""
        required_configs = {
            "DATABASE_URL": self.DATABASE_URL,
            "TAVILY_API_KEY": self.TAVILY_API_KEY,
            "CLOUDINARY_URL": self.CLOUDINARY_URL
        }
        
        missing_configs = []
        for config_name, config_value in required_configs.items():
            if not config_value:
                missing_configs.append(config_name)
        
        if missing_configs:
            st.error(f"Missing required configuration: {', '.join(missing_configs)}")
            st.info("Please set these values in your environment variables or Streamlit secrets.")
            return False
        
        # Check if at least one AI service is configured
        ai_services = [self.OPENAI_API_KEY, self.OPENROUTER_API_KEY, self.GEMINI_API_KEY]
        if not any(ai_services):
            st.warning("No AI service API keys configured. AI processing will be unavailable.")
        
        return True

# Create global config instance
config = Config()
