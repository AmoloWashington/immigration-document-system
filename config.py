import os
import streamlit as st
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # API Keys - Try Streamlit secrets first, then environment variables
    TAVILY_API_KEY: str = None
    OPENAI_API_KEY: str = None
    OPENROUTER_API_KEY: str = None
    GEMINI_API_KEY: str = None # New: Gemini API Key
    DATABASE_URL: str = None
    
    # Storage
    DOWNLOADS_DIR: str = "downloads"
    OUTPUTS_DIR: str = "output"
    
    # Processing
    MAX_FILE_SIZE_MB: int = 50
    SUPPORTED_FORMATS: list = None
    
    def __post_init__(self):
        # Try to get from Streamlit secrets first, then environment variables
        try:
            self.TAVILY_API_KEY = st.secrets.get("tavily_api_key", os.getenv("TAVILY_API_KEY", ""))
            self.OPENAI_API_KEY = st.secrets.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
            self.OPENROUTER_API_KEY = st.secrets.get("openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
            self.GEMINI_API_KEY = st.secrets.get("gemini_api_key", os.getenv("GEMINI_API_KEY", "")) # New
            self.DATABASE_URL = st.secrets.get("database_url", os.getenv("DATABASE_URL", ""))
        except:
            # Fallback to environment variables if secrets not available
            
            self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ['.pdf', '.docx', '.xlsx', '.doc', '.xls']
        
        # Create directories
        os.makedirs(self.DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(self.OUTPUTS_DIR, exist_ok=True)
        os.makedirs(f"{self.OUTPUTS_DIR}/forms", exist_ok=True)

config = Config()
