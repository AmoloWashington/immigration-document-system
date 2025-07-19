import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import streamlit as st
from datetime import datetime
from database import DatabaseManager # New import

class ExportService:
    def __init__(self, output_dir: str, db_manager: DatabaseManager): # Added db_manager
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db_manager = db_manager # Store db_manager instance
    
    def export_json(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes]]:
        """Export form data as JSON and return file path and content."""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Create country directory
        country_dir = self.output_dir / "forms" / form_data.get('country', 'unknown').lower()
        country_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = country_dir / filename
        
        try:
            json_content = json.dumps(form_data, indent=2, ensure_ascii=False)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            st.success(f"JSON exported to server: {file_path}")
            
            # --- NEW: Log export ---
            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["json"],
                    file_path=str(file_path)
                )
            # --- END NEW ---

            return str(file_path), json_content.encode('utf-8') # Return content as bytes
            
        except Exception as e:
            st.error(f"Error exporting JSON: {e}")
            return "", None
    
    def export_excel(self, forms_data: List[Dict[str, Any]], filename: str = None) -> Tuple[str, Optional[bytes]]:
        """Export multiple forms as Excel spreadsheet and return file path and content."""
        
        if not filename:
            filename = f"immigration_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path = self.output_dir / filename
        
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
            excel_buffer = pd.io.excel.ExcelWriter(file_path, engine='openpyxl')
            df.to_excel(excel_buffer, sheet_name='Immigration Forms', index=False)
            
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
                support_df.to_excel(excel_buffer, sheet_name='Supporting Documents', index=False)
            
            excel_buffer.close() # Save the file to disk
            
            # Read the saved file content as bytes
            with open(file_path, 'rb') as f:
                excel_content = f.read()

            st.success(f"Excel exported to server: {file_path}")

            # --- NEW: Log export ---
            if self.db_manager:
                exported_form_ids = [form.get('id') for form in forms_data if form.get('id')]
                self.db_manager.insert_export_log(
                    document_ids=exported_form_ids,
                    export_formats=["excel"],
                    file_path=str(file_path)
                )
            # --- END NEW ---

            return str(file_path), excel_content
            
        except Exception as e:
            st.error(f"Error exporting Excel: {e}")
            return "", None
    
    def export_summary_pdf(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes]]:
        """Export form summary as PDF (simplified to TXT) and return file path and content."""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_summary.txt"  # Using TXT for simplicity
        
        file_path = self.output_dir / filename
        
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

            # --- NEW: Log export ---
            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["summary_txt"], # Changed from pdf to txt
                    file_path=str(file_path)
                )
            # --- END NEW ---

            return str(file_path), summary_content.encode('utf-8') # Return content as bytes
            
        except Exception as e:
            st.error(f"Error exporting summary: {e}")
            return "", None
