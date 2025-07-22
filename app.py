import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import traceback
import psycopg2
from urllib.parse import urlparse
import mimetypes
import time

# Import our services
from config import config
from database import DatabaseManager
from discovery_service import DocumentDiscoveryService
from document_processor import DocumentProcessor
from ai_service import AIExtractionService
from export_service import ExportService

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
    
    st.title("🌍 Immigration Document Intelligence System")
    st.markdown("**Automated discovery, processing, and validation of official immigration documents and information**")
    
    if st.button("Clear all caches"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.warning("⚠️ **Important:** Documents are now stored **locally** in the `downloads` directory. For cloud deployments, this directory might be ephemeral. **All downloaded and generated documents are also uploaded to Cloudinary for persistent storage.**")
    
    db, discovery, processor, ai_service, export_service = init_services()
    
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page:",
        ["🔍 Document Discovery", "📄 Document Viewer", "✅ Validation Panel", "📊 Export Panel", "🗄️ Database Viewer", "☁️ Cloudinary Document Browser", "🩺 Database Health Check"]
    )
    
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
    st.header("🔍 Document Discovery")
    st.markdown("Discover official immigration documents and relevant informational pages from government sources.")
    
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

    st.subheader("Processing Options")
    col1, col2 = st.columns(2)

    with col1:
        max_docs = st.slider("Maximum documents/pages to process:", 1, 25, 5)
        auto_process = st.checkbox("Auto-process after discovery", value=True)

    with col2:
        save_to_db = st.checkbox("Save to database", value=True)
        validate_with_ai = st.checkbox("AI extraction & validation", value=True)

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
            # Get all visa types for the selected country (or a general list)
            # For simplicity, we'll use a predefined list of common visa types for batch processing
            common_visa_types = ["Work Visa", "Student Visa", "Tourist Visa", "Family Visa", "Permanent Residence", "Citizenship", "Business Visa"]
            
            all_discovered_docs = []
            for vt in common_visa_types:
                st.subheader(f"Discovering for {batch_country} - {vt}...")
                discovered_docs_for_type = discovery.discover_documents(batch_country, vt)
                all_discovered_docs.extend(discovered_docs_for_type)
                st.info(f"Found {len(discovered_docs_for_type)} documents for {batch_country} - {vt}.")
                time.sleep(1) # Small delay between queries

            if all_discovered_docs:
                st.success(f"Total {len(all_discovered_docs)} unique documents/pages discovered for {batch_country}.")
                st.subheader(f"Initiating processing for all discovered documents in {batch_country}...")
                # The process_documents_improved function already handles duplicates and AI processing
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
        
        # Initialize form_data_to_save with default values, which will be updated by AI
        form_data_to_save = {
            "country": country, # Default from user input, will be overridden by AI
            "visa_category": visa_type, # Default from user input, will be overridden by AI
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
            "processing_status": "failed", # Default to failed, update on success
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
            else: # If AI validation is skipped
                form_data_to_save["validation_warnings"].append("AI processing skipped by user")
                form_data_to_save["processing_status"] = "downloaded_only"
                form_data_to_save["structured_data"] = {
                    "extracted_text_length": len(extracted_text),
                    "file_info": file_info,
                    "full_markdown_summary": f"Document text extracted (AI processing skipped):\n\n\`\`\`\n{extracted_text[:1000]}...\n\`\`\`"
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
                with st.expander(f"📋 {form.get('form_name', 'Unknown Form/Page')} (ID: {form.get('form_id', 'N/A')})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Country:** {form.get('country', 'N/A')}")
                        st.write(f"**Visa Category:** {form.get('visa_category', 'N/A')}")
                        st.write(f"**Authority:** {form.get('governing_authority', 'N/A')}")
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
                with st.expander(f"❌ {failed['doc']['title'][:80]}..."):
                    st.error(f"**Error:** {failed['error']}")
                    st.write(f"**Failed at step:** {failed['step']}")
                    st.write(f"**URL:** {failed['doc']['url']}")

        if skipped_duplicates:
            st.subheader("⏩ Skipped Duplicate Documents/Pages")
            for skipped in skipped_duplicates:
                with st.expander(f"⏩ {skipped['title'][:80]}..."):
                    st.info(f"**URL:** {skipped['url']}")
                    st.info("This document/page was skipped because its URL already exists in the database.")


def document_viewer_page(db, processor, ai_service):
    st.header("📄 Document Viewer")
    st.markdown("View detailed information and extracted data for processed documents and informational pages.")
    
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents/pages in database")
        
        form_options = [f"{form['country']} - {form['form_name']} ({form['form_id']})" for form in forms]
        selected_idx = st.selectbox("Select document/page to view:", range(len(form_options)), format_func=lambda x: form_options[x])
        
        if selected_idx is not None:
            selected_form = forms[selected_idx]
            document_info_from_db = db.get_document_by_form_id(selected_form['id'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Form/Page Information")
                st.write(f"**Country:** {selected_form['country']}")
                st.write(f"**Visa Category:** {selected_form['visa_category']}")
                st.write(f"**Form Name:** {selected_form['form_name']}")
                st.write(f"**Form ID:** {selected_form['form_id']}")
                st.write(f"**Authority:** {selected_form.get('governing_authority', 'N/A')}")
            
            with col2:
                st.subheader("Processing Details")
                structured_data_full = selected_form.get('structured_data', {})
                st.write(f"**Processing Status:** {selected_form.get('processing_status', 'N/A')}")
                st.write(f"**Downloaded Path (Local):** {selected_form.get('downloaded_file_path', 'N/A')}")
                if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                    st.write(f"**Cloudinary URL:** [Link]({document_info_from_db['cloudinary_url']})")
                else:
                    st.write(f"**Cloudinary URL:** N/A")
                st.write(f"**Processing Time:** {structured_data_full.get('processing_time', 'N/A')}")
                st.write(f"**Fees:** {structured_data_full.get('fees', 'N/A')}")
                st.write(f"**Submission Method:** {structured_data_full.get('submission_method', 'N/A')}")
                st.write(f"**Last Updated:** {selected_form['created_at']}")
            
            with st.expander("Debug: Raw Database Data for Selected Document"):
                st.write("**Selected Form Data:**")
                st.json(selected_form)
                st.write("**Associated Document Data (from documents table):**")
                st.json(document_info_from_db)
                if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                    st.markdown(f"**Direct Cloudinary URL (copy and paste into browser):** `{document_info_from_db['cloudinary_url']}`")
                    st.markdown("If this URL doesn't work in your browser, the issue is with Cloudinary access/permissions, not the app.")
                else:
                    st.info("No Cloudinary URL found in database for this document.")
            st.subheader("Description")
            st.write(selected_form.get('description', 'No description available'))
            
            if structured_data_full.get('supporting_documents'):
                st.subheader("Supporting Documents")
                for doc in structured_data_full['supporting_documents']:
                    st.write(f"• {doc}")
            
            if selected_form.get('validation_warnings'):
                st.subheader("⚠️ Validation Warnings")
                for warning in selected_form['validation_warnings']:
                    st.warning(warning)

            full_markdown = structured_data_full.get('full_markdown_summary')
            if full_markdown:
                st.subheader("Comprehensive Document/Page Summary (Markdown)")
                st.markdown(full_markdown)
            else:
                st.info("No comprehensive Markdown summary available for this document/page.")
            
            st.subheader("Download Options")
            downloaded_file_path = selected_form.get('downloaded_file_path')
            
            col_dl1, col_dl2 = st.columns(2)

            if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                original_filename = document_info_from_db.get('filename', 'original_document')
                original_file_format = document_info_from_db.get('file_format', 'UNKNOWN').lower()
                with col_dl1:
                    st.markdown(f"**Download Original ({original_file_format.upper()}) from Cloud:**")
                    st.markdown(f"[Click to Download]({document_info_from_db['cloudinary_url']})")
            elif downloaded_file_path and Path(downloaded_file_path).exists():
                original_filename = Path(downloaded_file_path).name
                original_file_format = selected_form.get('document_format', 'UNKNOWN').lower()
                
                original_file_content = processor.get_file_content_bytes_from_path(downloaded_file_path)
                if original_file_content:
                    with col_dl1:
                        st.download_button(
                            label=f"Download Original ({original_file_format.upper()}) (Local)",
                            data=original_file_content,
                            file_name=original_filename,
                            mime=mimetypes.guess_type(original_filename)[0] or "application/octet-stream",
                            key=f"download_original_{selected_form['id']}"
                        )
                else:
                    with col_dl1:
                        st.warning("Original file content not available from local path.")
            else:
                st.info("Original document/page file not found locally or on Cloudinary.")
            
            if full_markdown:
                markdown_bytes = full_markdown.encode('utf-8')
                with col_dl2:
                    st.download_button(
                        label="Download Markdown Summary (.md)",
                        data=markdown_bytes,
                        file_name=f"{Path(selected_form.get('form_name', 'summary')).stem}_summary.md",
                        mime="text/markdown",
                        key=f"download_markdown_summary_{selected_form['id']}"
                    )
            else:
                with col_dl2:
                    st.warning("No Markdown summary to download.")
            
            with st.expander("View Raw Structured Data (Full AI Output)"):
                st.json(structured_data_full)
    else:
        st.info("No documents/pages found. Use the Document Discovery page to find and process documents/pages first.")

def validation_panel_page(db, processor, ai_service):
    st.header("✅ Validation & Lawyer Review Panel")
    st.markdown("Review and validate extracted data, and manage lawyer approvals for documents and informational pages.")
    
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents/pages for review")
        
        review_filter = st.selectbox(
            "Filter by review status:",
            ["All", "Pending Review", "Approved", "Approved with Comments", "Needs Revision", "Downloaded Only", "Partial AI Failure", "AI Extraction Failed", "Low Text Content"]
        )
        
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
                with st.expander(f"📋 {form['form_name']} - {form['country']} (Status: {form.get('processing_status', 'N/A')})"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Form ID:** {form['form_id']}")
                        st.write(f"**Description:** {form.get('description', 'N/A')}")
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
    st.header("📊 Export Panel")
    st.markdown("Export processed documents and extracted data in various formats.")
    
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents/pages available for export")
        
        st.subheader("Export Options")
        
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
                    "Country": form['country'],
                    "Form Name": form['form_name'],
                    "Form ID": form['form_id'],
                    "Review Status": (form.get('lawyer_review') or {}).get('approval_status', 'Pending'),
                    "Processing Status": form.get('processing_status', 'N/A'),
                    "Last Updated": form['created_at']
                })
            
            df = pd.DataFrame(preview_data)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No documents/pages available for export.")

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
    st.header("🗄️ Database Viewer")
    st.markdown("Browse and search all processed documents and informational pages in the database.")
    
    forms = db.get_forms()
    
    if forms:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Forms/Pages", len(forms))
        
        with col2:
            countries_in_db = set(form['country'] for form in forms)
            st.metric("Countries", len(countries_in_db))
        
        with col3:
            approved_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status') == 'Approved'
            ])
            st.metric("Approved Forms/Pages", approved_forms)
        
        with col4:
            pending_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
            ])
            st.metric("Pending Review", pending_forms)
        
        st.subheader("Search & Filter")
        
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
        
        st.subheader(f"Forms/Pages ({len(filtered_forms)} found)")
        
        for form in filtered_forms:
            with st.expander(f"📋 {form['form_name']} ({form['form_id']}) - {form['country']} (Status: {form.get('processing_status', 'N/A')})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Country:** {form['country']}")
                    st.write(f"**Visa Category:** {form['visa_category']}")
                    st.write(f"**Form ID:** {form['form_id']}")
                    st.write(f"**Authority:** {form.get('governing_authority', 'N/A')}")
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

                st.write(f"**Description:** {form.get('description', 'No description')}")
                
                if form.get('validation_warnings'):
                    st.write("**⚠️ Validation Warnings:**")
                    for warning in form['validation_warnings']:
                        st.write(f"• {warning}")
                
                with st.expander("View Raw Structured Data (Full AI Output)"):
                    st.json(form.get('structured_data', {}))
    else:
        st.info("No documents/pages in database. Use the Document Discovery page to find and process documents/pages.")

def cloudinary_browser_page(db):
    st.header("☁️ Cloudinary Document Browser")
    st.markdown("Browse documents stored on Cloudinary, organized by country and visa type.")

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
                with st.expander(f"🛂 {visa_category} ({len(docs)} documents)"):
                    for doc in docs:
                        st.markdown(f"**📄 {doc['form_name']}** (ID: {doc['form_id']})")
                        st.write(f"File: {doc['filename']} ({doc['file_format']})")
                        st.markdown(f"[View on Cloudinary]({doc['cloudinary_url']})")
                        st.markdown("---")

def database_health_check_page(database_url: str):
    st.header("🩺 Database Health Check")
    st.info("This page checks if the required columns exist in your 'forms' and 'documents' tables.")

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
