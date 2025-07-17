import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
import traceback
import psycopg2 
import mimetypes

from config import config
from database import DatabaseManager
from discovery_service import DocumentDiscoveryService
from document_processor import DocumentProcessor
from ai_service import AIExtractionService
from export_service import ExportService


def init_services():
    db = DatabaseManager(config.DATABASE_URL)
    discovery = DocumentDiscoveryService(config.TAVILY_API_KEY)
    processor = DocumentProcessor(config.DOWNLOADS_DIR)
   
    ai_service = AIExtractionService(config.OPENAI_API_KEY, config.OPENROUTER_API_KEY)
    export_service = ExportService(config.OUTPUTS_DIR)
    
    return db, discovery, processor, ai_service, export_service

def main():
    st.set_page_config(
        page_title="Immigration Document Intelligence System",
        page_icon="📋",
        layout="wide"
    )
    
    st.title("🌍 Immigration Document Intelligence System")
    st.markdown("**Automated discovery, processing, and validation of official immigration documents**")
    
    if st.button("Clear all caches"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    
  
    db, discovery, processor, ai_service, export_service = init_services()
    
    
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page:",
        ["🔍 Document Discovery", "📄 Document Viewer", "✅ Validation Panel", "📊 Export Panel", "🗄️ Database Viewer", "🩺 Database Health Check"] # Added new page
    )
    
    if page == "🔍 Document Discovery":
        discovery_page(discovery, processor, ai_service, db)
    elif page == "📄 Document Viewer":
        document_viewer_page(db, processor, ai_service)
    elif page == "✅ Validation Panel":
        # Pass processor and ai_service to validation_panel_page
        validation_panel_page(db, processor, ai_service)
    elif page == "📊 Export Panel":
        export_panel_page(db, export_service)
    elif page == "🗄️ Database Viewer":
        database_viewer_page(db)
    elif page == "🩺 Database Health Check": 
        database_health_check_page(config.DATABASE_URL)

def discovery_page(discovery, processor, ai_service, db):
    st.header("🔍 Document Discovery")
    
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
    
    # Add processing options
    st.subheader("Processing Options")
    col1, col2 = st.columns(2)
    
    with col1:
        max_docs = st.slider("Maximum documents to process:", 1, 10, 3)
        auto_process = st.checkbox("Auto-process after discovery", value=True)
    
    with col2:
        save_to_db = st.checkbox("Save to database", value=True)
        validate_with_ai = st.checkbox("AI validation", value=True)
    
    if st.button("🚀 Start Discovery", type="primary"):
        if country and visa_type:
            with st.spinner("Discovering documents..."):
                # Step 1: Discover documents
                st.subheader("Step 1: Document Discovery")
                discovered_docs = discovery.discover_documents(country, visa_type)
                
                if discovered_docs:
                    st.success(f"Found {len(discovered_docs)} potential documents")
                    
                    # Limit documents to process
                    docs_to_process = discovered_docs[:max_docs]
                    st.info(f"Attempting to process first {len(docs_to_process)} documents...")
                    
                    # Display discovered documents
                    for i, doc in enumerate(docs_to_process):
                        with st.expander(f"📄 {doc['title'][:100]}..."):
                            st.write(f"**URL:** {doc['url']}")
                            st.write(f"**Source:** {doc['source_domain']}")
                            st.write(f"**Type:** {doc['file_type']}")
                            st.write(f"**Description:** {doc['description'][:200]}...")
                    
                    # Auto-process if enabled
                    if auto_process:
                        st.subheader("Step 2: Processing Documents")
                        process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai)
                    else:
                        # Manual processing button
                        if st.button("📥 Download and Process Selected Documents"):
                            process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai)
                else:
                    st.warning("No documents found. Try different search terms.")
        else:
            st.error("Please select both country and visa type.")

def process_documents_improved(discovered_docs, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai):
    """Improved document processing with better error handling and progress tracking"""
    
    st.subheader("📥 Document Processing Pipeline")
    
    # Create progress tracking
    progress_container = st.container()
    status_container = st.container()
    results_container = st.container()
    
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    processed_forms = []
    failed_docs = []
    
    total_docs = len(discovered_docs)
    
    for i, doc in enumerate(discovered_docs):
        current_progress = (i + 1) / total_docs
        
        with status_container:
            st.write(f"**Processing {i+1}/{total_docs}:** {doc['title'][:80]}...")
        
        form_data_to_save = {
            "country": country,
            "visa_category": visa_type,
            "form_name": doc.get('title', 'Unknown Form'),
            "form_id": "N/A", 
            "description": doc.get('description', ''),
            "official_source_url": doc.get('url', ''),
            "discovered_by_query": doc.get('discovered_by_query', ''),
            "validation_warnings": [],
            "structured_data": {}, 
            "downloaded_file_path": None,
            "document_format": doc.get('file_type', 'UNKNOWN'),
            "last_fetched": datetime.now().isoformat(),
            "processing_status": "failed" 
        }

        try:
            status_text.text(f"Step 1/4: Downloading document...")
            progress_bar.progress(current_progress * 0.25)
            
            # Step 1: Download document
            file_info = processor.download_document(doc['url'], country, visa_type)
            
            if not file_info:
                failed_docs.append({"doc": doc, "error": "Download failed or file invalid", "step": "download"})
                continue
            
            form_data_to_save["downloaded_file_path"] = file_info['file_path']
            form_data_to_save["document_format"] = file_info['file_format']

            status_text.text(f"Step 2/4: Extracting text...")
            progress_bar.progress(current_progress * 0.5)
            
            # Step 2: Extract text
            extracted_text = processor.extract_text(file_info['file_path'])
            
            if not extracted_text or len(extracted_text.strip()) < 100:
                failed_docs.append({"doc": doc, "error": "Text extraction failed or insufficient content", "step": "extraction"})
                continue
            
            # Combine document info for AI service
            doc_info_for_ai = {**doc, **file_info}
            
            if validate_with_ai:
                status_text.text(f"Step 3/4: AI processing...")
                progress_bar.progress(current_progress * 0.75)
                
                # Step 3: AI extraction
                ai_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)
                
                if not ai_extracted_data:
                    failed_docs.append({"doc": doc, "error": "AI extraction failed", "step": "ai_extraction"})
                    # Still try to save basic info
                    form_data_to_save["validation_warnings"].append("AI extraction failed")
                    form_data_to_save["processing_status"] = "partial_ai_failure"
                else:
                    # Update form_data_to_save with AI results
                    form_data_to_save.update(ai_extracted_data)
                    form_data_to_save["form_id"] = ai_extracted_data.get('form_id', 'N/A')
                    form_data_to_save["structured_data"] = ai_extracted_data # Store full AI output
                    
                    # Step 4: AI validation
                    validation_warnings = ai_service.validate_form_data(form_data_to_save)
                    form_data_to_save['validation_warnings'] = validation_warnings
                    form_data_to_save["processing_status"] = "validated" if not validation_warnings else "validated_with_warnings"
            else:
                # Create basic form data without AI processing
                form_data_to_save["validation_warnings"].append("AI validation skipped")
                form_data_to_save["processing_status"] = "downloaded_only"
                form_data_to_save["structured_data"] = {
                    "extracted_text_length": len(extracted_text),
                    "file_info": file_info
                }
            
            if save_to_db:
                status_text.text(f"Step 4/4: Saving to database...")
                
                # Step 5: Store in database
                form_id = db.insert_form(form_data_to_save)
                if form_id:
                    form_data_to_save['id'] = form_id
                    processed_forms.append(form_data_to_save)
                    st.success(f"✅ Processed and Saved: {doc['title'][:50]}...")
                else:
                    failed_docs.append({"doc": doc, "error": "Database save failed", "step": "database"})
            else:
                processed_forms.append(form_data_to_save)
                st.success(f"✅ Processed (not saved to DB): {doc['title'][:50]}...")
            
        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            st.error(f"❌ Failed: {doc['title'][:50]}... - {error_msg}")
            failed_docs.append({"doc": doc, "error": error_msg, "step": "unknown"})
            
            # Log full error for debugging
            with st.expander(f"Debug Info for {doc['title'][:50]}..."):
                st.code(traceback.format_exc())
        
        progress_bar.progress(current_progress)
    
    # Final results
    with results_container:
        st.subheader("📊 Processing Results")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("✅ Successful", len(processed_forms))
        
        with col2:
            st.metric("❌ Failed", len(failed_docs))
        
        with col3:
            total_attempted = len(processed_forms) + len(failed_docs)
            success_rate = (len(processed_forms) / total_attempted) * 100 if total_attempted > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        # Show successful processing results
        if processed_forms:
            st.subheader("✅ Successfully Processed Documents")
            for form in processed_forms:
                with st.expander(f"📋 {form.get('form_name', 'Unknown Form')} (ID: {form.get('form_id', 'N/A')})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Country:** {form.get('country', 'N/A')}")
                        st.write(f"**Visa Category:** {form.get('visa_category', 'N/A')}")
                        st.write(f"**Authority:** {form.get('governing_authority', 'N/A')}")
                        st.write(f"**Database ID:** {form.get('id', 'Not saved')}")
                    
                    with col2:
                        st.write(f"**Processing Status:** {form.get('processing_status', 'N/A')}")
                        st.write(f"**Downloaded Path:** {form.get('downloaded_file_path', 'N/A')}")
                        st.write(f"**Text Length:** {form.get('structured_data', {}).get('extracted_text_length', 'N/A')} chars")
                        st.write(f"**Fees:** {form.get('structured_data', {}).get('fees', 'N/A')}")
                    
                    if form.get('validation_warnings'):
                        st.warning("⚠️ Validation Warnings:")
                        for warning in form['validation_warnings']:
                            st.write(f"• {warning}")
        
        # Show failed documents
        if failed_docs:
            st.subheader("❌ Failed Documents")
            for failed in failed_docs:
                with st.expander(f"❌ {failed['doc']['title'][:80]}..."):
                    st.error(f"**Error:** {failed['error']}")
                    st.write(f"**Failed at step:** {failed['step']}")
                    st.write(f"**URL:** {failed['doc']['url']}")

def document_viewer_page(db, processor, ai_service):
    st.header("📄 Document Viewer")
    
    # Get all forms
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents in database")
        
        # Select form to view
        form_options = [f"{form['country']} - {form['form_name']} ({form['form_id']})" for form in forms]
        selected_idx = st.selectbox("Select document to view:", range(len(form_options)), format_func=lambda x: form_options[x])
        
        if selected_idx is not None:
            selected_form = forms[selected_idx]
            
            # Display form details
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Form Information")
                st.write(f"**Country:** {selected_form['country']}")
                st.write(f"**Visa Category:** {selected_form['visa_category']}")
                st.write(f"**Form Name:** {selected_form['form_name']}")
                st.write(f"**Form ID:** {selected_form['form_id']}")
                st.write(f"**Authority:** {selected_form.get('governing_authority', 'N/A')}")
            
            with col2:
                st.subheader("Processing Details")
                structured_data = selected_form.get('structured_data', {})
                st.write(f"**Processing Status:** {selected_form.get('processing_status', 'N/A')}")
                st.write(f"**Downloaded Path:** {selected_form.get('downloaded_file_path', 'N/A')}")
                st.write(f"**Processing Time:** {structured_data.get('processing_time', 'N/A')}")
                st.write(f"**Fees:** {structured_data.get('fees', 'N/A')}")
                st.write(f"**Submission Method:** {structured_data.get('submission_method', 'N/A')}")
                st.write(f"**Last Updated:** {selected_form['created_at']}")
            
            # Description
            st.subheader("Description")
            st.write(selected_form.get('description', 'No description available'))
            
            # Supporting documents
            if structured_data.get('supporting_documents'):
                st.subheader("Supporting Documents")
                for doc in structured_data['supporting_documents']:
                    st.write(f"• {doc}")
            
            # Validation warnings
            if selected_form.get('validation_warnings'):
                st.subheader("⚠️ Validation Warnings")
                for warning in selected_form['validation_warnings']:
                    st.warning(warning)
            
            # --- NEW: Download Buttons for Original Document and Extracted Text ---
            st.subheader("Download Options")
            downloaded_file_path = selected_form.get('downloaded_file_path')
            original_filename = Path(downloaded_file_path).name if downloaded_file_path else "document"
            original_file_format = selected_form.get('document_format', 'UNKNOWN').lower()
            
            col_dl1, col_dl2 = st.columns(2)

            if downloaded_file_path and Path(downloaded_file_path).exists():
                # Download Original Document
                original_file_content = processor.get_file_content_bytes(downloaded_file_path)
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
                        st.warning("Original file content not available for download.")

                # Download Extracted Text
                extracted_text_content = processor.get_extracted_text_bytes(downloaded_file_path)
                if extracted_text_content:
                    with col_dl2:
                        st.download_button(
                            label="Download Extracted Text (.txt)",
                            data=extracted_text_content,
                            file_name=f"{Path(original_filename).stem}_extracted.txt",
                            mime="text/plain",
                            key=f"download_extracted_text_{selected_form['id']}"
                        )
                else:
                    with col_dl2:
                        st.warning("Extracted text content not available for download.")
            else:
                st.info("No downloaded file path available or file does not exist for this document.")
            # --- END NEW ---

            # Raw JSON data
            with st.expander("View Raw JSON Data"):
                st.json(selected_form.get('structured_data', {}))
    else:
        st.info("No documents found. Use the Document Discovery page to find and process documents first.")

def validation_panel_page(db, processor, ai_service): # Updated signature
    st.header("✅ Validation & Lawyer Review Panel")
    
    # Get forms that need review
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents for review")
        
        # Filter forms by review status
        review_filter = st.selectbox(
            "Filter by review status:",
            ["All", "Pending Review", "Approved", "Approved with Comments", "Needs Revision", "Downloaded Only", "Partial AI Failure"]
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
                    if form.get('processing_status') == 'partial_ai_failure'
                ]
            else:
                filtered_forms = [
                    form for form in forms 
                    if (form.get('lawyer_review') or {}).get('approval_status') == review_filter
                ]
        
        if filtered_forms:
            for form in filtered_forms:
                with st.expander(f"📋 {form['form_name']} - {form['country']} (Status: {form.get('processing_status', 'N/A')})"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.write(f"**Form ID:** {form['form_id']}")
                        st.write(f"**Description:** {form.get('description', 'N/A')}")
                        st.write(f"**Downloaded Path:** {form.get('downloaded_file_path', 'N/A')}")
                        
                        # Show validation warnings
                        if form.get('validation_warnings'):
                            st.subheader("⚠️ AI Validation Warnings")
                            for warning in form['validation_warnings']:
                                st.warning(warning)
                    
                    with col2:
                        st.subheader("Lawyer Review")
                        
                        # Current review status
                        current_review = form.get('lawyer_review') or {}
                        st.write(f"**Status:** {current_review.get('approval_status', 'Pending Review')}")
                        
                        if current_review.get('reviewer_name'):
                            st.write(f"**Reviewer:** {current_review['reviewer_name']}")
                            st.write(f"**Date:** {current_review.get('review_date', 'N/A')}")
                            st.write(f"**Comments:** {current_review.get('comments', 'None')}")
                        
                        # Review form
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
                                if st.form_submit_button("✨ Re-run AI Validation"):
                                    if not form.get('downloaded_file_path'):
                                        st.error("Cannot re-run AI validation: Document file path is missing.")
                                    else:
                                        with st.spinner("Re-running AI validation..."):
                                            try:
                                                # Re-extract text
                                                extracted_text = processor.extract_text(form['downloaded_file_path'])
                                                
                                                if not extracted_text or len(extracted_text.strip()) < 100:
                                                    st.error("Insufficient text content for AI re-validation (min 100 chars required).")
                                                else:
                                                    # Use the existing structured_data as a base for validation context
                                                    temp_form_data = form.get('structured_data', {})
                                                    temp_form_data.update({
                                                        "country": form.get('country'),
                                                        "visa_category": form.get('visa_category'),
                                                        "form_name": form.get('form_name'),
                                                        "form_id": form.get('form_id'),
                                                        "description": form.get('description'),
                                                        "governing_authority": form.get('governing_authority'),
                                                        "official_source_url": form.get('official_source_url'),
                                                        "discovered_by_query": form.get('discovered_by_query'),
                                                        "downloaded_file_path": form.get('downloaded_file_path'),
                                                        "document_format": form.get('document_format'),
                                                        "processing_status": form.get('processing_status'),
                                                        "last_fetched": form.get('last_fetched') # Keep original fetched date
                                                    })

                                                    # If structured_data is empty, try to re-extract first
                                                    if not temp_form_data.get('form_id') or not temp_form_data.get('form_name'):
                                                        st.info("Structured data is incomplete, attempting full AI re-extraction before validation.")
                                                        doc_info_for_ai = {
                                                            'filename': Path(form['downloaded_file_path']).name,
                                                            'download_url': form['official_source_url'],
                                                            'file_format': form['document_format'],
                                                            'file_path': form['downloaded_file_path'],
                                                            'discovered_by_query': form['discovered_by_query']
                                                        }
                                                        re_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)
                                                        if re_extracted_data:
                                                            temp_form_data.update(re_extracted_data)
                                                            temp_form_data['form_id'] = re_extracted_data.get('form_id', 'N/A')
                                                            temp_form_data['structured_data'] = re_extracted_data # Update structured_data
                                                        else:
                                                            st.error("Full AI re-extraction failed. Cannot proceed with validation.")
                                                            st.rerun()
                                                            continue

                                                    validation_warnings = ai_service.validate_form_data(temp_form_data)
                                                    
                                                    new_processing_status = "validated" if not validation_warnings else "validated_with_warnings"
                                                    
                                                    # Update the database
                                                    update_success = db.update_form_fields(
                                                        form['id'],
                                                        {
                                                            "validation_warnings": validation_warnings,
                                                            "processing_status": new_processing_status,
                                                            "structured_data": temp_form_data.get('structured_data', {}) # Save updated structured data if re-extracted
                                                        }
                                                    )
                                                    
                                                    if update_success:
                                                        st.success("AI validation re-run successfully!")
                                                        st.rerun()
                                                    else:
                                                        st.error("Failed to update form with new AI validation results.")
                                            except Exception as e:
                                                st.error(f"Error during AI re-validation: {e}")
                                                st.code(traceback.format_exc())
        else:
            st.info(f"No forms found with status: {review_filter}")
    else:
        st.info("No documents found for review.")

def export_panel_page(db, export_service):
    st.header("📊 Export Panel")
    
    # Get all forms
    forms = db.get_forms()
    
    if forms:
        st.info(f"Found {len(forms)} documents available for export")
        
        st.subheader("Export Options")
        
        # Filter forms for export
        col1, col2 = st.columns(2)
        
        with col1:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + list(set(form['country'] for form in forms))
            )
        
        with col2:
            status_filter = st.selectbox(
                "Filter by Review Status:",
                ["All", "Approved", "Pending Review", "Needs Revision", "Downloaded Only", "Partial AI Failure"]
            )
        
        # Apply filters
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
                    if form.get('processing_status') == 'partial_ai_failure'
                ]
            else:
                filtered_forms = [
                    form for form in filtered_forms 
                    if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == status_filter
                ]
        
        st.write(f"**Forms to export:** {len(filtered_forms)}")
        
        # Export buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Export as JSON"):
                if len(filtered_forms) == 1:
                    form_data = filtered_forms[0].get('structured_data', {})
                    file_path, file_content = export_service.export_json(form_data)
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
                        file_path, _ = export_service.export_json(form.get('structured_data', {}))
                        if file_path:
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} JSON files to server.")
                else:
                    st.warning("No forms selected for JSON export.")
    
        with col2:
            if st.button("📊 Export as Excel"):
                if filtered_forms:
                    forms_data = [form.get('structured_data', {}) for form in filtered_forms]
                    file_path, file_content = export_service.export_excel(forms_data)
                    if file_content:
                        st.download_button(
                            label="Download Excel",
                            data=file_content,
                            file_name=Path(file_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_excel"
                        )
                else:
                    st.warning("No forms selected for Excel export.")
    
        with col3:
            if st.button("📋 Export Summaries"):
                if filtered_forms:
                    exported_files_count = 0
                    for form in filtered_forms:
                        file_path, file_content = export_service.export_summary_pdf(form.get('structured_data', {}))
                        if file_content:
                            st.download_button(
                                label=f"Download {Path(file_path).name}",
                                data=file_content,
                                file_name=Path(file_path).name,
                                mime="text/plain", # Mime type for TXT
                                key=f"download_summary_{form['id']}" # Unique key for each button
                            )
                            exported_files_count += 1
                    if exported_files_count > 0:
                        st.success(f"Exported {exported_files_count} summary files.")
                else:
                    st.warning("No forms selected for summary export.")
    
        # Preview selected forms
        if filtered_forms:
            st.subheader("Preview of Forms to Export")
            
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
        st.info("No documents available for export.")

def database_viewer_page(db):
    st.header("🗄️ Database Viewer")
    
    # Get all forms
    forms = db.get_forms()
    
    if forms:
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Forms", len(forms))
        
        with col2:
            countries = set(form['country'] for form in forms)
            st.metric("Countries", len(countries))
        
        with col3:
            approved_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status') == 'Approved'
            ])
            st.metric("Approved Forms", approved_forms)
        
        with col4:
            pending_forms = len([
                form for form in forms 
                if (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review') == 'Pending Review'
            ])
            st.metric("Pending Review", pending_forms)
        
        # Search and filter
        st.subheader("Search & Filter")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_term = st.text_input("Search forms (name, ID, description):")
        
        with col2:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + sorted(list(set(form['country'] for form in forms)))
            )
        with col3:
            processing_status_filter = st.selectbox(
                "Filter by Processing Status:",
                ["All", "validated", "validated_with_warnings", "downloaded_only", "partial_ai_failure", "failed"]
            )
        
        # Apply filters
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
        
        # Display results
        st.subheader(f"Forms ({len(filtered_forms)} found)")
        
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
                    st.write(f"**Source:** {source_url[:50]}..." if source_url else "N/A")
                    st.write(f"**Downloaded Path:** {form.get('downloaded_file_path', 'N/A')}")
                
                st.write(f"**Description:** {form.get('description', 'No description')}")
                
                # Show validation warnings
                if form.get('validation_warnings'):
                    st.write("**⚠️ Validation Warnings:**")
                    for warning in form['validation_warnings']:
                        st.write(f"• {warning}")
                
                # Show raw structured data
                with st.expander("View Raw Structured Data"):
                    st.json(form.get('structured_data', {}))
    else:
        st.info("No documents in database. Use the Document Discovery page to find and process documents.")

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
