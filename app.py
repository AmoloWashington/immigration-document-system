import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import traceback
import psycopg2
from urllib.parse import urlparse
import mimetypes

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
    processor = DocumentProcessor(config.DOWNLOADS_DIR) 
    # Pass db to discovery service
    discovery = DocumentDiscoveryService(config.TAVILY_API_KEY, processor, db) 
    ai_service = AIExtractionService(config.OPENAI_API_KEY, config.OPENROUTER_API_KEY, config.GEMINI_API_KEY)
    # Pass db to export service
    export_service = ExportService(config.OUTPUTS_DIR, db) 
    
    return db, discovery, processor, ai_service, export_service

def main():
    st.set_page_config(
        page_title="Immigration Document Intelligence System",
        page_icon="📋",
        layout="wide"
    )
    
    st.title("🌍 Immigration Document Intelligence System")
    st.markdown("**Automated discovery, processing, and validation of official immigration documents and information**") # Updated title
    
    if st.button("Clear all caches"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    st.warning("⚠️ **Important:** Documents are now stored **locally** in the `downloads` directory. This means files will persist as long as the application's local storage is maintained. For cloud deployments, this directory might be ephemeral.")
    
    db, discovery, processor, ai_service, export_service = init_services()
    
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page:",
        ["🔍 Document Discovery", "📄 Document Viewer", "✅ Validation Panel", "📊 Export Panel", "🗄️ Database Viewer", "🩺 Database Health Check"]
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
    elif page == "🩺 Database Health Check":
        database_health_check_page(config.DATABASE_URL)

def discovery_page(discovery, processor, ai_service, db):
    st.header("🔍 Document Discovery")
    st.markdown("Discover official immigration documents and relevant informational pages from government sources.") # Updated description
    
    col1, col2 = st.columns(2)
    
    with col1:
        country = st.selectbox(
            "Select Country:",
            ["USA", "Canada", "UK", "Australia", "Germany", "France", "Other"]
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
        max_docs = st.slider("Maximum documents/pages to process:", 1, 20, 5) # Increased max to 20
        auto_process = st.checkbox("Auto-process after discovery", value=True)
    
    with col2:
        save_to_db = st.checkbox("Save to database", value=True)
        validate_with_ai = st.checkbox("AI extraction & validation", value=True) # Renamed for clarity

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
                st.info(f"⏩ Skipping duplicate: '{doc['title'][:50]}...' (already in database with ID: {existing_form['id']})")
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
            status_text.text(f"Step 1/4: Downloading document/page to local storage...")
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
            
            if not extracted_text or len(extracted_text.strip()) < 50: # Lowered threshold for AI processing
                st.warning(f"Low text content ({len(extracted_text.strip())} chars) for '{doc['title'][:50]}...'. Attempting AI processing anyway for summary.")
                form_data_to_save["processing_status"] = "low_text_content" # New status
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
                    
                    # --- IMPORTANT FIX: Prioritize AI-extracted country/visa_category ---
                    form_data_to_save['country'] = ai_extracted_data.get('country', country)
                    form_data_to_save['visa_category'] = ai_extracted_data.get('visa_category', visa_type)
                    # --- END IMPORTANT FIX ---

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
                    
                    # --- NEW: Insert into documents table ---
                    db.insert_document(form_id, file_info)
                    # --- END NEW ---

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
    st.markdown("View detailed information and extracted data for processed documents and informational pages.") # Updated description
    
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents/pages in database")
        
        form_options = [f"{form['country']} - {form['form_name']} ({form['form_id']})" for form in forms]
        selected_idx = st.selectbox("Select document/page to view:", range(len(form_options)), format_func=lambda x: form_options[x])
        
        if selected_idx is not None:
            selected_form = forms[selected_idx]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Form/Page Information") # Updated title
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
                st.write(f"**Processing Time:** {structured_data_full.get('processing_time', 'N/A')}")
                st.write(f"**Fees:** {structured_data_full.get('fees', 'N/A')}")
                st.write(f"**Submission Method:** {structured_data_full.get('submission_method', 'N/A')}")
                st.write(f"**Last Updated:** {selected_form['created_at']}")
            
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
                st.subheader("Comprehensive Document/Page Summary (Markdown)") # Updated title
                st.markdown(full_markdown)
            else:
                st.info("No comprehensive Markdown summary available for this document/page.") # Updated message
            
            st.subheader("Download Options")
            downloaded_file_path = selected_form.get('downloaded_file_path')
            
            col_dl1, col_dl2 = st.columns(2)

            if downloaded_file_path and Path(downloaded_file_path).exists():
                original_filename = Path(downloaded_file_path).name
                original_file_format = selected_form.get('document_format', 'UNKNOWN').lower()
                
                original_file_content = processor.get_file_content_bytes_from_path(downloaded_file_path)
                if original_file_content:
                    with col_dl1:
                        st.download_button(
                            label=f"Download Original ({original_file_format.upper()})",
                            data=original_file_content,
                            file_name=original_filename,
                            mime=mimetypes.guess_type(original_filename)[0] or "application/octet-stream",
                            key=f"download_original_{selected_form['id']}"
                        )
                else:
                    with col_dl1:
                        st.warning("Original file content not available from local path.")
            else:
                st.info("Original document/page file not found locally. It might have been deleted or not saved.") # Updated message
            
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
        st.info("No documents/pages found. Use the Document Discovery page to find and process documents/pages first.") # Updated message

def validation_panel_page(db, processor, ai_service):
    st.header("✅ Validation & Lawyer Review Panel")
    st.markdown("Review and validate extracted data, and manage lawyer approvals for documents and informational pages.") # Updated description
    
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents/pages for review") # Updated message
        
        review_filter = st.selectbox(
            "Filter by review status:",
            ["All", "Pending Review", "Approved", "Approved with Comments", "Needs Revision", "Downloaded Only", "Partial AI Failure", "AI Extraction Failed", "Low Text Content"] # Added "Low Text Content"
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
            elif review_filter == "Low Text Content": # New filter
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
                                if st.form_submit_button("✨ Re-run AI Extraction & Validation"): # Updated button text
                                    if not form.get('downloaded_file_path') or not Path(form['downloaded_file_path']).exists():
                                        st.error("Cannot re-run AI: Document/page file not found locally.") # Updated message
                                    else:
                                        with st.spinner("Re-running AI processing and validation..."):
                                            try:
                                                extracted_text = processor.extract_text(form['downloaded_file_path'])
                                                
                                                if not extracted_text or len(extracted_text.strip()) < 50: # Lowered threshold
                                                    st.warning("Low text content for AI re-validation. AI summary might be limited.")
                                                    # Do NOT return here, proceed with AI processing
                                                
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
                                                        new_processing_status = "low_text_content" # Re-apply if still low text
                                                    
                                                    update_success = db.update_form_fields(
                                                        form['id'],
                                                        {
                                                            "structured_data": re_extracted_data,
                                                            "validation_warnings": validation_warnings,
                                                            "processing_status": new_processing_status,
                                                            # --- IMPORTANT FIX: Update country/visa_category from AI ---
                                                            "country": re_extracted_data.get('country', form['country']),
                                                            "visa_category": re_extracted_data.get('visa_category', form['visa_category']),
                                                            # --- END IMPORTANT FIX ---
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
            elif status_filter == "Low Text Content": # New filter
                filtered_forms = [
                    form for form in filtered_forms
                    if form.get('processing_status') == 'low_text_content'
                ]
            else:
                filtered_forms = [
                    form for form in filtered_forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == status_filter
                ]
        
        st.write(f"**Forms/Pages to export:** {len(filtered_forms)}") # Updated message
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Export as JSON"):
                if len(filtered_forms) == 1:
                    form_data = filtered_forms[0].get('structured_data', {})
                    # Pass the original form object to export_json to get its ID
                    file_path, file_content = export_service.export_json(filtered_forms[0]) 
                    if file_content:
                        st.download_button(
                            label="Download JSON",
                            data=file_content,
                            file_name=Path(file_path).name,
                            mime="application/json",
                            key="download_json_single"
                        )
                elif len(filtered_forms) > 1:
                    st.info("Exporting multiple JSON files to the server. Individual download buttons are not provided for batch exports.")
                    exported_files_count = 0
                    for form in filtered_forms:
                        file_path, _ = export_service.export_json(form) # Pass the original form object
                        if file_path:
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} JSON files to server.")
                else:
                    st.warning("No forms/pages selected for JSON export.") # Updated message
    
        with col2:
            if st.button("📊 Export as Excel"):
                if filtered_forms:
                    forms_data_for_excel = []
                    for form in filtered_forms:
                        flat_form = {**form}
                        if 'structured_data' in form and form['structured_data'] is not None:
                            flat_form.update(form['structured_data'])
                        forms_data_for_excel.append(flat_form)

                    file_path, file_content = export_service.export_excel(forms_data_for_excel)
                    if file_content:
                        st.download_button(
                            label="Download Excel",
                            data=file_content,
                            file_name=Path(file_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_excel"
                        )
                else:
                    st.warning("No forms/pages selected for Excel export.") # Updated message
    
        with col3:
            if st.button("📋 Export Summaries"):
                if filtered_forms:
                    exported_files_count = 0
                    for form in filtered_forms:
                        summary_data_to_export = form.get('structured_data', {})
                        # Pass the original form object to export_summary_pdf to get its ID
                        file_path, file_content = export_service.export_summary_pdf(form) 
                        if file_content:
                            st.download_button(
                                label=f"Download {Path(file_path).name}",
                                data=file_content,
                                file_name=Path(file_path).name,
                                mime="text/plain",
                                key=f"download_summary_{form['id']}"
                            )
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} summary files.")
                else:
                    st.warning("No forms/pages selected for summary export.") # Updated message
    
        if filtered_forms:
            st.subheader("Preview of Forms/Pages to Export") # Updated message
            
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
        st.info("No documents/pages available for export.") # Updated message

def database_viewer_page(db):
    st.header("🗄️ Database Viewer")
    st.markdown("Browse and search all processed documents and informational pages in the database.") # Updated description
    
    forms = db.get_forms()
    
    if forms:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Forms/Pages", len(forms)) # Updated message
        
        with col2:
            # Dynamically get countries from forms data
            countries_in_db = set(form['country'] for form in forms)
            st.metric("Countries", len(countries_in_db)) # This will now reflect all countries
        
        with col3:
            approved_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status') == 'Approved'
            ])
            st.metric("Approved Forms/Pages", approved_forms) # Updated message
        
        with col4:
            pending_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
            ])
            st.metric("Pending Review", pending_forms)
        
        st.subheader("Search & Filter")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("Search forms/pages (name, ID, description):") # Updated message
        
        with col2:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + sorted(list(set(form['country'] for form in forms))) # Dynamically populate filter
            )
        with col3:
            processing_status_filter = st.selectbox(
                "Filter by Processing Status:",
                ["All", "validated", "validated_with_warnings", "downloaded_only", "ai_extraction_failed", "failed", "low_text_content"] # Added "low_text_content"
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
        
        st.subheader(f"Forms/Pages ({len(filtered_forms)} found)") # Updated message
        
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
                
                st.write(f"**Description:** {form.get('description', 'No description')}")
                
                if form.get('validation_warnings'):
                    st.write("**⚠️ Validation Warnings:**")
                    for warning in form['validation_warnings']:
                        st.write(f"• {warning}")
                
                with st.expander("View Raw Structured Data (Full AI Output)"):
                    st.json(form.get('structured_data', {}))
    else:
        st.info("No documents/pages in database. Use the Document Discovery page to find and process documents/pages.") # Updated message

def database_health_check_page(database_url: str):
    st.header("🩺 Database Health Check")
    st.info("This page checks if the required columns exist in your 'forms' table.")

    if not database_url:
        st.error("Database URL is not configured in `config.py` or Streamlit secrets.")
        return

    required_columns = ["downloaded_file_path", "document_format", "processing_status"]
    missing_columns = []
    
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
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        st.subheader("Existing Columns in 'forms' table:")
        st.write(existing_columns)

        for col in required_columns:
            if col not in existing_columns:
                missing_columns.append(col)
        
        if not missing_columns:
            st.success("✅ All required columns are present in the 'forms' table!")
            st.write("You should now be able to process and save documents correctly.")
        else:
            st.error(f"❌ Missing columns in 'forms' table: {', '.join(missing_columns)}")
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
