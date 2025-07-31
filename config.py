import os
import streamlit as st

class Config:
    def __init__(self):
        # Database Configuration
        self.DATABASE_URL = self._get_config_value("DATABASE_URL")
        
        # API Keys
        self.TAVILY_API_KEY = self._get_config_value("TAVILY_API_KEY")
        self.OPENAI_API_KEY = self._get_config_value("OPENAI_API_KEY")
        self.OPENROUTER_API_KEY = self._get_config_value("OPENROUTER_API_KEY")
        self.GEMINI_API_KEY = self._get_config_value("GEMINI_API_KEY")
        self.CLOUDINARY_URL = self._get_config_value("CLOUDINARY_URL")
        
        # Directory Configuration
        self.DOWNLOADS_DIR = "downloads"
        self.OUTPUTS_DIR = "outputs"
        
        # Create directories if they don't exist
        os.makedirs(self.DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(self.OUTPUTS_DIR, exist_ok=True)
    
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
