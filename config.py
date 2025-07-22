import os
import streamlit as st
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # API Keys - Strictly load from Streamlit secrets or environment variables
    TAVILY_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = ""
    CLOUDINARY_URL: str = "" # NEW: Added Cloudinary URL
    
    # Storage
    DOWNLOADS_DIR: str = "downloads"
    OUTPUTS_DIR: str = "output"
    
    # Processing
    MAX_FILE_SIZE_MB: int = 50
    SUPPORTED_FORMATS: list = None
    
    def __post_init__(self):
        # Attempt to load from Streamlit secrets first (for deployed apps)
        # Fallback to os.getenv (for local development or other environments)
        self.TAVILY_API_KEY = st.secrets.get("tavily_api_key", os.getenv("TAVILY_API_KEY", ""))
        self.OPENAI_API_KEY = st.secrets.get("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
        self.OPENROUTER_API_KEY = st.secrets.get("openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
        self.GEMINI_API_KEY = st.secrets.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
        self.DATABASE_URL = st.secrets.get("database_url", os.getenv("DATABASE_URL", ""))
        self.CLOUDINARY_URL = st.secrets.get("cloudinary_url", os.getenv("CLOUDINARY_URL", "")) # NEW: Load Cloudinary URL
        
        if self.SUPPORTED_FORMATS is None:
            self.SUPPORTED_FORMATS = ['.pdf', '.docx', '.xlsx', '.doc', '.xls', '.html', '.htm']
        
        # Create directories
        os.makedirs(self.DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(self.OUTPUTS_DIR, exist_ok=True)
        os.makedirs(f"{self.OUTPUTS_DIR}/forms", exist_ok=True)

config = Config()
