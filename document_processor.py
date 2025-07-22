import os
import requests
from pathlib import Path
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
import docx
import pandas as pd
from typing import Dict, Any, Optional, Tuple
import streamlit as st
from urllib.parse import urlparse
import mimetypes
import time
from bs4 import BeautifulSoup
import cloudinary # NEW: Import Cloudinary
import cloudinary.uploader # NEW: Import Cloudinary uploader

class DocumentProcessor:
    def __init__(self, downloads_dir: str, cloudinary_url: Optional[str] = None): # NEW: Added cloudinary_url parameter
        self.downloads_dir = downloads_dir
        self.cloudinary_url = cloudinary_url # NEW: Store Cloudinary URL
        if self.cloudinary_url: # NEW: Configure Cloudinary
            cloudinary.config(cloud_name=self.cloudinary_url.split('@')[1],
                              api_key=self.cloudinary_url.split('//')[1].split(':')[0],
                              api_secret=self.cloudinary_url.split(':')[2].split('@')[0],
                              secure=True)
            st.success("Cloudinary configured for document uploads.")
        else:
            st.warning("Cloudinary URL not configured. Documents will only be stored locally.")
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Validates a URL by making a HEAD request to check its accessibility and status code.
        It will now only skip URLs that lead to HTTP errors (4xx, 5xx) or network issues.
        Returns (is_valid, status_code, error_message).
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*' # Accept all content types
            }
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            
            if 200 <= response.status_code < 400: # Success or redirection
                return True, response.status_code, None
            else:
                return False, response.status_code, f"HTTP Error: {response.status_code}"
        except requests.exceptions.Timeout:
            return False, None, "Request timed out."
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error (DNS, network unreachable, etc.)."
        except requests.exceptions.RequestException as e:
            return False, None, f"Network error: {e}"
        except Exception as e:
            return False, None, f"Unexpected error during URL validation: {e}"

    def _upload_to_cloudinary(self, file_path: str, folder: str = "immigration_documents") -> Optional[str]: # NEW: Cloudinary upload method
        """Uploads a file to Cloudinary and returns its URL."""
        if not self.cloudinary_url:
            st.warning("Cloudinary not configured. Skipping upload.")
            return None
        try:
            st.info(f"Uploading {Path(file_path).name} to Cloudinary...")
            # Use the original filename as public_id, but ensure it's URL-safe
            public_id = Path(file_path).stem.replace(" ", "_").replace(".", "_")
            
            response = cloudinary.uploader.upload(
                file_path,
                folder=folder,
                public_id=public_id,
                resource_type="auto" # Auto-detect resource type (image, raw, video)
            )
            st.success(f"Uploaded to Cloudinary: {response['secure_url']}")
            return response['secure_url']
        except Exception as e:
            st.error(f"Error uploading to Cloudinary: {e}")
            return None

    def download_document(self, url: str, country: str, category: str) -> Optional[Dict[str, Any]]:
        """Download document, save locally, and upload to Cloudinary. Return local file info and Cloudinary URL."""
        
        local_file_path = None
        cloudinary_url = None # NEW: Initialize Cloudinary URL
        try:
            # Create directory structure for local storage
            save_dir = Path(self.downloads_dir) / country.lower() / category.lower().replace(" ", "_")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Get filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or '.' not in filename:
                filename = f"document_{abs(hash(url)) % 10000}.html" # Default to HTML if no clear extension
            
            filename = "".join(c for c in filename if c.isalnum() or c in '.-_').rstrip()
            
            # Ensure a valid extension, default to .html if none
            if not any(filename.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.html', '.htm']):
                filename += '.html'
            
            local_file_path = save_dir / filename
            
            # Download file locally
            st.info(f"Downloading: {filename} to local storage...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*'
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 50 * 1024 * 1024:  # 50MB limit
                st.warning(f"File too large: {content_length / 1024 / 1024:.1f}MB")
                return None
            
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            if not local_file_path.exists() or local_file_path.stat().st_size == 0:
                st.error(f"Failed to save file or file is empty: {filename}")
                return None
            
            # Specific check for PDF magic bytes, if it's supposed to be a PDF
            if local_file_path.suffix.lower() == '.pdf':
                with open(local_file_path, 'rb') as f:
                    first_bytes = f.read(4)
                    if first_bytes != b'%PDF':
                        st.warning(f"Downloaded file is not a valid PDF (magic bytes mismatch): {filename}. It might be HTML or another format. Attempting to rename to .html")
                        new_local_path = local_file_path.with_suffix('.html')
                        os.rename(local_file_path, new_local_path)
                        local_file_path = new_local_path # Update path for subsequent steps
            
            # NEW: Upload to Cloudinary after successful local download
            cloudinary_url = self._upload_to_cloudinary(str(local_file_path), folder=f"immigration_documents/originals/{country.lower()}/{category.lower().replace(' ', '_')}")

            # Return file info with the local file path AND Cloudinary URL
            final_file_format = Path(local_file_path).suffix.upper().replace('.', '') or 'UNKNOWN'
            if final_file_format == 'HTM': final_file_format = 'HTML'

            file_info = {
                "filename": filename,
                "file_path": str(local_file_path), # Store local file path here
                "file_size_bytes": local_file_path.stat().st_size,
                "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
                "download_url": url, # Original source URL
                "cloudinary_url": cloudinary_url, # NEW: Add Cloudinary URL
                "file_format": final_file_format
            }
            
            st.success(f"Ready: {filename} (Stored locally and on Cloudinary)")
            return file_info
            
        except requests.exceptions.RequestException as e:
            st.error(f"Network error downloading {url}: {e}")
            return None
        except Exception as e:
            st.error(f"Error downloading {url}: {e}")
            return None
        finally:
            # No cleanup needed here, as files are intended to be stored locally
            pass

    def extract_text(self, file_path: str) -> str:
        """Extract text from document using multiple methods.
        This method now expects a local file path.
        """
        return self._extract_text_from_local_file(file_path)

    def _extract_text_from_local_file(self, local_file_path: str) -> str:
        """Helper to extract text from a local file."""
        try:
            if not os.path.exists(local_file_path):
                st.error(f"Local file not found for text extraction: {local_file_path}")
                return ""
            
            file_ext = Path(local_file_path).suffix.lower()
            
            if file_ext == '.pdf':
                return self._extract_pdf_text_robust(local_file_path)
            elif file_ext in ['.docx', '.doc']:
                return self._extract_word_text(local_file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return self._extract_excel_text(local_file_path)
            elif file_ext in ['.html', '.htm']:
                return self._extract_html_text(local_file_path)
            else:
                st.warning(f"Unsupported file type for text extraction: {file_ext}")
                return ""
                
        except Exception as e:
            st.error(f"Error extracting text from {local_file_path}: {e}")
            return ""

    def _extract_pdf_text_robust(self, file_path: str) -> str:
        """Extract text from PDF using multiple methods"""
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if len(text.strip()) > 100:
                    st.success(f"Extracted text using pdfplumber: {len(text.strip())} chars")
                    return text.strip()
        except Exception as e:
            st.warning(f"pdfplumber failed for {Path(file_path).name}: {e}")
        
        try:
            doc = fitz.open(file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                text += page_text + "\n"
            doc.close()
            if len(text.strip()) > 100:
                st.success(f"Extracted text using PyMuPDF: {len(text.strip())} chars")
                return text.strip()
        except Exception as e:
            st.warning(f"PyMuPDF failed for {Path(file_path).name}: {e}")
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if pdf_reader.is_encrypted:
                    st.warning(f"PDF is encrypted, skipping PyPDF2: {Path(file_path).name}")
                    return ""
                text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text += page_text + "\n"
                    except Exception as e:
                        st.warning(f"PyPDF2: Error reading page {page_num + 1} of {Path(file_path).name}: {e}")
                        continue
                if len(text.strip()) > 50:
                    st.success(f"Extracted text using PyPDF2: {len(text.strip())} chars")
                    return text.strip()
        except Exception as e:
            st.error(f"PyPDF2 failed for {Path(file_path).name}: {e}")
        
        st.error(f"All PDF extraction methods failed for: {Path(file_path).name}. Content might be image-based or severely corrupted.")
        return ""

    def _extract_word_text(self, file_path: str) -> str:
        """Extract text from Word document"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            st.success(f"Extracted text from Word doc: {len(text.strip())} chars")
            return text.strip()
        except Exception as e:
            st.error(f"Error reading Word document {file_path}: {e}")
            return ""

    def _extract_excel_text(self, file_path: str) -> str:
        """Extract text from Excel file"""
        try:
            df = pd.read_excel(file_path, sheet_name=None)
            text = ""
            for sheet_name, sheet_df in df.items():
                text += f"Sheet: {sheet_name}\n"
                text += sheet_df.to_string() + "\n\n"
            st.success(f"Extracted text from Excel: {len(text.strip())} chars")
            return text.strip()
        except Exception as e:
            st.error(f"Error reading Excel file {file_path}: {e}")
            return ""

    def _extract_html_text(self, file_path: str) -> str:
        """Basic extraction of text from HTML file (strips tags)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                text = soup.get_text(separator='\n', strip=True)
            st.success(f"Extracted text from HTML: {len(text.strip())} chars")
            return text.strip()
        except ImportError:
            st.error("BeautifulSoup4 not installed. Cannot extract text from HTML. Please run `pip install beautifulsoup4`.")
            return ""
        except Exception as e:
            st.error(f"Error reading HTML file {file_path}: {e}")
            return ""

    def get_file_content_bytes_from_path(self, file_path: str) -> Optional[bytes]:
        """Reads a file from the given local file path and returns its content as bytes."""
        try:
            if not Path(file_path).exists():
                st.error(f"Local file not found: {file_path}")
                return None
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            st.error(f"Error reading file from local path for download: {e}")
            return None

    def get_extracted_text_bytes(self, file_path: str) -> Optional[bytes]:
        """Extracts text from a document (from local path) and returns it as UTF-8 encoded bytes (for Markdown/TXT)."""
        extracted_text = self.extract_text(file_path)
        if extracted_text:
            return extracted_text.encode('utf-8')
        return None
