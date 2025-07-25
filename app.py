import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import traceback
import psycopg2
from urllib.parse import urlparse
import mimetypes
import time  # Import time for delays
import html
import re

# Import our services
from config import config
from database import DatabaseManager
from discovery_service import DocumentDiscoveryService
from document_processor import DocumentProcessor
from ai_service import AIExtractionService
from export_service import ExportService

# Utility function to clean HTML tags and entities
def clean_html_text(text):
    """Remove HTML tags and decode HTML entities from text"""
    if not text:
        return text

    # Remove HTML tags
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', str(text))

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up extra whitespace
    text = ' '.join(text.split())

    return text

# Initialize services
def init_services():
    db = DatabaseManager(config.DATABASE_URL)
    processor = DocumentProcessor(config.DOWNLOADS_DIR, config.CLOUDINARY_URL)
    discovery = DocumentDiscoveryService(config.TAVILY_API_KEY, processor, db)
    ai_service = AIExtractionService(config.OPENAI_API_KEY, config.OPENROUTER_API_KEY, config.GEMINI_API_KEY)
    export_service = ExportService(config.OUTPUTS_DIR, db, config.CLOUDINARY_URL)

    return db, discovery, processor, ai_service, export_service

def main():
    st.set_page_config(
        page_title="Immigration Document Intelligence System",
        page_icon="📋",
        layout="wide"
    )

    # Hero Section with Custom Styling
    st.markdown("""
    <style>
    .hero-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .hero-title {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .hero-subtitle {
        font-size: 1.2rem;
        text-align: center;
        opacity: 0.9;
        margin-bottom: 2rem;
    }

    .main-nav {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    .feature-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        text-align: center;
        margin: 1rem 0;
        transition: transform 0.3s ease;
    }
    .feature-card:hover {
        transform: translateY(-5px);
    }
    .warning-banner {
        background: linear-gradient(45deg, #ff6b6b, #feca57);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
    }
    </style>

    <script>
    // Suppress metrics tracking errors that occur in Streamlit
    window.addEventListener('error', function(e) {
        if (e.message && e.message.includes('Failed to fetch') &&
            e.filename && e.filename.includes('MetricsManager')) {
            e.preventDefault();
            return false;
        }
    });

    // Override fetch for metrics endpoints to prevent errors
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        if (typeof url === 'string' && url.includes('metrics')) {
            return Promise.resolve(new Response('{}', {status: 200}));
        }
        return originalFetch.apply(this, arguments);
    };
    </script>

    <div class="hero-container">
        <h1 class="hero-title">🌍 Immigration Document Intelligence System</h1>
        <p class="hero-subtitle">Automated discovery, processing, and validation of official immigration documents and information</p>
    </div>
    """, unsafe_allow_html=True)

    # Clear cache button in sidebar
    with st.sidebar:
        st.markdown("### ⚙️ System Controls")
        if st.button("🔄 Clear All Caches", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    # Warning banner
    st.markdown("""
    <div class="warning-banner">
        ⚠️ <strong>Important:</strong> Documents are stored locally and uploaded to Cloudinary for persistent storage.
    </div>
    """, unsafe_allow_html=True)

    db, discovery, processor, ai_service, export_service = init_services()

    # Enhanced Navigation
    st.markdown('<div class="main-nav">', unsafe_allow_html=True)
    st.markdown("### 🧭 Navigation Dashboard")

    # Navigation cards in columns
    col1, col2, col3 = st.columns(3)

    navigation_options = [
        {"title": "🔍 Document Discovery", "desc": "Find and process immigration documents", "icon": "🔍"},
        {"title": "📄 Document Viewer", "desc": "Browse and analyze processed documents", "icon": "📄"},
        {"title": "✅ Validation Panel", "desc": "Review and validate document data", "icon": "✅"},
        {"title": "📊 Export Panel", "desc": "Export data in various formats", "icon": "📊"},
        {"title": "🗄️ Database Viewer", "desc": "Browse database contents", "icon": "🗄️"},
        {"title": "☁️ Cloudinary Document Browser", "desc": "View cloud-stored documents", "icon": "☁️"},
        {"title": "🩺 Database Health Check", "desc": "Check database health status", "icon": "🩺"}
    ]

    page = st.selectbox(
        "Choose a page:",
        [opt["title"] for opt in navigation_options],
        format_func=lambda x: x
    )

    st.markdown('</div>', unsafe_allow_html=True)

    if page == "🔍 Document Discovery":
        discovery_page(discovery, processor, ai_service, db)
    elif page == "📄 Document Viewer":
        document_viewer_page(db, processor, ai_service)
    elif page == "✅ Validation Panel":
        validation_panel_page(db, processor, ai_service)
    elif page == "📊 Export Panel":
        export_panel_page(db, export_service)
    elif page == "🗄️ Database Viewer":
        database_viewer_page(db)
    elif page == "☁️ Cloudinary Document Browser":
        cloudinary_browser_page(db)
    elif page == "🩺 Database Health Check":
        database_health_check_page(config.DATABASE_URL)

def discovery_page(discovery, processor, ai_service, db):
    st.markdown("""
    <style>
    .discovery-header {
        background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .input-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .options-section {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .action-button {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        border: none;
        padding: 1rem 2rem;
        border-radius: 10px;
        font-weight: bold;
        font-size: 1.1rem;
        cursor: pointer;
        transition: transform 0.3s ease;
    }
    .action-button:hover {
        transform: translateY(-2px);
    }
    </style>

    <div class="discovery-header">
        <h1>�� Document Discovery</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0; opacity: 0.9;">
            Discover official immigration documents and relevant informational pages from government sources
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="input-section">', unsafe_allow_html=True)
    st.markdown("### 🌍 Select Country and Visa Type")
    col1, col2 = st.columns(2)

    with col1:
        country = st.selectbox(
            "Select Country:",
            ["USA", "Canada", "UK", "Australia", "Germany", "France", "United Arab Emirates", "India", "Mexico", "Brazil", "China", "Japan", "South Korea", "South Africa", "New Zealand", "Singapore", "Philippines", "Other"]
        )

        if country == "Other":
            country = st.text_input("Enter country name:")

    with col2:
        visa_type = st.selectbox(
            "Select Visa/Immigration Type:",
            [
                "Work Visa", "Student Visa", "Tourist Visa", "Family Visa",
                "Permanent Residence", "Citizenship", "Business Visa", "Other"
            ]
        )

        if visa_type == "Other":
            visa_type = st.text_input("Enter visa type:")

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="options-section">', unsafe_allow_html=True)
    st.markdown("### ⚙️ Processing Options")

    # Information about balanced document discovery
    st.info("🎯 **Enhanced Discovery**: The system now equally prioritizes PDF, Excel, Word, and other critical document formats alongside web pages for comprehensive immigration intelligence.")

    col1, col2 = st.columns(2)

    with col1:
        max_docs = st.slider("Maximum documents/pages to process:", 1, 30, 8)  # Increased default for better format diversity
        auto_process = st.checkbox("Auto-process after discovery", value=True)

    with col2:
        save_to_db = st.checkbox("Save to database", value=True)
        validate_with_ai = st.checkbox("AI extraction & validation", value=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if st.checkbox("Show AI Prompt Preview"):
        if ai_service.openai_client or ai_service.openrouter_client or ai_service.gemini_model:
            dummy_doc_info = {
                'filename': 'example.pdf',
                'download_url': 'http://example.com/example.pdf',
                'file_format': 'PDF',
                'file_path': '/tmp/example.pdf',
                'discovered_by_query': 'dummy query'
            }
            st.json(ai_service.extract_form_data("dummy text content", dummy_doc_info))
        else:
            st.info("AI service not initialized to show prompt preview.")

    if st.button("🚀 Start Discovery", type="primary"):
        if country and visa_type:
            with st.spinner("Discovering documents and information pages..."):
                st.subheader("Step 1: Document Discovery")
                discovered_docs = discovery.discover_documents(country, visa_type)

                if discovered_docs:
                    st.success(f"Found {len(discovered_docs)} potential documents/information pages")

                    docs_to_process = discovered_docs[:max_docs]
                    st.info(f"Attempting to process first {len(docs_to_process)} documents/pages...")

                    for i, doc in enumerate(docs_to_process):
                        with st.expander(f"📄 {doc['title'][:100]}..."):
                            st.write(f"**URL:** {doc['url']}")
                            st.write(f"**Source:** {doc['source_domain']}")
                            st.write(f"**Type:** {doc['file_type']}")
                            st.write(f"**Description:** {doc['description'][:200]}...")

                    if auto_process:
                        st.subheader("Step 2: Processing Documents")
                        process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai)
                    else:
                        if st.button("📥 Download and Process Selected Documents"):
                            process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai)
                else:
                    st.warning("No documents or relevant information pages found. Try different search terms or broaden your query.")
        else:
            st.error("Please select both country and visa type.")

    st.markdown("---")
    st.subheader("⚡ Batch Process Country")
    st.markdown("Automatically discover, process, and save documents for an entire country.")
    batch_country = st.selectbox(
        "Select Country for Batch Processing:",
        [""] + sorted(list(DocumentDiscoveryService.COUNTRY_DOMAINS_MAP.keys()))
    )
    if st.button("🚀 Start Batch Processing", type="secondary"):
        if batch_country:
            st.info(f"Starting batch processing for {batch_country}. This may take a while...")
            common_visa_types = ["Work Visa", "Student Visa", "Tourist Visa", "Family Visa", "Permanent Residence", "Citizenship", "Business Visa"]

            all_discovered_docs = []
            for vt in common_visa_types:
                st.subheader(f"Discovering for {batch_country} - {vt}...")
                discovered_docs_for_type = discovery.discover_documents(batch_country, vt)
                all_discovered_docs.extend(discovered_docs_for_type)
                st.info(f"Found {len(discovered_docs_for_type)} documents for {batch_country} - {vt}.")
                time.sleep(1)

            if all_discovered_docs:
                st.success(f"Total {len(all_discovered_docs)} unique documents/pages discovered for {batch_country}.")
                st.subheader(f"Initiating processing for all discovered documents in {batch_country}...")
                process_documents_improved(all_discovered_docs, batch_country, "Batch Process", processor, ai_service, db, True, True)
            else:
                st.warning(f"No documents found for batch processing in {batch_country}.")
        else:
            st.error("Please select a country for batch processing.")


def process_documents_improved(discovered_docs, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai):
    """Improved document processing with better error handling and progress tracking"""

    st.subheader("📥 Document Processing Pipeline")

    progress_container = st.container()
    status_container = st.container()
    results_container = st.container()

    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()

    processed_forms = []
    failed_docs = []
    skipped_duplicates = []

    total_docs = len(discovered_docs)

    for i, doc in enumerate(discovered_docs):
        current_progress = (i + 1) / total_docs

        with status_container:
            st.write(f"**Processing {i+1}/{total_docs}:** {doc['title'][:80]}...")

        is_valid_url, status_code, error_msg = processor.validate_url(doc['url'])
        if not is_valid_url:
            st.error(f"❌ Skipping URL '{doc['url']}' due to validation error (Status: {status_code}, Error: {error_msg}).")
            failed_docs.append({"doc": doc, "error": f"URL validation failed: {error_msg}", "step": "pre-download validation"})
            progress_bar.progress(current_progress)
            continue

        if save_to_db:
            existing_form = db.get_form_by_url(doc['url'])
            if existing_form:
                st.info(f"⏩ Skipping duplicate: '{doc['title'][:50]}...' (already in database with ID: {existing_form['id']}). **Tokens saved!**")
                skipped_duplicates.append(doc)
                progress_bar.progress(current_progress)
                continue

        form_data_to_save = {
            "country": country,
            "visa_category": visa_type,
            "form_name": doc.get('title', 'Unknown Form/Page'),
            "form_id": "N/A",
            "description": doc.get('description', ''),
            "governing_authority": "N/A",
            "official_source_url": doc.get('url', ''),
            "discovered_by_query": doc.get('discovered_by_query', ''),
            "validation_warnings": [],
            "structured_data": {},
            "downloaded_file_path": None,
            "document_format": doc.get('file_type', 'UNKNOWN'),
            "processing_status": "failed",
            "last_fetched": datetime.now().isoformat(),
            "lawyer_review": {}
        }

        try:
            status_text.text(f"Step 1/4: Downloading document/page to local storage and Cloudinary...")
            progress_bar.progress(current_progress * 0.25)

            file_info = processor.download_document(doc['url'], country, visa_type)

            if not file_info:
                failed_docs.append({"doc": doc, "error": "Download failed or file invalid", "step": "download"})
                continue

            form_data_to_save["downloaded_file_path"] = file_info['file_path']
            form_data_to_save["document_format"] = file_info['file_format']

            status_text.text(f"Step 2/4: Extracting text...")
            progress_bar.progress(current_progress * 0.5)

            extracted_text = processor.extract_text(file_info['file_path'])

            if not extracted_text or len(extracted_text.strip()) < 50:
                st.warning(f"Low text content ({len(extracted_text.strip())} chars) for '{doc['title'][:50]}...'. Attempting AI processing anyway for summary.")
                form_data_to_save["processing_status"] = "low_text_content"
                form_data_to_save["validation_warnings"].append("Document had low text content, AI summary might be limited.")

            doc_info_for_ai = {**doc, **file_info}

            if validate_with_ai:
                status_text.text(f"Step 3/4: AI processing (Extraction & Validation)...")
                progress_bar.progress(current_progress * 0.75)

                ai_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)

                if not ai_extracted_data:
                    failed_docs.append({"doc": doc, "error": "AI extraction failed or returned invalid data", "step": "ai_extraction"})
                    form_data_to_save["validation_warnings"].append("AI extraction failed or returned invalid data")
                    form_data_to_save["processing_status"] = "ai_extraction_failed"
                else:
                    form_data_to_save["structured_data"] = ai_extracted_data

                    form_data_to_save['country'] = ai_extracted_data.get('country', country)
                    form_data_to_save['visa_category'] = ai_extracted_data.get('visa_category', visa_type)

                    form_data_to_save['form_name'] = ai_extracted_data.get('form_name', form_data_to_save['form_name'])
                    form_data_to_save['form_id'] = ai_extracted_data.get('form_id', form_data_to_save['form_id'])
                    form_data_to_save['description'] = ai_extracted_data.get('description', form_data_to_save['description'])
                    form_data_to_save['governing_authority'] = ai_extracted_data.get('governing_authority', form_data_to_save['governing_authority'])

                    validation_warnings = ai_service.validate_form_data(form_data_to_save["structured_data"])
                    form_data_to_save['validation_warnings'] = validation_warnings
                    form_data_to_save["processing_status"] = "validated" if not validation_warnings else "validated_with_warnings"
            else:
                form_data_to_save["validation_warnings"].append("AI processing skipped by user")
                form_data_to_save["processing_status"] = "downloaded_only"
                # FIX 1: Removed invalid escape sequences
                form_data_to_save["structured_data"] = {
                    "extracted_text_length": len(extracted_text),
                    "file_info": file_info,
                    "full_markdown_summary": f"Document text extracted (AI processing skipped):\n\n```\n{extracted_text[:1000]}...\n```"
                }

            if save_to_db:
                status_text.text(f"Step 4/4: Saving to database...")

                form_id = db.insert_form(form_data_to_save)
                if form_id:
                    form_data_to_save['id'] = form_id
                    processed_forms.append(form_data_to_save)
                    st.success(f"✅ Processed and Saved: {form_data_to_save.get('form_name', 'Unknown Form/Page')[:50]}...")

                    db.insert_document(form_id, file_info)

                else:
                    failed_docs.append({"doc": doc, "error": "Database save failed (check logs for details)", "step": "database"})
            else:
                processed_forms.append(form_data_to_save)
                st.success(f"✅ Processed (not saved to DB): {form_data_to_save.get('form_name', 'Unknown Form/Page')[:50]}...")

        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            st.error(f"❌ Failed: {doc['title'][:50]}... - {error_msg}")
            failed_docs.append({"doc": doc, "error": error_msg, "step": "unknown"})

            with st.expander(f"Debug Info for {doc['title'][:50]}..."):
                st.code(traceback.format_exc())

    progress_bar.progress(current_progress)

    with results_container:
        st.subheader("📊 Processing Results")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("✅ Successful", len(processed_forms))

        with col2:
            st.metric("❌ Failed", len(failed_docs))

        with col3:
            st.metric("⏩ Skipped Duplicates", len(skipped_duplicates))

        with col4:
            total_attempted = len(processed_forms) + len(failed_docs) + len(skipped_duplicates)
            success_rate = (len(processed_forms) / total_attempted) * 100 if total_attempted > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")

        if processed_forms:
            st.subheader("✅ Successfully Processed Documents/Pages")
            for form in processed_forms:
                clean_form_name = clean_html_text(form.get('form_name', 'Unknown Form/Page'))
                clean_form_id = clean_html_text(form.get('form_id', 'N/A'))
                with st.expander(f"📋 {clean_form_name} (ID: {clean_form_id})"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Country:** {clean_html_text(form.get('country', 'N/A'))}")
                        st.write(f"**Visa Category:** {clean_html_text(form.get('visa_category', 'N/A'))}")
                        st.write(f"**Authority:** {clean_html_text(form.get('governing_authority', 'N/A'))}")
                        st.write(f"**Database ID:** {form.get('id', 'Not saved')}")

                    with col2:
                        st.write(f"**Processing Status:** {form.get('processing_status', 'N/A')}")
                        st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                        document_info_from_db = db.get_document_by_form_id(form['id'])
                        if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                            st.write(f"**Cloudinary URL:** [Link]({document_info_from_db['cloudinary_url']})")
                        else:
                            st.write(f"**Cloudinary URL:** N/A")
                        st.write(f"**Text Length:** {form.get('structured_data', {}).get('extracted_text_length', 'N/A')} chars")
                        st.write(f"**Fees:** {form.get('structured_data', {}).get('fees', 'N/A')}")

                    if form.get('validation_warnings'):
                        st.warning("⚠️ Validation Warnings:")
                        for warning in form['validation_warnings']:
                            st.write(f"• {warning}")

        if failed_docs:
            st.subheader("❌ Failed Documents/Pages")
            for failed in failed_docs:
                clean_title = clean_html_text(failed['doc']['title'])
                with st.expander(f"❌ {clean_title[:80]}..."):
                    st.error(f"**Error:** {failed['error']}")
                    st.write(f"**Failed at step:** {failed['step']}")
                    st.write(f"**URL:** {failed['doc']['url']}")

        if skipped_duplicates:
            st.subheader("⏩ Skipped Duplicate Documents/Pages")
            for skipped in skipped_duplicates:
                clean_title = clean_html_text(skipped['title'])
                with st.expander(f"⏩ {clean_title[:80]}..."):
                    st.info(f"**URL:** {skipped['url']}")
                    st.info("This document/page was skipped because its URL already exists in the database.")


def document_viewer_page(db, processor, ai_service):
    # Custom CSS for professional styling with dark mode support
    st.markdown("""
    <style>
    /* Dark mode detection - Multiple approaches for better compatibility */
    @media (prefers-color-scheme: dark) {
        .document-card-wrapper {
            background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%) !important;
            border: 2px solid #4a5568 !important;
            color: #f7fafc !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
        }
        .document-card-wrapper h3 {
            color: #f7fafc !important;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.8) !important;
        }
        .document-card-wrapper p {
            color: #e2e8f0 !important;
            opacity: 0.95 !important;
        }
        .document-card-wrapper strong {
            color: #f7fafc !important;
        }
        .metric-card {
            background: #2d3748 !important;
            color: #f7fafc !important;
            border: 1px solid #4a5568 !important;
        }
        .filter-container {
            background: #1a202c !important;
            color: #f7fafc !important;
            border: 1px solid #4a5568 !important;
        }
        .document-preview {
            background: #1a202c !important;
            color: #f7fafc !important;
            border: 1px solid #4a5568 !important;
        }
        .document-preview h2 {
            color: #f7fafc !important;
        }
        .document-preview p {
            color: #e2e8f0 !important;
        }
        .tab-container {
            background: #1a202c !important;
            color: #f7fafc !important;
            border: 1px solid #4a5568 !important;
        }
        .download-section {
            background: linear-gradient(45deg, #4c51bf 0%, #553c9a 100%) !important;
            color: #f7fafc !important;
        }
    }

    /* Streamlit dark theme detection via CSS variables */
    [data-theme="dark"] .document-card-wrapper,
    .stApp[data-theme="dark"] .document-card-wrapper {
        background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%) !important;
        border: 2px solid #4a5568 !important;
        color: #f7fafc !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
    }

    .document-card-wrapper {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        color: white;
        transition: transform 0.3s ease;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .document-card-wrapper:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.15);
    }
    .document-card-wrapper h3 {
        color: white !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        margin-bottom: 15px !important;
        font-size: 1.1rem !important;
    }
    .document-card-wrapper p {
        color: white !important;
        opacity: 0.95;
        margin: 5px 0 !important;
        font-size: 0.9rem !important;
    }
    .document-card-wrapper strong {
        color: white !important;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        margin: 5px 0;
        text-shadow: none;
    }
    .status-validated { background: #28a745; color: white; }
    .status-warnings { background: #ffc107; color: black; }
    .status-failed { background: #dc3545; color: white; }
    .status-pending { background: #6c757d; color: white; }
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        margin: 10px 0;
    }
    .filter-container {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    .document-preview {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 20px 0;
    }
    .tab-container {
        background: white;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .download-section {
        background: linear-gradient(45deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }

    /* Force high contrast for better visibility */
    .document-card-wrapper * {
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
    }
    .document-card-wrapper h3,
    .document-card-wrapper p,
    .document-card-wrapper strong {
        color: inherit !important;
        opacity: 1 !important;
    }

    /* Additional dark mode override for Streamlit's specific classes */
    .stApp.dark .document-card-wrapper,
    [data-testid="stApp"][data-theme="dark"] .document-card-wrapper {
        background: linear-gradient(135deg, #1a202c 0%, #2d3748 100%) !important;
        border: 2px solid #4a5568 !important;
        color: #f7fafc !important;
    }

    /* High contrast text for all themes */
    .document-card-wrapper h3 {
        font-weight: 700 !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7) !important;
    }

    .document-card-wrapper p {
        font-weight: 500 !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.6) !important;
    }
    </style>

    <script>
    // Dynamic theme detection for Streamlit
    function updateThemeClasses() {
        const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const body = document.body;

        if (isDark) {
            body.classList.add('dark-mode');
        } else {
            body.classList.remove('dark-mode');
        }
    }

    // Check theme on load and when it changes
    updateThemeClasses();
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateThemeClasses);
    }
    </script>
    """, unsafe_allow_html=True)

    st.header("📄 Professional Document Viewer")
    st.markdown("**Advanced document management with AI-powered insights**")

    # Initialize session state
    if 'selected_form_id' not in st.session_state:
        st.session_state.selected_form_id = None
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = "overview"

    forms = db.get_forms()

    if not forms:
        st.info("🔍 No documents found. Use the Document Discovery page to find and process documents first.")
        return

    # Find selected form
    selected_form = None
    if st.session_state.selected_form_id:
        for form in forms:
            if form['id'] == st.session_state.selected_form_id:
                selected_form = form
                break

    if selected_form:
        # === DETAILED DOCUMENT VIEW ===
        clean_form_name = clean_html_text(selected_form.get('form_name', 'Unknown Document'))
        clean_form_id = clean_html_text(selected_form.get('form_id', 'N/A'))
        clean_country = clean_html_text(selected_form.get('country', 'N/A'))

        st.markdown(f"""
        <div class="document-preview">
            <h2>📋 {clean_form_name}</h2>
            <p><strong>Form ID:</strong> {clean_form_id} |
               <strong>Country:</strong> {clean_country} |
               <strong>Status:</strong> {selected_form.get('processing_status', 'Unknown').replace('_', ' ').title()}</p>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        col_nav1, col_nav2, col_nav3, col_nav4 = st.columns([1, 1, 1, 3])
        with col_nav1:
            if st.button("⬅️ Back to List", type="secondary"):
                st.session_state.selected_form_id = None
                st.rerun()
        with col_nav2:
            if st.button("📄 Overview", type="primary" if st.session_state.current_tab == "overview" else "secondary"):
                st.session_state.current_tab = "overview"
                st.rerun()
        with col_nav3:
            if st.button("📖 Full Document", type="primary" if st.session_state.current_tab == "document" else "secondary"):
                st.session_state.current_tab = "document"
                st.rerun()
        with col_nav4:
            if st.button("🤖 AI Analysis", type="primary" if st.session_state.current_tab == "ai" else "secondary"):
                st.session_state.current_tab = "ai"
                st.rerun()

        document_info_from_db = db.get_document_by_form_id(selected_form['id'])
        downloaded_file_path = selected_form.get('downloaded_file_path')  # FIX 3: Defined here for all tabs

        # Tab Content
        if st.session_state.current_tab == "overview":
            # Overview Tab
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### 📋 Document Information")
                st.write(f"**Country:** {clean_html_text(selected_form.get('country', 'N/A'))}")
                st.write(f"**Visa Category:** {clean_html_text(selected_form.get('visa_category', 'N/A'))}")
                st.write(f"**Form Name:** {clean_html_text(selected_form.get('form_name', 'N/A'))}")
                st.write(f"**Form ID:** {clean_html_text(selected_form.get('form_id', 'N/A'))}")
                st.write(f"**Authority:** {clean_html_text(selected_form.get('governing_authority', 'N/A'))}")

                if document_info_from_db:
                    st.write(f"**File Format:** {document_info_from_db.get('file_format', 'Unknown')}")
                    st.write(f"**File Size:** {document_info_from_db.get('file_size_bytes', 0):,} bytes")

            with col2:
                st.markdown("### ⚙️ Processing Details")
                structured_data = selected_form.get('structured_data', {})  # FIX 4: Defined here
                st.write(f"**Processing Status:** {selected_form.get('processing_status', 'N/A').replace('_', ' ').title()}")
                st.write(f"**Processing Time:** {structured_data.get('processing_time', 'N/A')}")
                st.write(f"**Fees:** {structured_data.get('fees', 'N/A')}")
                st.write(f"**Submission Method:** {structured_data.get('submission_method', 'N/A')}")
                st.write(f"**Last Updated:** {selected_form.get('created_at', 'N/A')}")

            # Description
            st.markdown("### 📝 Description")
            st.write(clean_html_text(selected_form.get('description', 'No description available')))

            # Supporting Documents
            if structured_data.get('supporting_documents'):
                st.markdown("### 📎 Required Supporting Documents")
                for i, doc in enumerate(structured_data['supporting_documents'], 1):
                    st.write(f"{i}. {doc}")

            # Validation Warnings
            if selected_form.get('validation_warnings'):
                st.markdown("### ⚠️ Validation Warnings")
                for warning in selected_form['validation_warnings']:
                    st.warning(f"⚠️ {warning}")

        elif st.session_state.current_tab == "document":
            # Document Tab
            st.markdown("### 📖 Original Document")

            if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                file_format = document_info_from_db.get('file_format', '').upper()
                st.markdown(f"**File:** {document_info_from_db.get('filename', 'Unknown')} ({file_format})")

                # Display based on format
                if file_format == 'PDF':
                    st.markdown("**PDF Preview:**")
                    st.markdown(f'<iframe src="{document_info_from_db["cloudinary_url"]}" width="100%" height="800px" style="border-radius: 10px;"></iframe>', unsafe_allow_html=True)
                elif file_format in ['JPG', 'JPEG', 'PNG', 'GIF']:
                    st.image(document_info_from_db['cloudinary_url'], caption="Document Image", use_column_width=True)
                elif file_format == 'HTML':
                    st.markdown(f"**HTML Document:** [Open in New Tab]({document_info_from_db['cloudinary_url']})")
                    # Try to show a preview of HTML content
                    if downloaded_file_path and Path(downloaded_file_path).exists():
                        try:
                            with open(downloaded_file_path, 'r', encoding='utf-8') as f:
                                html_content = f.read()
                            st.code(html_content[:2000] + "..." if len(html_content) > 2000 else html_content, language='html')
                        except Exception as e:
                            st.error(f"Error reading HTML file: {e}")
                else:
                    st.markdown(f"[📎 Download Original Document]({document_info_from_db['cloudinary_url']})")

            # Extracted Text
            st.markdown("### 📝 Extracted Text Content")
            if downloaded_file_path and Path(downloaded_file_path).exists():
                try:
                    extracted_text = processor.extract_text(downloaded_file_path)
                    if extracted_text:
                        # Text statistics
                        word_count = len(extracted_text.split())
                        char_count = len(extracted_text)
                        line_count = len(extracted_text.split('\n'))

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Words", f"{word_count:,}")
                        with col2:
                            st.metric("Characters", f"{char_count:,}")
                        with col3:
                            st.metric("Lines", f"{line_count:,}")

                        st.text_area(
                            "Full Extracted Text:",
                            value=extracted_text,
                            height=400,
                            disabled=True,
                            key=f"extracted_text_{selected_form['id']}"
                        )
                    else:
                        st.warning("⚠️ No text could be extracted from this document.")
                except Exception as e:
                    st.error(f"❌ Error extracting text: {e}")
            else:
                st.warning("⚠️ Original document file not found locally for text extraction.")

        elif st.session_state.current_tab == "ai":
            # AI Analysis Tab
            structured_data = selected_form.get('structured_data', {})  # FIX 4: Defined here
            full_markdown = structured_data.get('full_markdown_summary') if structured_data else None

            if full_markdown:
                st.markdown("### 🤖 AI-Generated Comprehensive Analysis")
                st.markdown(full_markdown)

                # AI Extracted Fields
                st.markdown("### 📊 Structured Data Extracted by AI")

                col1, col2 = st.columns(2)
                with col1:
                    if structured_data.get('target_applicants'):
                        st.write(f"**Target Applicants:** {structured_data['target_applicants']}")
                    if structured_data.get('language'):
                        st.write(f"**Language:** {structured_data['language']}")
                    if structured_data.get('fees'):
                        st.write(f"**Fees:** {structured_data['fees']}")

                with col2:
                    if structured_data.get('processing_time'):
                        st.write(f"**Processing Time:** {structured_data['processing_time']}")
                    if structured_data.get('submission_method'):
                        st.write(f"**Submission Method:** {structured_data['submission_method']}")

                # Required Fields
                if structured_data.get('required_fields'):
                    st.markdown("### 📝 Required Form Fields")
                    for field in structured_data['required_fields']:
                        with st.expander(f"📄 {field.get('name', 'Unknown Field')}"):
                            st.write(f"**Type:** {field.get('type', 'N/A')}")
                            st.write(f"**Description:** {field.get('description', 'N/A')}")
                            if field.get('example_value'):
                                st.write(f"**Example:** {field['example_value']}")
            else:
                st.info("🤖 No AI analysis available for this document.")

        # Download Section
        st.markdown('<div class="download-section">', unsafe_allow_html=True)
        st.markdown("### 📥 Download Options")

        col1, col2, col3, col4 = st.columns(4)

        # Original Document
        with col1:
            if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                st.markdown(f"[📎 Original Document]({document_info_from_db['cloudinary_url']})")
            elif downloaded_file_path and Path(downloaded_file_path).exists():
                original_file_content = processor.get_file_content_bytes_from_path(downloaded_file_path)
                if original_file_content:
                    st.download_button(
                        "📎 Original",
                        data=original_file_content,
                        file_name=Path(downloaded_file_path).name,
                        mime=mimetypes.guess_type(downloaded_file_path)[0] or "application/octet-stream"
                    )
            else:
                st.info("Not available")

        # AI Summary
        with col2:
            structured_data = selected_form.get('structured_data', {})  # Define structured_data here
            if structured_data and structured_data.get('full_markdown_summary'):
                st.download_button(
                    "📄 AI Summary",
                    data=structured_data['full_markdown_summary'].encode('utf-8'),
                    file_name=f"{selected_form.get('form_id', 'summary')}_summary.md",
                    mime="text/markdown"
                )
            else:
                st.info("Not available")

        # JSON Data
        with col3:
            if structured_data:
                def json_serializer(obj):
                    """JSON serializer function that handles datetime objects"""
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

                st.download_button(
                    "📊 JSON Data",
                    data=json.dumps(structured_data, indent=2, ensure_ascii=False, default=json_serializer).encode('utf-8'),
                    file_name=f"{selected_form.get('form_id', 'data')}_data.json",
                    mime="application/json"
                )
            else:
                st.info("Not available")

        # Extracted Text
        with col4:
            if downloaded_file_path and Path(downloaded_file_path).exists():
                try:
                    extracted_text = processor.extract_text(downloaded_file_path)
                    if extracted_text:
                        st.download_button(
                            "📝 Text",
                            data=extracted_text.encode('utf-8'),
                            file_name=f"{selected_form.get('form_id', 'text')}_extracted.txt",
                            mime="text/plain"
                        )
                    else:
                        st.info("Not available")
                except:
                    st.info("Not available")
            else:
                st.info("Not available")

        st.markdown('</div>', unsafe_allow_html=True)

    else:
        # === DOCUMENT BROWSER VIEW ===

        # Statistics Dashboard
        st.markdown("### 📊 Document Statistics")

        # Calculate statistics
        total_docs = len(forms)
        pdf_docs = len([f for f in forms if db.get_document_by_form_id(f['id']) and db.get_document_by_form_id(f['id']).get('file_format') == 'PDF'])
        html_docs = len([f for f in forms if db.get_document_by_form_id(f['id']) and db.get_document_by_form_id(f['id']).get('file_format') == 'HTML'])
        ai_processed = len([f for f in forms if f.get('structured_data', {}).get('full_markdown_summary')])

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #667eea; margin: 0;">📄 {total_docs}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Total Documents</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #dc3545; margin: 0;">📕 {pdf_docs}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">PDF Documents</p>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #28a745; margin: 0;">🌐 {html_docs}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">HTML Pages</p>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #ffc107; margin: 0;">🤖 {ai_processed}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">AI Processed</p>
            </div>
            """, unsafe_allow_html=True)

        # Advanced Filters
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.markdown("### 🔍 Advanced Filters")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            all_countries = sorted(list(set(f.get('country', 'Unknown') for f in forms if f.get('country'))))
            selected_country = st.selectbox("🌍 Country:", ["All"] + all_countries)

        with col2:
            all_visa_categories = sorted(list(set(f.get('visa_category', 'Unknown') for f in forms if f.get('visa_category'))))
            selected_visa_category = st.selectbox("🛂 Visa Type:", ["All"] + all_visa_categories)

        with col3:
            # Get all file formats
            all_formats = set()
            for f in forms:
                doc_info = db.get_document_by_form_id(f['id'])
                if doc_info and doc_info.get('file_format'):
                    all_formats.add(doc_info['file_format'])
            all_formats = sorted(list(all_formats))
            selected_format = st.selectbox("📄 Format:", ["All"] + all_formats)

        with col4:
            processing_statuses = sorted(list(set(f.get('processing_status', 'Unknown') for f in forms if f.get('processing_status'))))
            selected_status = st.selectbox("⚙️ Status:", ["All"] + processing_statuses)

        # Search
        search_query = st.text_input("🔍 Search documents (name, ID, description):", placeholder="Type to search...")

        st.markdown('</div>', unsafe_allow_html=True)

        # Apply Filters
        filtered_forms = forms

        if selected_country != "All":
            filtered_forms = [f for f in filtered_forms if f.get('country') == selected_country]

        if selected_visa_category != "All":
            filtered_forms = [f for f in filtered_forms if f.get('visa_category') == selected_visa_category]

        if selected_format != "All":
            filtered_forms = [f for f in filtered_forms if db.get_document_by_form_id(f['id']) and db.get_document_by_form_id(f['id']).get('file_format') == selected_format]

        if selected_status != "All":
            filtered_forms = [f for f in filtered_forms if f.get('processing_status') == selected_status]

        if search_query:
            search_query_lower = search_query.lower()
            # FIX 2: Handle None values in search
            filtered_forms = [
                f for f in filtered_forms
                if (search_query_lower in (f.get('form_name') or '').lower() or
                   search_query_lower in (f.get('form_id') or '').lower() or
                   search_query_lower in (f.get('description') or '').lower())
            ]

        st.markdown(f"### 📚 Documents ({len(filtered_forms)} found)")

        # Document Cards
        if filtered_forms:
            # Display 2 cards per row for better readability
            for i in range(0, len(filtered_forms), 2):
                cols = st.columns(2)

                for j, col in enumerate(cols):
                    form_idx = i + j
                    if form_idx < len(filtered_forms):
                        form = filtered_forms[form_idx]
                        document_info = db.get_document_by_form_id(form['id'])

                        with col:
                            # Get status info
                            status = form.get('processing_status', 'unknown')
                            file_format = document_info.get('file_format', 'Unknown') if document_info else 'Unknown'

                            # Status badge class
                            status_class = {
                                'validated': 'status-validated',
                                'validated_with_warnings': 'status-warnings',
                                'ai_extraction_failed': 'status-failed',
                                'downloaded_only': 'status-pending'
                            }.get(status, 'status-pending')

                            # Format icon
                            format_icon = {
                                'PDF': '📕',
                                'HTML': '🌐',
                                'DOCX': '📘',
                                'DOC': '📘',
                                'XLSX': '📊',
                                'XLS': '📊'
                            }.get(file_format, '📄')

                            # Clean text content to prevent HTML tags from showing
                            clean_form_name = clean_html_text(form.get('form_name', 'Unknown Document'))
                            clean_description = clean_html_text(form.get('description', 'No description available'))
                            clean_country = clean_html_text(form.get('country', 'N/A'))
                            clean_visa_category = clean_html_text(form.get('visa_category', 'N/A'))
                            clean_form_id = clean_html_text(form.get('form_id', 'N/A'))

                            # Use Streamlit container for the card instead of HTML template
                            with st.container():
                                # Apply custom CSS class
                                st.markdown(f'<div class="document-card-wrapper">', unsafe_allow_html=True)

                                # Header with title and format badge
                                col_title, col_badge = st.columns([4, 1])
                                with col_title:
                                    st.markdown(f"### {format_icon} {clean_form_name[:50]}{'...' if len(clean_form_name) > 50 else ''}")
                                with col_badge:
                                    st.markdown(f'<span class="{status_class} status-badge">{file_format}</span>', unsafe_allow_html=True)

                                # Document details
                                st.markdown(f"**🌍 Country:** {clean_country}")
                                st.markdown(f"**🛂 Visa Type:** {clean_visa_category}")
                                st.markdown(f"**🆔 Form ID:** {clean_form_id}")
                                st.markdown(f"**Status:** {status.replace('_', ' ').title()}")

                                # Description
                                if clean_description:
                                    st.markdown(f"**Description:** {clean_description[:100]}{'...' if len(clean_description) > 100 else ''}")

                                st.markdown('</div>', unsafe_allow_html=True)

                            # View Details Button
                            if st.button(
                                "👁️ View Details", 
                                key=f"view_details_{form['id']}",
                                type="primary",
                                use_container_width=True
                            ):
                                st.session_state.selected_form_id = form['id']
                                st.session_state.current_tab = "overview"
                                st.rerun()
        else:
            st.info("🔍 No documents match your current filters. Try adjusting the search criteria.")

def validation_panel_page(db, processor, ai_service):
    st.markdown("""
    <style>
    .validation-header {
        background: linear-gradient(45deg, #11998e 0%, #38ef7d 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .filter-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    .document-card-validation {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #11998e;
    }
    </style>

    <div class="validation-header">
        <h1>✅ Validation & Lawyer Review Panel</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0; opacity: 0.9;">
            Review and validate extracted data, and manage lawyer approvals for documents and informational pages
        </p>
    </div>
    """, unsafe_allow_html=True)

    forms = db.get_forms()

    if forms:
        st.success(f"✅ Found {len(forms)} documents/pages for review")

        st.markdown('<div class="filter-section">', unsafe_allow_html=True)
        st.markdown("### 🔍 Filter Documents")
        review_filter = st.selectbox(
            "Filter by review status:",
            ["All", "Pending Review", "Approved", "Approved with Comments", "Needs Revision", "Downloaded Only", "Partial AI Failure", "AI Extraction Failed", "Low Text Content"]
        )
        st.markdown('</div>', unsafe_allow_html=True)

        filtered_forms = forms
        if review_filter != "All":
            if review_filter == "Pending Review":
                filtered_forms = [
                    form for form in forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
                ]
            elif review_filter == "Downloaded Only":
                filtered_forms = [
                    form for form in forms 
                    if form.get('processing_status') == 'downloaded_only'
                ]
            elif review_filter == "Partial AI Failure":
                filtered_forms = [
                    form for form in forms 
                    if form.get('processing_status') == 'validated_with_warnings'
                ]
            elif review_filter == "AI Extraction Failed":
                 filtered_forms = [
                    form for form in forms 
                    if form.get('processing_status') == 'ai_extraction_failed'
                ]
            elif review_filter == "Low Text Content":
                 filtered_forms = [
                    form for form in forms 
                    if form.get('processing_status') == 'low_text_content'
                ]
            else:
                filtered_forms = [
                    form for form in forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == review_filter 
                ]

        if filtered_forms:
            for form in filtered_forms:
                clean_form_name = clean_html_text(form['form_name'])
                clean_country = clean_html_text(form['country'])
                with st.expander(f"📋 {clean_form_name} - {clean_country} (Status: {form.get('processing_status', 'N/A')})"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(f"**Form ID:** {clean_html_text(form['form_id'])}")
                        st.write(f"**Description:** {clean_html_text(form.get('description', 'N/A'))}")
                        st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                        st.write(f"**Official Source URL:** {form.get('official_source_url', 'N/A')}")

                        document_info_from_db = db.get_document_by_form_id(form['id'])
                        if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                            st.write(f"**Cloudinary Original URL:** [Link]({document_info_from_db['cloudinary_url']})")
                        else:
                            st.write(f"**Cloudinary Original URL:** N/A")

                        if form.get('validation_warnings'):
                            st.subheader("⚠️ AI Validation Warnings")
                            for warning in form['validation_warnings']:
                                st.warning(warning)

                        full_markdown = form.get('structured_data', {}).get('full_markdown_summary')
                        if full_markdown:
                            st.subheader("AI's Comprehensive Summary")
                            st.markdown(full_markdown[:500] + "..." if len(full_markdown) > 500 else full_markdown)
                            with st.expander("View Full Summary"):
                                st.markdown(full_markdown)


                    with col2:
                        st.subheader("Lawyer Review")

                        current_review = form.get('lawyer_review') or {}
                        st.write(f"**Status:** {current_review.get('approval_status', 'Pending Review')}")

                        if current_review.get('reviewer_name'):
                            st.write(f"**Reviewer:** {current_review['reviewer_name']}")
                            st.write(f"**Date:** {current_review.get('review_date', 'N/A')}")
                            st.write(f"**Comments:** {current_review.get('comments', 'None')}")

                        with st.form(f"review_form_{form['id']}"):
                            reviewer_name = st.text_input("Reviewer Name", value=current_review.get('reviewer_name', ''))
                            approval_status = st.selectbox(
                                "Approval Status",
                                ["Pending Review", "Approved", "Approved with Comments", "Needs Revision"],
                                index=["Pending Review", "Approved", "Approved with Comments", "Needs Revision"].index(
                                    current_review.get('approval_status', 'Pending Review')
                                )
                            )
                            comments = st.text_area("Comments", value=current_review.get('comments', ''))

                            col_buttons_review, col_buttons_ai = st.columns(2)

                            with col_buttons_review:
                                if st.form_submit_button("Update Review"):
                                    review_data = {
                                        "reviewer_name": reviewer_name,
                                        "review_date": datetime.now().isoformat(),
                                        "approval_status": approval_status,
                                        "comments": comments
                                    }

                                    if db.update_lawyer_review(form['id'], review_data):
                                        st.success("Review updated successfully!")
                                        st.rerun()
                                    else:
                                        st.error("Failed to update review")

                            with col_buttons_ai:
                                if st.form_submit_button("✨ Re-run AI Extraction & Validation"):
                                    if not form.get('downloaded_file_path') or not Path(form['downloaded_file_path']).exists():
                                        st.error("Cannot re-run AI: Document/page file not found locally.")
                                    else:
                                        with st.spinner("Re-running AI processing and validation..."):
                                            try:
                                                extracted_text = processor.extract_text(form['downloaded_file_path'])

                                                if not extracted_text or len(extracted_text.strip()) < 50:
                                                    st.warning("Low text content for AI re-validation. AI summary might be limited.")

                                                doc_info_for_ai = {
                                                    'filename': Path(form['downloaded_file_path']).name,
                                                    'download_url': form['official_source_url'],
                                                    'file_format': form['document_format'],
                                                    'file_path': form['downloaded_file_path'],
                                                    'discovered_by_query': form['discovered_by_query']
                                                }

                                                re_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)

                                                if re_extracted_data:
                                                    validation_warnings = ai_service.validate_form_data(re_extracted_data)

                                                    new_processing_status = "validated" if not validation_warnings else "validated_with_warnings"
                                                    if not extracted_text or len(extracted_text.strip()) < 50:
                                                        new_processing_status = "low_text_content"

                                                    update_success = db.update_form_fields(
                                                        form['id'],
                                                        {
                                                            "structured_data": re_extracted_data,
                                                            "validation_warnings": validation_warnings,
                                                            "processing_status": new_processing_status,
                                                            "country": re_extracted_data.get('country', form['country']),
                                                            "visa_category": re_extracted_data.get('visa_category', form['visa_category']),
                                                            "form_name": re_extracted_data.get('form_name', form['form_name']),
                                                            "form_id": re_extracted_data.get('form_id', form['form_id']),
                                                            "description": re_extracted_data.get('description', form['description']),
                                                            "governing_authority": re_extracted_data.get('governing_authority', form['governing_authority'])
                                                        }
                                                    )

                                                    if update_success:
                                                        st.success("AI extraction and validation re-run successfully!")
                                                        st.rerun()
                                                    else:
                                                        st.error("Failed to update form with new AI results.")
                                                else:
                                                    st.error("AI re-extraction failed. Cannot proceed with validation.")
                                            except Exception as e:
                                                st.error(f"Error during AI re-validation: {e}")
                                                st.code(traceback.format_exc())
    else:
        st.info(f"No forms/pages found with status: {review_filter}")

    st.info("No documents/pages found for review.")

def export_panel_page(db, export_service):
    st.markdown("""
    <style>
    .export-header {
        background: linear-gradient(45deg, #ffecd2 0%, #fcb69f 100%);
        padding: 2rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .export-options {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .export-button {
        width: 100%;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 10px;
        font-weight: bold;
        transition: transform 0.3s ease;
    }
    .export-button:hover {
        transform: translateY(-2px);
    }
    </style>

    <div class="export-header">
        <h1>📊 Export Panel</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0;">
            Export processed documents and extracted data in various formats
        </p>
    </div>
    """, unsafe_allow_html=True)

    forms = db.get_forms()

    if forms:
        st.success(f"✅ Found {len(forms)} documents/pages available for export")

        st.markdown('<div class="export-options">', unsafe_allow_html=True)
        st.markdown("### 🔧 Export Options")

        col1, col2 = st.columns(2)

        with col1:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + list(set(form['country'] for form in forms))
            )

        with col2:
            status_filter = st.selectbox(
                "Filter by Review Status:",
                ["All", "Approved", "Pending Review", "Needs Revision", "Downloaded Only", "Partial AI Failure", "AI Extraction Failed", "Low Text Content"]
            )

        filtered_forms = forms
        if country_filter != "All":
            filtered_forms = [form for form in filtered_forms if form['country'] == country_filter]

        if status_filter != "All":
            if status_filter == "Pending Review":
                filtered_forms = [
                    form for form in filtered_forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
                ]
            elif status_filter == "Downloaded Only":
                filtered_forms = [
                    form for form in filtered_forms 
                    if form.get('processing_status') == 'downloaded_only'
                ]
            elif status_filter == "Partial AI Failure":
                filtered_forms = [
                    form for form in filtered_forms 
                    if form.get('processing_status') == 'validated_with_warnings'
                ]
            elif status_filter == "AI Extraction Failed":
                filtered_forms = [
                    form for form in filtered_forms
                    if form.get('processing_status') == 'ai_extraction_failed'
                ]
            elif status_filter == "Low Text Content":
                filtered_forms = [
                    form for form in filtered_forms
                    if form.get('processing_status') == 'low_text_content'
                ]
            else:
                filtered_forms = [
                    form for form in filtered_forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == status_filter
                ]

        st.write(f"**Forms/Pages to export:** {len(filtered_forms)}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 📁 Export Actions")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📄 Export as JSON"):
                if len(filtered_forms) == 1:
                    form_data = filtered_forms[0].get('structured_data', {})
                    file_path, file_content, cloudinary_export_url = export_service.export_json(filtered_forms[0])
                    if file_content:
                        if cloudinary_export_url:
                            st.markdown(f"**Download JSON from Cloud:**")
                            st.markdown(f"[Click to Download]({cloudinary_export_url})")
                        else:
                            st.download_button(
                                label="Download JSON (Local)",
                                data=file_content,
                                file_name=Path(file_path).name,
                                mime="application/json",
                                key="download_json_single"
                            )
                elif len(filtered_forms) > 1:
                    st.info("Exporting multiple JSON files to the server and Cloudinary. Individual download buttons are not provided for batch exports.")
                    exported_files_count = 0
                    for form in filtered_forms:
                        file_path, _, cloudinary_export_url = export_service.export_json(form)
                        if file_path:
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} JSON files to server and Cloudinary.")
                else:
                    st.warning("No forms/pages selected for JSON export.")
                if cloudinary_export_url:
                    st.info(f"Debug: Cloudinary URL for JSON export: {cloudinary_export_url}")
                else:
                    st.warning("Debug: No Cloudinary URL returned for JSON export.")

        with col2:
            if st.button("📊 Export as Excel"):
                if filtered_forms:
                    forms_data_for_excel = []
                    for form in filtered_forms:
                        flat_form = {**form}
                        if 'structured_data' in form and form['structured_data'] is not None:
                            flat_form.update(form['structured_data'])
                        forms_data_for_excel.append(flat_form)

                    file_path, file_content, cloudinary_export_url = export_service.export_excel(forms_data_for_excel)
                    if file_content:
                        if cloudinary_export_url:
                            st.markdown(f"**Download Excel from Cloud:**")
                            st.markdown(f"[Click to Download]({cloudinary_export_url})")
                        else:
                            st.download_button(
                                label="Download Excel (Local)",
                                data=file_content,
                                file_name=Path(file_path).name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="download_excel"
                            )
                else:
                    st.warning("No forms/pages selected for Excel export.")
                if cloudinary_export_url:
                    st.info(f"Debug: Cloudinary URL for Excel export: {cloudinary_export_url}")
                else:
                    st.warning("Debug: No Cloudinary URL returned for Excel export.")

        with col3:
            if st.button("📋 Export Summaries (Markdown)"):
                if filtered_forms:
                    exported_files_count = 0
                    for form in filtered_forms:
                        summary_data_to_export = form.get('structured_data', {})
                        file_path, file_content, cloudinary_export_url = export_service.export_summary_markdown(form)
                        if file_content:
                            if cloudinary_export_url:
                                st.markdown(f"**Download {Path(file_path).name} from Cloud:**")
                                st.markdown(f"[Click to Download]({cloudinary_export_url})")
                            else:
                                st.download_button(
                                    label=f"Download {Path(file_path).name} (Local)",
                                    data=file_content,
                                    file_name=Path(file_path).name,
                                    mime="text/markdown",
                                    key=f"download_summary_{form['id']}"
                                )
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} summary files.")
                else:
                    st.warning("No forms/pages selected for summary export.")
                if cloudinary_export_url:
                    st.info(f"Debug: Cloudinary URL for Summary export: {cloudinary_export_url}")
                else:
                    st.warning("Debug: No Cloudinary URL returned for Summary export.")

        if filtered_forms:
            st.subheader("Preview of Forms/Pages to Export")

            preview_data = []
            for form in filtered_forms:
                preview_data.append({
                    "Country": clean_html_text(form['country']),
                    "Form Name": clean_html_text(form['form_name']),
                    "Form ID": clean_html_text(form['form_id']),
                    "Review Status": (form.get('lawyer_review') or {}).get('approval_status', 'Pending'),
                    "Processing Status": form.get('processing_status', 'N/A'),
                    "Last Updated": form['created_at']
                })

            df = pd.DataFrame(preview_data)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No documents/pages available for export.")

    st.markdown("---")
    # Add test export section
    st.subheader("🧪 Test Export (Troubleshooting)")
    st.markdown("Test the export functionality with a small sample before exporting the full database.")

    if st.button("🔍 Test Export (5 records)", type="secondary"):
        if not db or not db.database_url:
            st.error("❌ Database connection not available.")
        else:
            try:
                test_forms = db.get_forms()[:5]  # Get only first 5 records
                if test_forms:
                    import io
                    import pandas as pd

                    # Simple test export
                    test_df = pd.DataFrame([{
                        'id': form.get('id', ''),
                        'country': form.get('country', ''),
                        'form_name': form.get('form_name', ''),
                        'form_id': form.get('form_id', ''),
                        'created_at': str(form.get('created_at', ''))
                    } for form in test_forms])

                    csv_buffer = io.StringIO()
                    test_df.to_csv(csv_buffer, index=False)
                    csv_content = csv_buffer.getvalue().encode('utf-8')

                    st.success(f"✅ Test export successful! Found {len(test_forms)} records.")
                    st.download_button(
                        label="Download Test Export (CSV)",
                        data=csv_content,
                        file_name=f"test_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key="test_export_csv"
                    )
                else:
                    st.warning("No data found in database.")
            except Exception as test_error:
                st.error(f"❌ Test export failed: {str(test_error)}")

    st.markdown("---")
    st.subheader("🗄️ Complete Database Export")
    st.markdown("Export the entire database with all rows, columns, and fields in a single file that can be imported elsewhere.")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📄 Export Database as JSON", type="primary"):
            with st.spinner("Exporting complete database as JSON..."):
                file_path, file_content, cloudinary_export_url = export_service.export_full_database("json")
                if file_content:
                    if cloudinary_export_url:
                        st.markdown(f"**Download Complete Database (JSON) from Cloud:**")
                        st.markdown(f"[Click to Download]({cloudinary_export_url})")
                    else:
                        st.download_button(
                            label="Download Complete Database (JSON)",
                            data=file_content,
                            file_name=Path(file_path).name,
                            mime="application/json",
                            key="download_full_db_json"
                        )

    with col2:
        if st.button("📊 Export Database as CSV", type="primary"):
            # Check if database is available before export
            if not db or not db.database_url:
                st.error("❌ Database connection not available. Please check your database configuration.")
            else:
                with st.spinner("Exporting complete database as CSV..."):
                    try:
                        file_path, file_content, cloudinary_export_url = export_service.export_full_database("csv")
                        if file_content:
                            if cloudinary_export_url:
                                st.success("✅ Export completed successfully!")
                                st.markdown(f"**Download Complete Database (CSV) from Cloud:**")
                                st.markdown(f"[Click to Download]({cloudinary_export_url})")
                            else:
                                st.success("✅ Export completed successfully!")
                                st.download_button(
                                    label="Download Complete Database (CSV)",
                                    data=file_content,
                                    file_name=Path(file_path).name if file_path else f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv",
                                    key="download_full_db_csv"
                                )
                        else:
                            st.error("❌ Export failed. No data was generated.")
                    except Exception as export_error:
                        st.error(f"❌ Export failed: {str(export_error)}")
                        st.info("💡 This might be due to deployment constraints. Try exporting a smaller dataset or contact support.")

    with col3:
        if st.button("📈 Export Database as Excel", type="primary"):
            # Check if database is available before export
            if not db or not db.database_url:
                st.error("❌ Database connection not available. Please check your database configuration.")
            else:
                with st.spinner("Exporting complete database as Excel..."):
                    try:
                        file_path, file_content, cloudinary_export_url = export_service.export_full_database("xlsx")
                        if file_content:
                            if cloudinary_export_url:
                                st.success("✅ Export completed successfully!")
                                st.markdown(f"**Download Complete Database (Excel) from Cloud:**")
                                st.markdown(f"[Click to Download]({cloudinary_export_url})")
                            else:
                                st.success("✅ Export completed successfully!")
                                st.download_button(
                                    label="Download Complete Database (Excel)",
                                    data=file_content,
                                    file_name=Path(file_path).name if file_path else f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key="download_full_db_xlsx"
                                )
                        else:
                            st.error("❌ Export failed. No data was generated.")
                    except Exception as export_error:
                        st.error(f"❌ Export failed: {str(export_error)}")
                        st.info("💡 This might be due to deployment constraints. Try exporting a smaller dataset or contact support.")

    st.markdown("---")
    st.subheader("📦 Comprehensive USA Export")
    st.markdown("Generate a single report with all USA immigration forms, including links to original documents, JSON data, and Markdown summaries on Cloudinary.")
    if st.button("🚀 Generate Comprehensive USA Export Report", type="primary"):
        with st.spinner("Generating comprehensive USA export report..."):
            usa_forms = db.get_forms(country="USA")
            if usa_forms:
                report_path, report_content, cloudinary_report_url = export_service.generate_comprehensive_report(usa_forms)
                if report_content:
                    st.success("Comprehensive USA Export Report generated successfully!")
                    if cloudinary_report_url:
                        st.markdown(f"**Download Comprehensive USA Report from Cloud:**")
                        st.markdown(f"[Click to Download]({cloudinary_report_url})")
                    else:
                        st.download_button(
                            label="Download Comprehensive USA Report (Local)",
                            data=report_content,
                            file_name=Path(report_path).name,
                            mime="text/markdown",
                            key="download_usa_report"
                        )
                else:
                    st.error("Failed to generate comprehensive USA export report.")
            else:
                st.warning("No USA immigration forms found in the database to export.")


def database_viewer_page(db):
    st.markdown("""
    <style>
    .database-header {
        background: linear-gradient(45deg, #a8edea 0%, #fed6e3 100%);
        padding: 2rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .stats-container {
        display: flex;
        justify-content: space-around;
        margin: 2rem 0;
    }
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        min-width: 150px;
    }
    .search-section {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
    }
    </style>

    <div class="database-header">
        <h1>🗄️ Database Viewer</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0;">
            Browse and search all processed documents and informational pages in the database
        </p>
    </div>
    """, unsafe_allow_html=True)

    forms = db.get_forms()

    if forms:
        st.markdown("### 📊 Database Statistics")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #667eea; margin: 0;">📄 {len(forms)}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Total Forms/Pages</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            countries_in_db = set(form['country'] for form in forms)
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #11998e; margin: 0;">🌍 {len(countries_in_db)}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Countries</p>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            approved_forms = len([
                form for form in forms
                if (form.get('lawyer_review') or {}).get('approval_status') == 'Approved'
            ])
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #28a745; margin: 0;">✅ {approved_forms}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Approved Forms/Pages</p>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            pending_forms = len([
                form for form in forms
                if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
            ])
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #ffc107; margin: 0;">⏳ {pending_forms}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Pending Review</p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="search-section">', unsafe_allow_html=True)
        st.markdown("### 🔍 Search & Filter")

        col1, col2, col3 = st.columns(3)

        with col1:
            search_term = st.text_input("Search forms/pages (name, ID, description):")

        with col2:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + sorted(list(set(form['country'] for form in forms)))
            )
        with col3:
            processing_status_filter = st.selectbox(
                "Filter by Processing Status:",
                ["All", "validated", "validated_with_warnings", "downloaded_only", "ai_extraction_failed", "failed", "low_text_content"]
            )

        filtered_forms = forms

        if search_term:
            filtered_forms = [
                form for form in filtered_forms
                if (search_term.lower() in form.get('form_name', '').lower() or
                    search_term.lower() in form.get('form_id', '').lower() or
                    search_term.lower() in form.get('description', '').lower())
            ]

        if country_filter != "All":
            filtered_forms = [form for form in filtered_forms if form['country'] == country_filter]

        if processing_status_filter != "All":
            filtered_forms = [form for form in filtered_forms if form.get('processing_status') == processing_status_filter]

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f"### ���� Forms/Pages ({len(filtered_forms)} found)")

        for form in filtered_forms:
            clean_form_name = clean_html_text(form['form_name'])
            clean_form_id = clean_html_text(form['form_id'])
            clean_country = clean_html_text(form['country'])
            with st.expander(f"📋 {clean_form_name} ({clean_form_id}) - {clean_country} (Status: {form.get('processing_status', 'N/A')})"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Country:** {clean_country}")
                    st.write(f"**Visa Category:** {clean_html_text(form['visa_category'])}")
                    st.write(f"**Form ID:** {clean_form_id}")
                    st.write(f"**Authority:** {clean_html_text(form.get('governing_authority', 'N/A'))}")
                    st.write(f"**Created:** {form['created_at']}")

                with col2:
                    review_status = (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review')
                    st.write(f"**Review Status:** {review_status}")

                    if form.get('validation_warnings'):
                        st.write(f"**Warnings:** {len(form['validation_warnings'])}")

                    source_url = form.get('official_source_url', '')
                    st.write(f"**Source:** {source_url}")
                    st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                    document_info_from_db = db.get_document_by_form_id(form['id'])
                    if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                        st.write(f"**Cloudinary Original URL:** [Link]({document_info_from_db['cloudinary_url']})")
                    else:
                        st.write(f"**Cloudinary Original URL:** N/A")

                st.write(f"**Description:** {clean_html_text(form.get('description', 'No description'))}")

                if form.get('validation_warnings'):
                    st.write("**⚠️ Validation Warnings:**")
                    for warning in form['validation_warnings']:
                        st.write(f"• {warning}")

                with st.expander("View Raw Structured Data (Full AI Output)"):
                    st.json(form.get('structured_data', {}))
    else:
        st.info("No documents/pages in database. Use the Document Discovery page to find and process documents/pages.")

def cloudinary_browser_page(db):
    st.markdown("""
    <style>
    .cloudinary-header {
        background: linear-gradient(45deg, #d299c2 0%, #fef9d7 100%);
        padding: 2rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .cloud-document {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        box-shadow: 0 3px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #d299c2;
    }
    </style>

    <div class="cloudinary-header">
        <h1>☁️ Cloudinary Document Browser</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0;">
            Browse documents stored on Cloudinary, organized by country and visa type
        </p>
    </div>
    """, unsafe_allow_html=True)

    all_forms = db.get_forms()

    cloudinary_docs = []
    for form in all_forms:
        document_info = db.get_document_by_form_id(form['id'])
        if document_info and document_info.get('cloudinary_url'):
            cloudinary_docs.append({
                "form_id": form['id'],
                "country": form['country'],
                "visa_category": form['visa_category'],
                "form_name": form['form_name'],
                "cloudinary_url": document_info['cloudinary_url'],
                "file_format": document_info['file_format'],
                "filename": document_info['filename']
            })

    if not cloudinary_docs:
        st.info("No documents with Cloudinary URLs found in the database. Please process some documents first.")
        return

    st.info(f"Displaying {len(cloudinary_docs)} documents found on Cloudinary.")

    grouped_docs = {}
    for doc in cloudinary_docs:
        country = doc['country'] if doc['country'] else "Unknown Country"
        visa_category = doc['visa_category'] if doc['visa_category'] else "Unknown Visa Type"

        if country not in grouped_docs:
            grouped_docs[country] = {}
        if visa_category not in grouped_docs[country]:
            grouped_docs[country][visa_category] = []
        grouped_docs[country][visa_category].append(doc)

    for country, visa_categories in sorted(grouped_docs.items()):
        with st.expander(f"🌍 {country} ({sum(len(v) for v in visa_categories.values())} documents)"):
            for visa_category, docs in sorted(visa_categories.items()):
                st.markdown(f"""
                <div style="background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 15px; border-radius: 10px; margin: 10px 0;
                           text-align: center; font-weight: bold; font-size: 1.1rem;">
                    🛂 {visa_category} ({len(docs)} documents)
                </div>
                """, unsafe_allow_html=True)

                for doc in docs:
                    clean_doc_form_name = clean_html_text(doc['form_name'])
                    clean_doc_form_id = clean_html_text(doc['form_id'])

                    st.markdown(f"""
                    <div style="background: white; padding: 15px; border-radius: 8px; margin: 8px 0;
                               box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-left: 4px solid #667eea;">
                        <h4 style="margin: 0 0 10px 0; color: #333;">📄 {clean_doc_form_name}</h4>
                        <p style="margin: 5px 0; color: #666;"><strong>Form ID:</strong> {clean_doc_form_id}</p>
                        <p style="margin: 5px 0; color: #666;"><strong>File:</strong> {doc['filename']} ({doc['file_format']})</p>
                        <a href="{doc['cloudinary_url']}" target="_blank"
                           style="display: inline-block; background: #667eea; color: white;
                                  padding: 8px 16px; border-radius: 5px; text-decoration: none;
                                  margin-top: 10px;">
                            ☁️ View on Cloudinary
                        </a>
                    </div>
                    """, unsafe_allow_html=True)

def database_health_check_page(database_url: str):
    st.markdown("""
    <style>
    .health-header {
        background: linear-gradient(45deg, #fa709a 0%, #fee140 100%);
        padding: 2rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .health-info {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #2196f3;
    }
    .troubleshooting {
        background: #fff3e0;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 4px solid #ff9800;
    }
    </style>

    <div class="health-header">
        <h1>🩺 Database Health Check</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0;">
            Verify database schema and column integrity
        </p>
    </div>

    <div class="health-info">
        <p style="margin: 0;"><strong>Info:</strong> This page checks if the required columns exist in your 'forms' and 'documents' tables.</p>
    </div>
    """, unsafe_allow_html=True)

    if not database_url:
        st.error("Database URL is not configured in `config.py` or Streamlit secrets.")
        return

    required_forms_columns = ["downloaded_file_path", "document_format", "processing_status"]
    required_documents_columns = ["cloudinary_url"]
    required_export_logs_columns = ["cloudinary_url"]

    missing_forms_columns = []
    missing_documents_columns = []
    missing_export_logs_columns = []

    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        st.success("Successfully connected to the database!")

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'forms'
            AND table_schema = 'public';
        """)
        existing_forms_columns = [row[0] for row in cursor.fetchall()]
        st.subheader("Existing Columns in 'forms' table:")
        st.write(existing_forms_columns)
        for col in required_forms_columns:
            if col not in existing_forms_columns:
                missing_forms_columns.append(col)

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'documents'
            AND table_schema = 'public';
        """)
        existing_documents_columns = [row[0] for row in cursor.fetchall()]
        st.subheader("Existing Columns in 'documents' table:")
        st.write(existing_documents_columns)
        for col in required_documents_columns:
            if col not in existing_documents_columns:
                missing_documents_columns.append(col)

        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'export_logs'
            AND table_schema = 'public';
        """)
        existing_export_logs_columns = [row[0] for row in cursor.fetchall()]
        st.subheader("Existing Columns in 'export_logs' table:")
        st.write(existing_export_logs_columns)
        for col in required_export_logs_columns:
            if col not in existing_export_logs_columns:
                missing_export_logs_columns.append(col)

        all_missing = False
        if missing_forms_columns:
            st.error(f"❌ Missing columns in 'forms' table: {', '.join(missing_forms_columns)}")
            all_missing = True
        if missing_documents_columns:
            st.error(f"❌ Missing columns in 'documents' table: {', '.join(missing_documents_columns)}")
            all_missing = True
        if missing_export_logs_columns:
            st.error(f"❌ Missing columns in 'export_logs' table: {', '.join(missing_export_logs_columns)}")
            all_missing = True

        if not all_missing:
            st.success("✅ All required columns are present in the 'forms', 'documents', and 'export_logs' tables!")
            st.write("You should now be able to process and save documents correctly, including Cloudinary uploads.")
        else:
            st.warning("Please ensure you have dropped the old tables in your NeonDB console and re-run `python setup_neondb.py` to synchronize the schema.")
            st.markdown("---")
            st.subheader("Troubleshooting Steps:")
            st.markdown("1. **Go to your NeonDB project dashboard and open the SQL Editor.**")
            st.markdown("2. **Execute the following SQL commands to drop existing tables:**")
            st.code("""
DROP TABLE IF EXISTS export_logs CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS sources CASCADE;
DROP TABLE IF EXISTS forms CASCADE;
            """)
            st.markdown("3. **Refresh your NeonDB console's 'Tables' view and visually confirm these tables are gone.**")
            st.markdown("4. **In your local terminal, re-run the setup script:**")
            st.code("python setup_neondb.py")
            st.markdown("5. **Restart your Streamlit app completely (Ctrl+C then `streamlit run app.py`).**")
            st.markdown("6. **Come back to this 'Database Health Check' page to verify the columns are now present.**")

        cursor.close()
        conn.close()

    except Exception as e:
        st.error(f"Failed to connect to database or check schema: {e}")
        st.warning("Please check your `database_url` in `.streamlit/secrets.toml` and ensure your NeonDB project is active.")


if __name__ == "__main__":
      main()
