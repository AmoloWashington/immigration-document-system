import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import streamlit as st
from datetime import datetime
from database import DatabaseManager
import cloudinary # NEW: Import Cloudinary
import cloudinary.uploader # NEW: Import Cloudinary uploader

class ExportService:
    def __init__(self, output_dir: str, db_manager: DatabaseManager, cloudinary_url: Optional[str] = None): # NEW: Added cloudinary_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db_manager = db_manager
        self.cloudinary_url = cloudinary_url # NEW: Store Cloudinary URL
        if self.cloudinary_url: # NEW: Configure Cloudinary
            cloudinary.config(cloud_name=self.cloudinary_url.split('@')[1],
                              api_key=self.cloudinary_url.split('//')[1].split(':')[0],
                              api_secret=self.cloudinary_url.split(':')[2].split('@')[0],
                              secure=True)
            st.success("Cloudinary configured for export uploads.")
        else:
            st.warning("Cloudinary URL not configured. Exports will only be stored locally.")
    
    def _upload_to_cloudinary(self, file_path: str, folder: str = "immigration_exports") -> Optional[str]: # NEW: Cloudinary upload method for exports
        """Uploads a file to Cloudinary and returns its URL."""
        if not self.cloudinary_url:
            st.warning("Cloudinary not configured. Skipping upload.")
            return None
        try:
            st.info(f"Uploading {Path(file_path).name} to Cloudinary...")
            public_id = Path(file_path).stem.replace(" ", "_").replace(".", "_") + "_" + datetime.now().strftime('%Y%m%d%H%M%S')
            
            response = cloudinary.uploader.upload(
                file_path,
                folder=folder,
                public_id=public_id,
                resource_type="auto"
            )
            st.success(f"Uploaded to Cloudinary: {response['secure_url']}")
            return response['secure_url']
        except Exception as e:
            st.error(f"Error uploading to Cloudinary: {e}")
            return None

    def export_json(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]: # NEW: Return Cloudinary URL
        """Export form data as JSON, save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Create country directory
        country_dir = self.output_dir / "forms" / form_data.get('country', 'unknown').lower()
        country_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = country_dir / filename
        cloudinary_url = None # NEW: Initialize Cloudinary URL
        
        try:
            json_content = json.dumps(form_data, indent=2, ensure_ascii=False)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            st.success(f"JSON exported to server: {file_path}")
            
            # NEW: Upload to Cloudinary
            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder=f"immigration_exports/json/{form_data.get('country', 'unknown').lower()}")

            # --- NEW: Log export ---
            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["json"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url # NEW: Log Cloudinary URL
                )
            # --- END NEW ---

            return str(file_path), json_content.encode('utf-8'), cloudinary_url # NEW: Return Cloudinary URL
            
        except Exception as e:
            st.error(f"Error exporting JSON: {e}")
            return "", None, None
    
    def export_excel(self, forms_data: List[Dict[str, Any]], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]: # NEW: Return Cloudinary URL
        """Export multiple forms as Excel spreadsheet, save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""
        
        if not filename:
            filename = f"immigration_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path = self.output_dir / filename
        excel_content = None
        cloudinary_url = None # NEW: Initialize Cloudinary URL
        
        try:
            # Create DataFrame
            df_data = []
            for form in forms_data:
                row = {
                    'Country': form.get('country', ''),
                    'Visa Category': form.get('visa_category', ''),
                    'Form Name': form.get('form_name', ''),
                    'Form ID': form.get('form_id', ''),
                    'Description': form.get('description', ''),
                    'Governing Authority': form.get('governing_authority', ''),
                    'Target Applicants': form.get('target_applicants', ''),
                    'Submission Method': form.get('submission_method', ''),
                    'Processing Time': form.get('processing_time', ''),
                    'Fees': form.get('fees', ''),
                    'Official Source URL': form.get('official_source_url', ''),
                    'Validation Warnings': '; '.join(form.get('validation_warnings', [])),
                    'Last Fetched': form.get('last_fetched', ''),
                    'Lawyer Review Status': form.get('lawyer_review', {}).get('approval_status', 'Pending')
                }
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            
            # Export to Excel in memory first to get bytes
            excel_writer = pd.io.excel.ExcelWriter(file_path, engine='openpyxl') # Use a variable for the writer
            df.to_excel(excel_writer, sheet_name='Immigration Forms', index=False)
            
            # Add supporting documents sheet if available
            support_docs = []
            for form in forms_data:
                form_id = form.get('form_id', 'Unknown')
                for doc in form.get('supporting_documents', []):
                    support_docs.append({
                        'Form ID': form_id,
                        'Supporting Document': doc
                    })
            
            if support_docs:
                support_df = pd.DataFrame(support_docs)
                support_df.to_excel(excel_writer, sheet_name='Supporting Documents', index=False)
            
            excel_writer.close() # Save the file to disk
            
            # Read the saved file content as bytes
            with open(file_path, 'rb') as f:
                excel_content = f.read()

            st.success(f"Excel exported to server: {file_path}")

            # NEW: Upload to Cloudinary
            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder="immigration_exports/excel")

            # --- NEW: Log export ---
            if self.db_manager:
                exported_form_ids = [form.get('id') for form in forms_data if form.get('id')]
                self.db_manager.insert_export_log(
                    document_ids=exported_form_ids,
                    export_formats=["excel"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url # NEW: Log Cloudinary URL
                )
            # --- END NEW ---

            return str(file_path), excel_content, cloudinary_url # NEW: Return Cloudinary URL
            
        except Exception as e:
            st.error(f"Error exporting Excel: {e}")
            return "", None, None
    
    def export_summary_pdf(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]: # NEW: Return Cloudinary URL
        """Export form summary as PDF (simplified to TXT), save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_summary.txt"  # Using TXT for simplicity
        
        file_path = self.output_dir / filename
        summary_content = None
        cloudinary_url = None # NEW: Initialize Cloudinary URL
        
        try:
            summary_content_lines = []
            summary_content_lines.append("IMMIGRATION FORM SUMMARY\n")
            summary_content_lines.append("=" * 50 + "\n\n")
            
            summary_content_lines.append(f"Country: {form_data.get('country', 'N/A')}\n")
            summary_content_lines.append(f"Visa Category: {form_data.get('visa_category', 'N/A')}\n")
            summary_content_lines.append(f"Form Name: {form_data.get('form_name', 'N/A')}\n")
            summary_content_lines.append(f"Form ID: {form_data.get('form_id', 'N/A')}\n")
            summary_content_lines.append(f"Governing Authority: {form_data.get('governing_authority', 'N/A')}\n\n")
            
            summary_content_lines.append("DESCRIPTION:\n")
            summary_content_lines.append(f"{form_data.get('description', 'N/A')}\n\n")
            
            summary_content_lines.append("TARGET APPLICANTS:\n")
            summary_content_lines.append(f"{form_data.get('target_applicants', 'N/A')}\n\n")
            
            summary_content_lines.append("SUBMISSION METHOD:\n")
            summary_content_lines.append(f"{form_data.get('submission_method', 'N/A')}\n\n")
            
            summary_content_lines.append("PROCESSING TIME:\n")
            summary_content_lines.append(f"{form_data.get('processing_time', 'N/A')}\n\n")
            
            summary_content_lines.append("FEES:\n")
            summary_content_lines.append(f"{form_data.get('fees', 'N/A')}\n\n")
            
            if form_data.get('supporting_documents'):
                summary_content_lines.append("SUPPORTING DOCUMENTS:\n")
                for doc in form_data.get('supporting_documents', []):
                    summary_content_lines.append(f"- {doc}\n")
                summary_content_lines.append("\n")
            
            if form_data.get('validation_warnings'):
                summary_content_lines.append("VALIDATION WARNINGS:\n")
                for warning in form_data.get('validation_warnings', []):
                    summary_content_lines.append(f"⚠️ {warning}\n")
                summary_content_lines.append("\n")
            
            summary_content_lines.append(f"Source: {form_data.get('official_source_url', 'N/A')}\n")
            summary_content_lines.append(f"Last Updated: {form_data.get('last_fetched', 'N/A')}\n")

            summary_content = "".join(summary_content_lines)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            st.success(f"Summary exported to server: {file_path}")

            # NEW: Upload to Cloudinary
            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder=f"immigration_exports/summaries/{form_data.get('country', 'unknown').lower()}")

            # --- NEW: Log export ---
            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["summary_txt"], # Changed from pdf to txt
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url # NEW: Log Cloudinary URL
                )
            # --- END NEW ---

            return str(file_path), summary_content.encode('utf-8'), cloudinary_url # NEW: Return Cloudinary URL
            
        except Exception as e:
            st.error(f"Error exporting summary: {e}")
            return "", None, None
