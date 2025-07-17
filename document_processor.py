import os
import requests
from pathlib import Path
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
import docx
import pandas as pd
from typing import Dict, Any, Optional
import streamlit as st
from urllib.parse import urlparse
import mimetypes
import time

class DocumentProcessor:
    def __init__(self, downloads_dir: str):
        self.downloads_dir = downloads_dir
        
    def download_document(self, url: str, country: str, category: str) -> Optional[Dict[str, Any]]:
        """Download document and return file info"""
        
        try:
            # Create directory structure
            save_dir = Path(self.downloads_dir) / country.lower() / category.lower().replace(" ", "_")
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # Get filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            if not filename or '.' not in filename:
                # Generate filename from URL
                filename = f"document_{abs(hash(url)) % 10000}.pdf"
            
            # Clean filename
            filename = "".join(c for c in filename if c.isalnum() or c in '.-_').rstrip()
            
            # Ensure a valid extension, default to .pdf if none
            if not any(filename.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']):
                filename += '.pdf'
            
            file_path = save_dir / filename
            
            # Skip if file already exists
            if file_path.exists() and file_path.stat().st_size > 0:
                st.info(f"File already exists: {filename}")
                return self._get_file_info(file_path, url)
            
            # Download file
            st.info(f"Downloading: {filename}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,*/*'
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Check content type from response headers
            content_type = response.headers.get('content-type', '').lower()
            
            # If it's clearly HTML and not a PDF, skip
            if 'html' in content_type and 'pdf' not in content_type and 'xml' not in content_type:
                st.warning(f"Skipping HTML/XML file: {url}")
                return None
            
            # Check file size
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 50 * 1024 * 1024:  # 50MB limit
                st.warning(f"File too large: {content_length / 1024 / 1024:.1f}MB")
                return None
            
            # Save file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify file was saved and has content
            if not file_path.exists() or file_path.stat().st_size == 0:
                st.error(f"Failed to save file or file is empty: {filename}")
                return None
            
            # **Crucial: Verify actual file type using magic bytes for PDFs**
            if file_path.suffix.lower() == '.pdf':
                with open(file_path, 'rb') as f:
                    first_bytes = f.read(4)
                    if first_bytes != b'%PDF':
                        st.warning(f"Downloaded file is not a valid PDF (magic bytes mismatch): {filename}. Deleting.")
                        file_path.unlink() # Delete the invalid file
                        return None
            
            return self._get_file_info(file_path, url)
            
        except requests.exceptions.RequestException as e:
            st.error(f"Network error downloading {url}: {e}")
            return None
        except Exception as e:
            st.error(f"Error downloading {url}: {e}")
            return None
    
    def _get_file_info(self, file_path: Path, url: str) -> Dict[str, Any]:
        """Get file information"""
        actual_size = file_path.stat().st_size
        filename = file_path.name
        
        file_info = {
            "filename": filename,
            "file_path": str(file_path),
            "file_size_bytes": actual_size,
            "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream", # Default to octet-stream
            "download_url": url,
            "file_format": Path(filename).suffix.upper().replace('.', '') or 'UNKNOWN'
        }
        
        st.success(f"Ready: {filename} ({actual_size / 1024:.1f}KB)")
        return file_info
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from document using multiple methods"""
        
        try:
            if not os.path.exists(file_path):
                st.error(f"File not found: {file_path}")
                return ""
            
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                return self._extract_pdf_text_robust(file_path)
            elif file_ext in ['.docx', '.doc']:
                return self._extract_word_text(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                return self._extract_excel_text(file_path)
            else:
                st.warning(f"Unsupported file type for text extraction: {file_ext}")
                return ""
                
        except Exception as e:
            st.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    def _extract_pdf_text_robust(self, file_path: str) -> str:
        """Extract text from PDF using multiple methods"""
        
        # Method 1: Try pdfplumber first (best for forms)
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                
                if len(text.strip()) > 100:  # If we got good text
                    st.success(f"Extracted text using pdfplumber: {len(text.strip())} chars")
                    return text.strip()
        except Exception as e:
            st.warning(f"pdfplumber failed for {Path(file_path).name}: {e}")
        
        # Method 2: Try PyMuPDF (fitz)
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
        
        # Method 3: Try PyPDF2 as fallback (less robust, but can work for simple PDFs)
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Skip if encrypted
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
            df = pd.read_excel(file_path, sheet_name=None)  # Read all sheets
            text = ""
            for sheet_name, sheet_df in df.items():
                text += f"Sheet: {sheet_name}\n"
                text += sheet_df.to_string() + "\n\n"
            
            st.success(f"Extracted text from Excel: {len(text.strip())} chars")
            return text.strip()
        except Exception as e:
            st.error(f"Error reading Excel file {file_path}: {e}")
            return ""

    def get_file_content_bytes(self, file_path: str) -> Optional[bytes]:
        """Reads a file from the given path and returns its content as bytes."""
        try:
            if not os.path.exists(file_path):
                st.error(f"File not found for download: {file_path}")
                return None
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            st.error(f"Error reading file for download: {e}")
            return None

    def get_extracted_text_bytes(self, file_path: str) -> Optional[bytes]:
        """Extracts text from a document and returns it as UTF-8 encoded bytes."""
        extracted_text = self.extract_text(file_path)
        if extracted_text:
            return extracted_text.encode('utf-8')
        return None
