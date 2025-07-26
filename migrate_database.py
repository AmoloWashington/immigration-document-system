#!/usr/bin/env python3
"""
Database migration script to update from old schema to new schema.
This script will:
1. Add new columns to the forms table
2. Migrate existing data to new format
3. Generate form slugs for existing forms
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from config import Config

def generate_form_slug(form_name, form_id):
    """Generate a URL-friendly slug from form name and ID"""
    slug_parts = []
    
    if form_name:
        # Clean form name
        name_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', form_name.lower())
        name_clean = re.sub(r'\s+', '-', name_clean.strip())
        if name_clean:
            slug_parts.append(name_clean)
    
    if form_id:
        # Clean form ID
        id_clean = re.sub(r'[^a-zA-Z0-9\s-]', '', form_id.lower())
        id_clean = re.sub(r'\s+', '-', id_clean.strip())
        if id_clean:
            slug_parts.append(id_clean)
    
    slug = '-'.join(slug_parts)
    return slug[:200] if slug else 'unknown-form'

def get_country_info(country_field):
    """Extract country code and name from country field"""
    if not country_field:
        return 'UNK', 'Unknown'
    
    country_map = {
        'usa': ('USA', 'United States'),
        'united states': ('USA', 'United States'),
        'us': ('USA', 'United States'),
        'canada': ('CAN', 'Canada'),
        'can': ('CAN', 'Canada'),
        'united arab emirates': ('ARE', 'United Arab Emirates'),
        'uae': ('ARE', 'United Arab Emirates'),
        'are': ('ARE', 'United Arab Emirates'),
    }
    
    country_lower = country_field.lower().strip()
    return country_map.get(country_lower, (country_field[:3].upper(), country_field.title()))

def migrate_database():
    """Main migration function"""
    config = Config()
    database_url = config.get_database_url()
    
    if not database_url:
        print("❌ Database URL not configured. Cannot run migration.")
        return False
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        
        with conn.cursor() as cur:
            print("🔄 Starting database migration...")
            
            # Step 1: Add new columns if they don't exist
            print("📋 Adding new columns to forms table...")
            
            # Check if new columns already exist
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'forms' AND table_schema = 'public'
            """)
            existing_columns = {row['column_name'] for row in cur.fetchall()}
            
            # Add new columns if they don't exist
            new_columns = [
                ("form_slug", "VARCHAR(200)"),
                ("country_code", "VARCHAR(3)"),
                ("country_name", "VARCHAR(100)"),
                ("category", "VARCHAR(200)"),
                ("form_description", "TEXT")
            ]
            
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    cur.execute(f"ALTER TABLE public.forms ADD COLUMN {col_name} {col_type}")
                    print(f"✅ Added column: {col_name}")
                else:
                    print(f"⏭️ Column already exists: {col_name}")
            
            # Step 2: Migrate existing data
            print("📊 Migrating existing data...")
            
            # Get all existing forms
            cur.execute("SELECT * FROM public.forms WHERE form_slug IS NULL OR country_code IS NULL")
            forms_to_migrate = cur.fetchall()
            
            print(f"🔍 Found {len(forms_to_migrate)} forms to migrate")
            
            for form in forms_to_migrate:
                try:
                    # Generate form slug
                    form_slug = generate_form_slug(form.get('form_name'), form.get('form_id'))
                    
                    # Extract country info
                    old_country = form.get('country', '')
                    country_code, country_name = get_country_info(old_country)
                    
                    # Map visa_category to category
                    category = form.get('visa_category', 'General')
                    
                    # Use existing description or generate from form name
                    form_description = (
                        form.get('description') or 
                        f"Official immigration form: {form.get('form_name', 'Unknown Form')}"
                    )
                    
                    # Ensure unique slug
                    original_slug = form_slug
                    counter = 1
                    while True:
                        cur.execute("SELECT id FROM public.forms WHERE form_slug = %s AND id != %s", 
                                  (form_slug, form['id']))
                        if not cur.fetchone():
                            break
                        form_slug = f"{original_slug}-{counter}"
                        counter += 1
                    
                    # Update the form
                    cur.execute("""
                        UPDATE public.forms 
                        SET form_slug = %s, country_code = %s, country_name = %s, 
                            category = %s, form_description = %s
                        WHERE id = %s
                    """, (form_slug, country_code, country_name, category, form_description, form['id']))
                    
                    print(f"✅ Migrated form {form['id']}: {form.get('form_name', 'Unknown')} -> {form_slug}")
                    
                except Exception as e:
                    print(f"⚠️ Error migrating form {form['id']}: {e}")
                    continue
            
            # Step 3: Add constraints and indexes for new columns
            print("🔗 Adding constraints and indexes...")
            
            try:
                # Make form_slug unique (if not already)
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_forms_form_slug_unique ON public.forms(form_slug)")
                
                # Add NOT NULL constraints where appropriate (after data migration)
                cur.execute("ALTER TABLE public.forms ALTER COLUMN form_slug SET NOT NULL")
                cur.execute("ALTER TABLE public.forms ALTER COLUMN country_code SET NOT NULL")
                cur.execute("ALTER TABLE public.forms ALTER COLUMN country_name SET NOT NULL") 
                cur.execute("ALTER TABLE public.forms ALTER COLUMN category SET NOT NULL")
                cur.execute("ALTER TABLE public.forms ALTER COLUMN form_description SET NOT NULL")
                
                print("✅ Added constraints and indexes")
                
            except Exception as e:
                print(f"⚠️ Warning adding constraints: {e}")
            
            # Commit all changes
            conn.commit()
            print("✅ Migration completed successfully!")
            
            # Print summary
            cur.execute("SELECT COUNT(*) as total FROM public.forms")
            total_forms = cur.fetchone()['total']
            
            cur.execute("SELECT COUNT(*) as migrated FROM public.forms WHERE form_slug IS NOT NULL")
            migrated_forms = cur.fetchone()['migrated']
            
            print(f"📊 Migration Summary:")
            print(f"   Total forms: {total_forms}")
            print(f"   Migrated forms: {migrated_forms}")
            print(f"   Success rate: {(migrated_forms/total_forms*100):.1f}%" if total_forms > 0 else "   No forms found")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Immigration Forms Database Migration")
    print("=" * 50)
    
    success = migrate_database()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("Your database now supports the new format with:")
        print("• Form names and slugs")
        print("• Country codes and names") 
        print("• Categories")
        print("• Comprehensive form descriptions")
    else:
        print("\n💥 Migration failed. Please check the error messages above.")
