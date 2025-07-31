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

                    # NEW: US Forms Collection tracking table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.us_forms_collections (
                            id SERIAL PRIMARY KEY,
                            collection_name VARCHAR(200) NOT NULL,
                            collection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            total_forms_targeted INTEGER,
                            total_forms_collected INTEGER,
                            completeness_score DECIMAL(5,2),
                            collection_status VARCHAR(50),
                            verification_results JSONB,
                            collection_metadata JSONB,
                            created_by VARCHAR(100) DEFAULT 'System'
                        )
                    """)

                    # NEW: Form collection relationships table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS public.form_collection_items (
                            id SERIAL PRIMARY KEY,
                            collection_id INTEGER REFERENCES public.us_forms_collections(id) ON DELETE CASCADE,
                            form_id INTEGER REFERENCES public.forms(id) ON DELETE CASCADE,
                            collection_priority INTEGER DEFAULT 1,
                            format_preference VARCHAR(20),
                            collection_notes TEXT,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    
                    # NEW: Indexes for US forms collection tables
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_date ON public.us_forms_collections(collection_date)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_status ON public.us_forms_collections(collection_status)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_form_collection_items_collection_id ON public.form_collection_items(collection_id)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_form_collection_items_form_id ON public.form_collection_items(form_id)")
                    
                    # Create JSONB indexes
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_structured_data ON public.forms USING GIN(structured_data)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_validation_warnings ON public.forms USING GIN(validation_warnings)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_lawyer_review ON public.forms USING GIN(lawyer_review)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_verification ON public.us_forms_collections USING GIN(verification_results)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_metadata ON public.us_forms_collections USING GIN(collection_metadata)")
                    
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

    # NEW: US Forms Collection Database Methods
    def create_us_forms_collection(self, collection_name: str, total_targeted: int, verification_results: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[int]:
        """Create a new US forms collection record"""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping collection creation.")
            return None
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.us_forms_collections (
                            collection_name, total_forms_targeted, total_forms_collected,
                            completeness_score, collection_status, verification_results, collection_metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        collection_name,
                        total_targeted,
                        0,  # Will be updated as forms are added
                        verification_results.get('completeness_score', 0),
                        'In Progress',
                        Json(verification_results),
                        Json(metadata)
                    ))
                    collection_id = cur.fetchone()['id']
                    conn.commit()
                    st.success(f"US Forms Collection '{collection_name}' created with ID: {collection_id}")
                    return collection_id
        except Exception as e:
            st.error(f"Error creating US forms collection: {e}")
            return None

    def add_form_to_collection(self, collection_id: int, form_id: int, priority: int = 1, format_preference: str = None, notes: str = None) -> bool:
        """Add a form to a US forms collection"""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping form addition to collection.")
            return False
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Insert form into collection
                    cur.execute("""
                        INSERT INTO public.form_collection_items (
                            collection_id, form_id, collection_priority, format_preference, collection_notes
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (collection_id, form_id, priority, format_preference, notes))
                    
                    # Update collection count
                    cur.execute("""
                        UPDATE public.us_forms_collections 
                        SET total_forms_collected = (
                            SELECT COUNT(*) FROM public.form_collection_items 
                            WHERE collection_id = %s
                        )
                        WHERE id = %s
                    """, (collection_id, collection_id))
                    
                    conn.commit()
                    return True
        except Exception as e:
            st.error(f"Error adding form to collection: {e}")
            return False

    def update_collection_status(self, collection_id: int, status: str, verification_results: Dict[str, Any] = None) -> bool:
        """Update US forms collection status and verification results"""
        if not self.database_url:
            st.warning("Database URL not configured. Skipping collection status update.")
            return False
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if verification_results:
                        cur.execute("""
                            UPDATE public.us_forms_collections 
                            SET collection_status = %s, verification_results = %s,
                                completeness_score = %s
                            WHERE id = %s
                        """, (
                            status, 
                            Json(verification_results),
                            verification_results.get('completeness_score', 0),
                            collection_id
                        ))
                    else:
                        cur.execute("""
                            UPDATE public.us_forms_collections 
                            SET collection_status = %s
                            WHERE id = %s
                        """, (status, collection_id))
                    
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            st.error(f"Error updating collection status: {e}")
            return False

    def get_us_forms_collections(self, status: str = None) -> List[Dict]:
        """Get US forms collections with optional status filter"""
        if not self.database_url:
            return []
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if status:
                        cur.execute("""
                            SELECT * FROM public.us_forms_collections 
                            WHERE collection_status = %s 
                            ORDER BY collection_date DESC
                        """, (status,))
                    else:
                        cur.execute("""
                            SELECT * FROM public.us_forms_collections 
                            ORDER BY collection_date DESC
                        """)
                    return cur.fetchall()
        except Exception as e:
            st.error(f"Error retrieving US forms collections: {e}")
            return []

    def get_collection_forms(self, collection_id: int) -> List[Dict]:
        """Get all forms in a specific collection with their details"""
        if not self.database_url:
            return []
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT f.*, fci.collection_priority, fci.format_preference, fci.collection_notes
                        FROM public.forms f
                        JOIN public.form_collection_items fci ON f.id = fci.form_id
                        WHERE fci.collection_id = %s
                        ORDER BY fci.collection_priority, f.form_name
                    """, (collection_id,))
                    return cur.fetchall()
        except Exception as e:
            st.error(f"Error retrieving collection forms: {e}")
            return []

    def get_us_forms_by_criteria(self, category: str = None, form_ids: List[str] = None, format_types: List[str] = None) -> List[Dict]:
        """Get US forms by specific criteria for collection purposes"""
        if not self.database_url:
            return []
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = "SELECT * FROM public.forms WHERE country_code = 'USA'"
                    params = []
                    
                    if category:
                        query += " AND category = %s"
                        params.append(category)
                    
                    if form_ids:
                        placeholders = ','.join(['%s'] * len(form_ids))
                        query += f" AND form_id IN ({placeholders})"
                        params.extend(form_ids)
                    
                    if format_types:
                        placeholders = ','.join(['%s'] * len(format_types))
                        query += f" AND document_format IN ({placeholders})"
                        params.extend(format_types)
                    
                    query += " ORDER BY category, form_name"
                    
                    cur.execute(query, params)
                    return cur.fetchall()
        except Exception as e:
            st.error(f"Error retrieving US forms by criteria: {e}")
            return []

    def get_collection_statistics(self, collection_id: int) -> Dict[str, Any]:
        """Get detailed statistics for a US forms collection"""
        if not self.database_url:
            return {}
            
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get basic collection info
                    cur.execute("SELECT * FROM public.us_forms_collections WHERE id = %s", (collection_id,))
                    collection_info = cur.fetchone()
                    
                    if not collection_info:
                        return {}
                    
                    # Get format distribution
                    cur.execute("""
                        SELECT f.document_format, COUNT(*) as count
                        FROM public.forms f
                        JOIN public.form_collection_items fci ON f.id = fci.form_id
                        WHERE fci.collection_id = %s
                        GROUP BY f.document_format
                        ORDER BY count DESC
                    """, (collection_id,))
                    format_distribution = dict(cur.fetchall())
                    
                    # Get category distribution
                    cur.execute("""
                        SELECT f.category, COUNT(*) as count
                        FROM public.forms f
                        JOIN public.form_collection_items fci ON f.id = fci.form_id
                        WHERE fci.collection_id = %s
                        GROUP BY f.category
                        ORDER BY count DESC
                    """, (collection_id,))
                    category_distribution = dict(cur.fetchall())
                    
                    # Get quality metrics
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_forms,
                            COUNT(CASE WHEN f.structured_data->>'multi_agent_analysis' IS NOT NULL THEN 1 END) as ai_processed,
                            COUNT(CASE WHEN array_length(f.validation_warnings::jsonb, 1) > 0 THEN 1 END) as with_warnings,
                            AVG(CASE WHEN f.structured_data->>'extracted_text_length' ~ '^[0-9]+$' 
                                THEN (f.structured_data->>'extracted_text_length')::int ELSE 0 END) as avg_text_length
                        FROM public.forms f
                        JOIN public.form_collection_items fci ON f.id = fci.form_id
                        WHERE fci.collection_id = %s
                    """, (collection_id,))
                    quality_metrics = cur.fetchone()
                    
                    return {
                        'collection_info': dict(collection_info),
                        'format_distribution': format_distribution,
                        'category_distribution': category_distribution,
                        'quality_metrics': dict(quality_metrics) if quality_metrics else {},
                        'statistics_generated_at': datetime.now().isoformat()
                    }
                    
        except Exception as e:
            st.error(f"Error retrieving collection statistics: {e}")
            return {}
