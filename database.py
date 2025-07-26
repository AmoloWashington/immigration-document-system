import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import streamlit as st
import uuid # For generating unique export IDs
import re

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        if not self.database_url:
            st.warning("Database URL not configured. Database operations will be skipped.")
        self.init_tables()
    
    def get_connection(self):
        if not self.database_url:
            raise Exception("Database URL is not configured.")
        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
    
    def init_tables(self):
        """Initialize database tables"""
        if not self.database_url:
            return
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Forms table with all required fields
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.forms (
                            id SERIAL PRIMARY KEY,
                            form_name VARCHAR(300) NOT NULL,
                            form_slug VARCHAR(200) NOT NULL UNIQUE,
                            country_code VARCHAR(3) NOT NULL,
                            country_name VARCHAR(100) NOT NULL,
                            category VARCHAR(200) NOT NULL,
                            form_description TEXT NOT NULL,
                            form_id VARCHAR(100),
                            governing_authority VARCHAR(200),
                            structured_data JSONB,
                            validation_warnings JSONB,
                            lawyer_review JSONB,
                            official_source_url TEXT UNIQUE,
                            discovered_by_query TEXT,
                            downloaded_file_path TEXT,
                            document_format VARCHAR(20),
                            processing_status VARCHAR(50),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Documents table (for file metadata, if needed separately from forms)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.documents (
                            id SERIAL PRIMARY KEY,
                            form_id INTEGER REFERENCES public.forms(id) ON DELETE CASCADE,
                            filename VARCHAR(300),
                            file_path TEXT,
                            file_format VARCHAR(20),
                            file_size_bytes INTEGER,
                            mime_type VARCHAR(100),
                            download_url TEXT,
                            cloudinary_url TEXT,
                            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Sources table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.sources (
                            id SERIAL PRIMARY KEY,
                            domain VARCHAR(200),
                            url TEXT UNIQUE,
                            title TEXT,
                            description TEXT,
                            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # Export logs table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.export_logs (
                            id SERIAL PRIMARY KEY,
                            export_id VARCHAR(100) UNIQUE NOT NULL,
                            document_ids JSONB NOT NULL,
                            export_formats JSONB NOT NULL,
                            exported_by VARCHAR(200),
                            export_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            file_path TEXT,
                            cloudinary_url TEXT
                        )
                    """)
                    
                    # Create indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_country_code ON public.forms(country_code)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_country_name ON public.forms(country_name)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_category ON public.forms(category)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_form_name ON public.forms(form_name)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_form_slug ON public.forms(form_slug)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_form_id ON public.documents(form_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_domain ON public.sources(domain)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_processing_status ON public.forms(processing_status)")
                    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_forms_official_source_url ON public.forms(official_source_url)")
                    
                    # Create JSONB indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_structured_data ON public.forms USING GIN(structured_data)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_validation_warnings ON public.forms USING GIN(validation_warnings)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_lawyer_review ON public.forms USING GIN(lawyer_review)")
                    
                    # Create function to update updated_at timestamp
                    cur.execute("""
                        CREATE OR REPLACE FUNCTION update_updated_at_column()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.updated_at = CURRENT_TIMESTAMP;
                            RETURN NEW;
                        END;
                        $$ language 'plpgsql';
                    """)
                    
                    # Create trigger
                    cur.execute("""
                        DROP TRIGGER IF EXISTS update_forms_updated_at ON public.forms;
                        CREATE TRIGGER update_forms_updated_at 
                            BEFORE UPDATE ON public.forms
                            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                    """)
                    
                    conn.commit()
                    st.success("Database tables and indexes initialized successfully.")
        except Exception as e:
            st.error(f"Database initialization error: {e}")
    
    def _generate_form_slug(self, form_name: str, form_id: str, country_code: str) -> str:
        """Generate a URL-friendly slug from form name and ID"""
        # Clean and combine form name and ID
        slug_parts = []
        
        if form_name and form_name != 'Unknown Form/Page':
            clean_name = re.sub(r'[^a-zA-Z0-9\s-]', '', form_name.lower())
            clean_name = re.sub(r'\s+', '-', clean_name.strip())
            if clean_name:
                slug_parts.append(clean_name)
        
        if form_id and form_id != 'N/A':
            clean_id = re.sub(r'[^a-zA-Z0-9\s-]', '', form_id.lower())
            clean_id = re.sub(r'\s+', '-', clean_id.strip())
            if clean_id:
                slug_parts.append(clean_id)
        
        if country_code:
            slug_parts.append(country_code.lower())
        
        # If no valid parts, create a generic slug
        if not slug_parts:
            slug_parts = ['immigration-form', str(uuid.uuid4())[:8]]
        
        slug = '-'.join(slug_parts)
        
        # Ensure slug is not too long
        if len(slug) > 200:
            slug = slug[:200]
        
        return slug
    
    def insert_form(self, form_data: Dict[str, Any]) -> Optional[int]:
        """Insert a new form record with proper slug generation"""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping form insertion.")
            return None
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Extract data from structured_data if available
                    structured_data = form_data.get('structured_data', {})
                    
                    # Generate form_slug if not provided
                    form_slug = structured_data.get('form_slug')
                    if not form_slug:
                        form_slug = self._generate_form_slug(
                            form_data.get('form_name', ''),
                            form_data.get('form_id', ''),
                            structured_data.get('country_code', form_data.get('country', ''))
                        )
                    
                    # Extract required fields with fallbacks
                    country_code = (
                        structured_data.get('country_code') or 
                        form_data.get('country', '')[:3].upper() if form_data.get('country') and form_data.get('country') != 'Unknown' else 
                        'UNK'
                    )

                    country_name = (
                        structured_data.get('country_name') or 
                        form_data.get('country', '') if form_data.get('country') and form_data.get('country') != 'Unknown' else 
                        'Unknown'
                    )

                    category = (
                        structured_data.get('category') or 
                        form_data.get('visa_category', '') if form_data.get('visa_category') and form_data.get('visa_category') != 'Unknown' else 
                        'Unknown'
                    )
                    
                    form_description = (
                        structured_data.get('form_description') or 
                        form_data.get('description', '') if form_data.get('description') and form_data.get('description') != 'No description available' else 
                        ''
                    )
                    
                    cur.execute("""
                        INSERT INTO public.forms (
                            form_name, form_slug, country_code, country_name, category,
                            form_description, form_id, governing_authority, structured_data,
                            validation_warnings, lawyer_review, official_source_url,
                            discovered_by_query, downloaded_file_path, document_format, processing_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        form_data.get('form_name'),
                        form_slug,
                        country_code,
                        country_name,
                        category,
                        form_description,
                        form_data.get('form_id'),
                        form_data.get('governing_authority'),
                        Json(form_data.get('structured_data', {})),
                        Json(form_data.get('validation_warnings', [])),
                        Json(form_data.get('lawyer_review', {})),
                        form_data.get('official_source_url'),
                        form_data.get('discovered_by_query'),
                        form_data.get('downloaded_file_path'),
                        form_data.get('document_format'),
                        form_data.get('processing_status')
                    ))
                    inserted_id = cur.fetchone()['id']
                    conn.commit()
                    st.success(f"Form '{form_data.get('form_name', 'Unknown')}' inserted with ID: {inserted_id}")
                    return inserted_id
        except psycopg2.errors.UniqueViolation as e:
            if 'form_slug' in str(e):
                # Try with a unique suffix
                try:
                    with self.get_connection() as conn:
                        with conn.cursor() as cur:
                            unique_slug = form_slug + '-' + str(uuid.uuid4())[:8]
                            cur.execute("""
                                INSERT INTO public.forms (
                                    form_name, form_slug, country_code, country_name, category,
                                    form_description, form_id, governing_authority, structured_data,
                                    validation_warnings, lawyer_review, official_source_url,
                                    discovered_by_query, downloaded_file_path, document_format, processing_status
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (
                                form_data.get('form_name'),
                                unique_slug,
                                country_code,
                                country_name,
                                category,
                                form_description,
                                form_data.get('form_id'),
                                form_data.get('governing_authority'),
                                Json(form_data.get('structured_data', {})),
                                Json(form_data.get('validation_warnings', [])),
                                Json(form_data.get('lawyer_review', {})),
                                form_data.get('official_source_url'),
                                form_data.get('discovered_by_query'),
                                form_data.get('downloaded_file_path'),
                                form_data.get('document_format'),
                                form_data.get('processing_status')
                            ))
                            inserted_id = cur.fetchone()['id']
                            conn.commit()
                            st.success(f"Form '{form_data.get('form_name', 'Unknown')}' inserted with unique slug: {unique_slug}")
                            return inserted_id
                except Exception as retry_error:
                    st.error(f"Error inserting form even with unique slug: {retry_error}")
                    return None
            else:
                st.warning(f"Form with URL '{form_data.get('official_source_url')}' already exists. Skipping insertion.")
                return None
        except Exception as e:
            st.error(f"Error inserting form: {e}")
            return None
    
    def insert_document(self, form_id: int, file_info: Dict[str, Any]) -> Optional[int]:
        """Insert a new document record linked to a form."""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping document insertion.")
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.documents (
                            form_id, filename, file_path, file_format, file_size_bytes, mime_type, download_url, cloudinary_url, downloaded_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        form_id,
                        file_info.get('filename'),
                        file_info.get('file_path'),
                        file_info.get('file_format'),
                        file_info.get('file_size_bytes'),
                        file_info.get('mime_type'),
                        file_info.get('download_url'),
                        file_info.get('cloudinary_url'),
                        datetime.now()
                    ))
                    inserted_id = cur.fetchone()['id']
                    conn.commit()
                    st.success(f"Document '{file_info.get('filename', 'Unknown')}' inserted with ID: {inserted_id} for Form ID: {form_id}")
                    return inserted_id
        except Exception as e:
            st.error(f"Error inserting document: {e}")
            return None

    def get_forms(self, country_code: str = None, category: str = None) -> List[Dict]:
        """Retrieve forms with optional filtering"""
        if not self.database_url:
            return []
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = "SELECT * FROM public.forms WHERE 1=1"
                    params = []
                    
                    if country_code:
                        query += " AND country_code = %s"
                        params.append(country_code)

                    if category:
                        query += " AND category = %s"
                        params.append(category)
                    
                    query += " ORDER BY created_at DESC"
                    
                    cur.execute(query, params)
                    return cur.fetchall()
        except Exception as e:
            st.error(f"Error retrieving forms: {e}")
            return []

    def get_form_by_url(self, url: str) -> Optional[Dict]:
        """Retrieve a single form by its official source URL."""
        if not self.database_url:
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM public.forms WHERE official_source_url = %s", (url,))
                    return cur.fetchone()
        except Exception as e:
            st.error(f"Error retrieving form by URL: {e}")
            return None
    
    def get_document_by_form_id(self, form_id: int) -> Optional[Dict]:
        """Retrieve document info by form ID."""
        if not self.database_url:
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM public.documents WHERE form_id = %s", (form_id,))
                    return cur.fetchone()
        except Exception as e:
            st.error(f"Error retrieving document by form ID: {e}")
            return None

    def update_lawyer_review(self, form_id: int, review_data: Dict[str, Any]) -> bool:
        """Update lawyer review for a form"""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping lawyer review update.")
            return False
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE public.forms 
                        SET lawyer_review = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (Json(review_data), form_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            st.error(f"Error updating lawyer review: {e}")
            return False

    def update_form_fields(self, form_id: int, fields_to_update: Dict[str, Any]) -> bool:
        """Update specific fields for a form record."""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping form update.")
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    set_clauses = []
                    params = []
                    for key, value in fields_to_update.items():
                        set_clauses.append(f"{key} = %s")
                        if isinstance(value, (dict, list)):
                            params.append(Json(value))
                        else:
                            params.append(value)
                    
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    
                    query = f"UPDATE public.forms SET {', '.join(set_clauses)} WHERE id = %s"
                    params.append(form_id)
                    
                    cur.execute(query, params)
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            st.error(f"Error updating form fields for ID {form_id}: {e}")
            return False

    def insert_source(self, url: str, title: str, description: str, domain: str) -> Optional[int]:
        """Insert a new source record if it doesn't already exist."""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping source insertion.")
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM public.sources WHERE url = %s", (url,))
                    if cur.fetchone():
                        return None
                    
                    cur.execute("""
                        INSERT INTO public.sources (url, title, description, domain, discovered_at)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (url, title, description, domain, datetime.now()))
                    inserted_id = cur.fetchone()['id']
                    conn.commit()
                    st.success(f"Source '{title}' inserted with ID: {inserted_id}")
                    return inserted_id
        except psycopg2.errors.UniqueViolation:
            st.warning(f"Source with URL '{url}' already exists (concurrent insert).")
            return None
        except Exception as e:
            st.error(f"Error inserting source: {e}")
            return None

    def insert_export_log(self, document_ids: List[int], export_formats: List[str], file_path: str, cloudinary_url: Optional[str] = None, exported_by: str = "System") -> Optional[int]:
        """Log an export operation."""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping export log insertion.")
            return None
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    export_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO public.export_logs (export_id, document_ids, export_formats, exported_by, export_timestamp, file_path, cloudinary_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (export_id, Json(document_ids), Json(export_formats), exported_by, datetime.now(), file_path, cloudinary_url))
                    inserted_id = cur.fetchone()['id']
                    conn.commit()
                    st.success(f"Export log recorded with ID: {inserted_id}")
                    return inserted_id
        except Exception as e:
            st.error(f"Error inserting export log: {e}")
            return None
