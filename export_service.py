import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import streamlit as st
from datetime import datetime

class ExportService:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def export_json(self, form_data: Dict[str, Any], filename: str = None) -> str:
        """Export form data as JSON"""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Create country directory
        country_dir = self.output_dir / "forms" / form_data.get('country', 'unknown').lower()
        country_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = country_dir / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(form_data, f, indent=2, ensure_ascii=False)
            
            st.success(f"JSON exported: {file_path}")
            return str(file_path)
            
        except Exception as e:
            st.error(f"Error exporting JSON: {e}")
            return ""
    
    def export_excel(self, forms_data: List[Dict[str, Any]], filename: str = None) -> str:
        """Export multiple forms as Excel spreadsheet"""
        
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
            
            # Export to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Immigration Forms', index=False)
                
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
                    support_df.to_excel(writer, sheet_name='Supporting Documents', index=False)
            
            st.success(f"Excel exported: {file_path}")
            return str(file_path)
            
        except Exception as e:
            st.error(f"Error exporting Excel: {e}")
            return ""
    
    def export_summary_pdf(self, form_data: Dict[str, Any], filename: str = None) -> str:
        """Export form summary as PDF (simplified version)"""
        
        if not filename:
            country = form_data.get('country', 'unknown').lower()
            form_id = form_data.get('form_id', 'unknown').lower()
            filename = f"{country}_{form_id}_summary.txt"  # Using TXT for simplicity
        
        file_path = self.output_dir / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("IMMIGRATION FORM SUMMARY\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"Country: {form_data.get('country', 'N/A')}\n")
                f.write(f"Visa Category: {form_data.get('visa_category', 'N/A')}\n")
                f.write(f"Form Name: {form_data.get('form_name', 'N/A')}\n")
                f.write(f"Form ID: {form_data.get('form_id', 'N/A')}\n")
                f.write(f"Governing Authority: {form_data.get('governing_authority', 'N/A')}\n\n")
                
                f.write("DESCRIPTION:\n")
                f.write(f"{form_data.get('description', 'N/A')}\n\n")
                
                f.write("TARGET APPLICANTS:\n")
                f.write(f"{form_data.get('target_applicants', 'N/A')}\n\n")
                
                f.write("SUBMISSION METHOD:\n")
                f.write(f"{form_data.get('submission_method', 'N/A')}\n\n")
                
                f.write("PROCESSING TIME:\n")
                f.write(f"{form_data.get('processing_time', 'N/A')}\n\n")
                
                f.write("FEES:\n")
                f.write(f"{form_data.get('fees', 'N/A')}\n\n")
                
                if form_data.get('supporting_documents'):
                    f.write("SUPPORTING DOCUMENTS:\n")
                    for doc in form_data.get('supporting_documents', []):
                        f.write(f"- {doc}\n")
                    f.write("\n")
                
                if form_data.get('validation_warnings'):
                    f.write("VALIDATION WARNINGS:\n")
                    for warning in form_data.get('validation_warnings', []):
                        f.write(f"⚠️ {warning}\n")
                    f.write("\n")
                
                f.write(f"Source: {form_data.get('official_source_url', 'N/A')}\n")
                f.write(f"Last Updated: {form_data.get('last_fetched', 'N/A')}\n")
            
            st.success(f"Summary exported: {file_path}")
            return str(file_path)
            
        except Exception as e:
            st.error(f"Error exporting summary: {e}")
            return ""
