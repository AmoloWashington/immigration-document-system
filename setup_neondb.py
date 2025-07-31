"""
NeonDB Setup Script for Immigration Document Intelligence System
Run this script to set up your NeonDB database with the required tables.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st 
import sys
import os 

def create_database_url(host, database, username, password, port=5432):
    """Create a PostgreSQL connection URL"""
    return f"postgresql://{username}:{password}@{host}:{port}/{database}?sslmode=require"

def setup_database(database_url):
    """Set up the database with required tables"""
    
    conn = None
    cur = None
    try:
        # Connect to database
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        print("✅ Connected to NeonDB successfully!")
        
        # Create tables
        print("📋 Creating tables...")
        
        # Forms table
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
        
        # Documents table
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
        print("🔍 Creating indexes...")
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_country_code ON public.forms(country_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_country_name ON public.forms(country_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_category ON public.forms(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_form_name ON public.forms(form_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_form_slug ON public.forms(form_slug)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_form_id ON public.documents(form_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_domain ON public.sources(domain)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_processing_status ON public.forms(processing_status)")
        
        # NEW: Indexes for US forms collection tables
        cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_date ON public.us_forms_collections(collection_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_us_collections_status ON public.us_forms_collections(collection_status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_form_collection_items_collection_id ON public.form_collection_items(collection_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_form_collection_items_form_id ON public.form_collection_items(form_id)")
        
        # Create JSONB indexes for better performance
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
        
        # Commit changes
        conn.commit()
        
        print("✅ Database setup completed successfully!")
        print("📊 Tables created:")
        print("   - forms (main document data)")
        print("   - documents (file metadata)")
        print("   - sources (provenance tracking)")
        print("   - export_logs (export history)")
        print("   - us_forms_collections (US forms collection tracking)")
        print("   - form_collection_items (collection relationships)")
        
        # --- NEW DIAGNOSTIC STEP ---
        print("\n--- Verifying created tables and columns ---")
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name IN ('forms', 'documents', 'sources', 'export_logs', 'us_forms_collections', 'form_collection_items')
            ORDER BY table_name, column_name;
        """)
        verified_schema = cur.fetchall()
        if verified_schema:
            for row in verified_schema:
                print(f"  Table: {row['table_name']}, Column: {row['column_name']}, Type: {row['data_type']}")
            print("--- Schema verification complete ---")
        else:
            print("⚠️ No tables found in 'public' schema after creation. This indicates a problem.")
            return False # Indicate failure
        # --- END NEW DIAGNOSTIC STEP ---

        # Test the setup
        try:
            cur.execute("SELECT COUNT(*) FROM public.forms")
            result = cur.fetchone()
            forms_count = result[0] if result else 0
            print(f"📋 Current forms in database: {forms_count}")
            
            # Test US forms collections table
            cur.execute("SELECT COUNT(*) FROM public.us_forms_collections")
            result = cur.fetchone()
            collections_count = result[0] if result else 0
            print(f"📦 Current US forms collections: {collections_count}")
            
        except Exception as e:
            print(f"⚠️ Warning: Could not count records: {e}")
            # This is not a critical error, continue
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        if conn:
            conn.rollback() # Ensure rollback on error
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def main():
    print("🌍 Immigration Document Intelligence System - NeonDB Setup")
    print("=" * 60)
    
    database_url = None
    # Try to get database URL from Streamlit secrets or environment
    try:
        # This block will only work if run within a Streamlit context or if secrets.toml is loaded
        # For standalone script, os.getenv is more reliable.
        # We'll prioritize os.getenv for setup_neondb.py
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            # Fallback to Streamlit secrets if not in env (e.g., local dev)
            try:
                import streamlit as st
                database_url = st.secrets.get("database_url")
                if database_url:
                    print("📡 Using database URL from Streamlit secrets")
            except ImportError:
                pass # Streamlit not installed or not in Streamlit context
        else:
            print("📡 Using database URL from environment variable")

    except Exception as e:
        print(f"Error trying to get database URL from secrets/env: {e}")
        
    if not database_url:
        # Manual configuration if no URL found
        print("🔧 Manual NeonDB Configuration")
        print("Please enter your NeonDB connection details:")
        
        host = input("Host (e.g., your-project.neon.tech): ")
        database = input("Database name: ")
        username = input("Username: ")
        password = input("Password: ")
        
        database_url = create_database_url(host, database, username, password)
    
    if database_url:
        print(f"🔗 Connecting to: {database_url.split('@')[1].split('?')[0]}")  # Hide credentials
        
        if setup_database(database_url):
            print("\n🎉 Setup completed! You can now run the Streamlit app:")
            print("   streamlit run app.py")
            print("\n🆕 New Features Added:")
            print("   - US Forms Collection tracking")
            print("   - Enhanced export capabilities")
            print("   - Collection verification and reporting")
        else:
            print("\n❌ Setup failed. Please check your database credentials and permissions.")
            sys.exit(1) # Exit with error code
    else:
        print("❌ No database URL provided. Cannot proceed with setup.")
        sys.exit(1) # Exit with error code

if __name__ == "__main__":
    main()
