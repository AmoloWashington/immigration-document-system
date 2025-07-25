import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import streamlit as st
from datetime import datetime
from database import DatabaseManager
import cloudinary
import cloudinary.uploader

class ExportService:
    def __init__(self, output_dir: str, db_manager: DatabaseManager, cloudinary_url: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db_manager = db_manager
        self.cloudinary_url = cloudinary_url
        if self.cloudinary_url:
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(self.cloudinary_url)
                cloudinary.config(
                    cloud_name=parsed_url.hostname,
                    api_key=parsed_url.username,
                    api_secret=parsed_url.password,
                    secure=True
                )
                st.success("Cloudinary configured for export uploads.")
            except Exception as e:
                st.error(f"Error configuring Cloudinary for export uploads: {e}. Please check your CLOUDINARY_URL format.")
                self.cloudinary_url = None
        else:
            st.warning("Cloudinary URL not configured. Exports will only be stored locally.")
    
    def _upload_to_cloudinary(self, file_path: str, folder: str = "immigration_exports") -> Optional[str]:
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
            st.json(response)
            secure_url = response.get('secure_url')
            if secure_url:
                st.success(f"Uploaded to Cloudinary: {secure_url}")
                return secure_url
            else:
                st.error(f"Cloudinary upload successful, but 'secure_url' not found in response: {response}")
                return None
        except Exception as e:
            st.error(f"Error uploading to Cloudinary: {e}")
            return None

    def _json_serializer(self, obj):
        """JSON serializer function that handles datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def export_json(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]:
        """Export form data as JSON, save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""

        # Fix: Ensure country and form_id are strings before calling .lower()
        country = (form_data.get('country') or 'unknown').lower()
        form_id = (form_data.get('form_id') or 'unknown').lower()

        if not filename:
            filename = f"{country}_{form_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        country_dir = self.output_dir / "forms" / country
        country_dir.mkdir(parents=True, exist_ok=True)

        file_path = country_dir / filename
        cloudinary_url = None

        try:
            json_content = json.dumps(form_data, indent=2, ensure_ascii=False, default=self._json_serializer)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            st.success(f"JSON exported to server: {file_path}")
            
            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder=f"immigration_exports/json/{country}")

            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["json"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url
                )

            return str(file_path), json_content.encode('utf-8'), cloudinary_url
            
        except Exception as e:
            st.error(f"Error exporting JSON: {e}")
            return "", None, None
    
    def export_excel(self, forms_data: List[Dict[str, Any]], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]:
        """Export multiple forms as Excel spreadsheet, save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""
        
        if not filename:
            filename = f"immigration_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        file_path = self.output_dir / filename
        excel_content = None
        cloudinary_url = None
        
        try:
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
            
            excel_writer = pd.io.excel.ExcelWriter(file_path, engine='openpyxl')
            df.to_excel(excel_writer, sheet_name='Immigration Forms', index=False)
            
            support_docs = []
            for form in forms_data:
                form_id = form.get('form_id', 'Unknown')
                for doc in form.get('structured_data', {}).get('supporting_documents', []): # Access supporting_documents from structured_data
                    support_docs.append({
                        'Form ID': form_id,
                        'Supporting Document': doc
                    })
            
            if support_docs:
                support_df = pd.DataFrame(support_docs)
                support_df.to_excel(excel_writer, sheet_name='Supporting Documents', index=False)
            
            excel_writer.close()
            
            with open(file_path, 'rb') as f:
                excel_content = f.read()

            st.success(f"Excel exported to server: {file_path}")

            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder="immigration_exports/excel")

            if self.db_manager:
                exported_form_ids = [form.get('id') for form in forms_data if form.get('id')]
                self.db_manager.insert_export_log(
                    document_ids=exported_form_ids,
                    export_formats=["excel"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url
                )

            return str(file_path), excel_content, cloudinary_url
            
        except Exception as e:
            st.error(f"Error exporting Excel: {e}")
            return "", None, None
    
    def export_summary_markdown(self, form_data: Dict[str, Any], filename: str = None) -> Tuple[str, Optional[bytes], Optional[str]]:
        """Export form summary as Markdown, save locally, upload to Cloudinary, and return file path, content, and Cloudinary URL."""
        
        # Fix: Ensure country and form_id are strings before calling .lower()
        country = (form_data.get('country') or 'unknown').lower()
        form_id = (form_data.get('form_id') or 'unknown').lower()

        if not filename:
            filename = f"{country}_{form_id}_summary.md"
        
        country_dir = self.output_dir / "forms" / country
        country_dir.mkdir(parents=True, exist_ok=True)

        file_path = country_dir / filename
        summary_content = None
        cloudinary_url = None
        
        try:
            full_markdown_summary = form_data.get('structured_data', {}).get('full_markdown_summary')
            
            if full_markdown_summary:
                summary_content = full_markdown_summary
            else:
                summary_content_lines = []
                summary_content_lines.append(f"# Immigration Form Summary: {form_data.get('form_name', 'N/A')}\n\n")
                summary_content_lines.append(f"**Country:** {form_data.get('country', 'N/A')}\n")
                summary_content_lines.append(f"**Visa Category:** {form_data.get('visa_category', 'N/A')}\n")
                summary_content_lines.append(f"**Form ID:** {form_data.get('form_id', 'N/A')}\n")
                summary_content_lines.append(f"**Governing Authority:** {form_data.get('governing_authority', 'N/A')}\n\n")
                summary_content_lines.append(f"**Description:** {form_data.get('description', 'N/A')}\n\n")
                
                if form_data.get('structured_data', {}).get('target_applicants'):
                    summary_content_lines.append(f"**Target Applicants:** {form_data['structured_data']['target_applicants']}\n\n")
                if form_data.get('structured_data', {}).get('submission_method'):
                    summary_content_lines.append(f"**Submission Method:** {form_data['structured_data']['submission_method']}\n\n")
                if form_data.get('structured_data', {}).get('processing_time'):
                    summary_content_lines.append(f"**Processing Time:** {form_data['structured_data']['processing_time']}\n\n")
                if form_data.get('structured_data', {}).get('fees'):
                    summary_content_lines.append(f"**Fees:** {form_data['structured_data']['fees']}\n\n")
                
                if form_data.get('structured_data', {}).get('supporting_documents'):
                    summary_content_lines.append("## Supporting Documents\n")
                    for doc in form_data['structured_data']['supporting_documents']:
                        summary_content_lines.append(f"- {doc}\n")
                    summary_content_lines.append("\n")
                
                if form_data.get('validation_warnings'):
                    summary_content_lines.append("## Validation Warnings\n")
                    for warning in form_data['validation_warnings']:
                        summary_content_lines.append(f"⚠️ {warning}\n")
                    summary_content_lines.append("\n")
                
                summary_content_lines.append(f"**Official Source URL:** {form_data.get('official_source_url', 'N/A')}\n")
                summary_content_lines.append(f"**Last Updated:** {form_data.get('updated_at', 'N/A')}\n")
                summary_content = "".join(summary_content_lines)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(summary_content)
            
            st.success(f"Summary exported to server: {file_path}")

            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder=f"immigration_exports/summaries/{country}")

            if self.db_manager and form_data.get('id'):
                self.db_manager.insert_export_log(
                    document_ids=[form_data['id']],
                    export_formats=["summary_md"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url
                )

            return str(file_path), summary_content.encode('utf-8'), cloudinary_url
            
        except Exception as e:
            st.error(f"Error exporting summary: {e}")
            return "", None, None

    def generate_comprehensive_report(self, forms: List[Dict[str, Any]]) -> Tuple[str, Optional[bytes], Optional[str]]:
        """
        Generates a comprehensive Markdown report for a list of forms,
        including links to original documents, JSON, and Markdown summaries on Cloudinary.
        """
        report_filename = f"usa_immigration_forms_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = self.output_dir / report_filename
        report_content_lines = []
        cloudinary_report_url = None

        report_content_lines.append("# Comprehensive USA Immigration Forms Report\n\n")
        report_content_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        report_content_lines.append(f"This report lists all processed USA immigration forms, including links to their original documents, structured JSON data, and comprehensive Markdown summaries stored on Cloudinary.\n\n")
        report_content_lines.append("## Overview by Visa Category\n\n")

        grouped_by_visa = {}
        for form in forms:
            visa_cat = form.get('visa_category', 'Uncategorized')
            if visa_cat not in grouped_by_visa:
                grouped_by_visa[visa_cat] = []
            grouped_by_visa[visa_cat].append(form)
        
        for visa_category, category_forms in sorted(grouped_by_visa.items()):
            report_content_lines.append(f"### {visa_category} ({len(category_forms)} Forms)\n\n")
            for form in category_forms:
                form_name = form.get('form_name', 'Unknown Form')
                form_id = form.get('form_id', 'N/A')
                description = form.get('description', 'No description available.')
                official_source_url = form.get('official_source_url', 'N/A')
                
                original_doc_info = self.db_manager.get_document_by_form_id(form['id'])
                original_cloudinary_url = original_doc_info.get('cloudinary_url') if original_doc_info else 'N/A'

                # Generate JSON and Markdown summary exports to ensure they exist on Cloudinary
                json_file_path, _, json_cloudinary_url = self.export_json(form)
                md_summary_file_path, _, md_summary_cloudinary_url = self.export_summary_markdown(form)

                report_content_lines.append(f"#### 📄 {form_name} (Form ID: {form_id})\n")
                report_content_lines.append(f"- **Description:** {description}\n")
                report_content_lines.append(f"- **Official Source:** [Link]({official_source_url})\n")
                report_content_lines.append(f"- **Original Document (Cloudinary):** [Link]({original_cloudinary_url})\n")
                report_content_lines.append(f"- **Structured Data (JSON on Cloudinary):** [Link]({json_cloudinary_url if json_cloudinary_url else 'N/A'})\n")
                report_content_lines.append(f"- **Comprehensive Summary (Markdown on Cloudinary):** [Link]({md_summary_cloudinary_url if md_summary_cloudinary_url else 'N/A'})\n")
                
                if form.get('validation_warnings'):
                    report_content_lines.append("- **Validation Warnings:**\n")
                    for warning in form['validation_warnings']:
                        report_content_lines.append(f"  - ⚠️ {warning}\n")
                report_content_lines.append("\n---\n\n")

        report_full_content = "".join(report_content_lines)

        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_full_content)
            st.success(f"Comprehensive report saved locally: {report_path}")

            cloudinary_report_url = self._upload_to_cloudinary(str(report_path), folder="immigration_exports/reports")
            
            if self.db_manager:
                exported_form_ids = [form['id'] for form in forms if form.get('id')]
                self.db_manager.insert_export_log(
                    document_ids=exported_form_ids,
                    export_formats=["comprehensive_report_md"],
                    file_path=str(report_path),
                    cloudinary_url=cloudinary_report_url
                )

            return str(report_path), report_full_content.encode('utf-8'), cloudinary_report_url
        except Exception as e:
            st.error(f"Error generating comprehensive report: {e}")
            return "", None, None

    def export_full_database(self, export_format: str = "json") -> Tuple[str, Optional[bytes], Optional[str]]:
        """Export complete database with all tables and fields in specified format"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        cloudinary_url = None

        try:
            # Get all forms with complete data
            all_forms = self.db_manager.get_forms()

            if not all_forms:
                st.warning("No data found in database to export.")
                return "", None, None

            # Flatten all data including structured_data fields
            flattened_data = []
            for form in all_forms:
                row = {}

                # Basic form fields
                row['id'] = form.get('id')
                row['country'] = form.get('country')
                row['visa_category'] = form.get('visa_category')
                row['form_name'] = form.get('form_name')
                row['form_id'] = form.get('form_id')
                row['description'] = form.get('description')
                row['governing_authority'] = form.get('governing_authority')
                row['official_source_url'] = form.get('official_source_url')
                row['discovered_by_query'] = form.get('discovered_by_query')
                row['downloaded_file_path'] = form.get('downloaded_file_path')
                row['document_format'] = form.get('document_format')
                row['processing_status'] = form.get('processing_status')
                row['created_at'] = form.get('created_at')
                row['updated_at'] = form.get('updated_at')

                # Validation warnings
                warnings = form.get('validation_warnings', [])
                row['validation_warnings'] = '; '.join(warnings) if warnings else ''
                row['validation_warnings_count'] = len(warnings) if warnings else 0

                # Lawyer review data
                lawyer_review = form.get('lawyer_review', {})
                row['lawyer_review_status'] = lawyer_review.get('approval_status', 'Pending Review')
                row['lawyer_reviewer_name'] = lawyer_review.get('reviewer_name', '')
                row['lawyer_review_date'] = lawyer_review.get('review_date', '')
                row['lawyer_review_comments'] = lawyer_review.get('comments', '')

                # Structured data fields
                structured_data = form.get('structured_data', {})
                if structured_data:
                    row['target_applicants'] = structured_data.get('target_applicants', '')
                    row['submission_method'] = structured_data.get('submission_method', '')
                    row['processing_time'] = structured_data.get('processing_time', '')
                    row['fees'] = structured_data.get('fees', '')
                    row['language'] = structured_data.get('language', '')

                    # Required fields
                    required_fields = structured_data.get('required_fields', [])
                    if required_fields:
                        for i, field in enumerate(required_fields, 1):
                            if i <= 10:  # Limit to first 10 fields to avoid too many columns
                                row[f'required_field_{i}_name'] = field.get('name', '')
                                row[f'required_field_{i}_type'] = field.get('type', '')
                                row[f'required_field_{i}_description'] = field.get('description', '')
                                row[f'required_field_{i}_example'] = field.get('example_value', '')

                    # Supporting documents
                    supporting_docs = structured_data.get('supporting_documents', [])
                    row['supporting_documents'] = '; '.join(supporting_docs) if supporting_docs else ''
                    row['supporting_documents_count'] = len(supporting_docs) if supporting_docs else 0

                    # Extract text length
                    row['extracted_text_length'] = structured_data.get('extracted_text_length', 0)
                else:
                    # Set empty values for structured data fields
                    row['target_applicants'] = ''
                    row['submission_method'] = ''
                    row['processing_time'] = ''
                    row['fees'] = ''
                    row['language'] = ''
                    row['supporting_documents'] = ''
                    row['supporting_documents_count'] = 0
                    row['extracted_text_length'] = 0

                # Get document information
                document_info = self.db_manager.get_document_by_form_id(form['id'])
                if document_info:
                    row['document_filename'] = document_info.get('filename', '')
                    row['document_file_format'] = document_info.get('file_format', '')
                    row['document_file_size_bytes'] = document_info.get('file_size_bytes', 0)
                    row['document_cloudinary_url'] = document_info.get('cloudinary_url', '')
                else:
                    row['document_filename'] = ''
                    row['document_file_format'] = ''
                    row['document_file_size_bytes'] = 0
                    row['document_cloudinary_url'] = ''

                flattened_data.append(row)

            # Export based on format
            if export_format.lower() == "json":
                filename = f"complete_database_export_{timestamp}.json"
                file_path = self.output_dir / filename

                json_content = json.dumps(flattened_data, indent=2, ensure_ascii=False, default=self._json_serializer)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_content)

                content = json_content.encode('utf-8')
                st.success(f"Complete database exported as JSON: {file_path}")

            elif export_format.lower() == "csv":
                filename = f"complete_database_export_{timestamp}.csv"
                file_path = self.output_dir / filename

                df = pd.DataFrame(flattened_data)
                df.to_csv(file_path, index=False, encoding='utf-8')

                with open(file_path, 'rb') as f:
                    content = f.read()

                st.success(f"Complete database exported as CSV: {file_path}")

            elif export_format.lower() == "xlsx":
                filename = f"complete_database_export_{timestamp}.xlsx"
                file_path = self.output_dir / filename

                df = pd.DataFrame(flattened_data)

                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Complete Database', index=False)

                with open(file_path, 'rb') as f:
                    content = f.read()

                st.success(f"Complete database exported as Excel: {file_path}")

            else:
                st.error(f"Unsupported export format: {export_format}")
                return "", None, None

            # Upload to Cloudinary
            cloudinary_url = self._upload_to_cloudinary(str(file_path), folder="immigration_exports/database")

            # Log export
            if self.db_manager:
                exported_form_ids = [form['id'] for form in all_forms]
                self.db_manager.insert_export_log(
                    document_ids=exported_form_ids,
                    export_formats=[f"database_{export_format}"],
                    file_path=str(file_path),
                    cloudinary_url=cloudinary_url
                )

            return str(file_path), content, cloudinary_url

        except Exception as e:
            st.error(f"Error exporting complete database: {e}")
            return "", None, None
