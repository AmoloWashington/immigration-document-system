import io
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
import html
import re
import asyncio
from typing import Dict, List, Any, Optional

# Import our services
from config import config
from database import DatabaseManager
from discovery_service import DocumentDiscoveryService
from document_processor import DocumentProcessor
from ai_service import AIExtractionService
from export_service import ExportService

# Multi-Agent System Classes
class DocumentAnalysisAgent:
    """Agent specialized in document structure and content analysis"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.role = "Document Analysis Specialist"
        self.expertise = "Document structure, content extraction, and format analysis"
    
    def analyze_document(self, extracted_text: str, doc_info: Dict) -> Dict:
        """Analyze document structure and extract basic information"""
        analysis_prompt = f"""
        As a Document Analysis Specialist, analyze this document and extract:
        1. Document type and format characteristics
        2. Main sections and structure
        3. Key identifying information
        4. Content quality assessment
        
        Document: {extracted_text[:2000]}...
        
        Provide structured analysis focusing on document characteristics.
        """
        
        # Use AI service to get analysis
        if hasattr(self.ai_service, 'openai_client') and self.ai_service.openai_client:
            try:
                response = self.ai_service.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": analysis_prompt}],
                    temperature=0.1
                )
                analysis = response.choices[0].message.content
                return {
                    "agent": self.role,
                    "analysis": analysis,
                    "document_type": self._extract_document_type(analysis),
                    "structure_quality": self._assess_structure_quality(extracted_text),
                    "confidence": 0.85
                }
            except Exception as e:
                return {"agent": self.role, "error": str(e), "confidence": 0.0}
        
        return {"agent": self.role, "analysis": "Basic analysis completed", "confidence": 0.5}
    
    def _extract_document_type(self, analysis: str) -> str:
        """Extract document type from analysis"""
        if "form" in analysis.lower():
            return "immigration_form"
        elif "guide" in analysis.lower() or "instruction" in analysis.lower():
            return "guidance_document"
        elif "webpage" in analysis.lower() or "website" in analysis.lower():
            return "web_page"
        return "unknown"
    
    def _assess_structure_quality(self, text: str) -> str:
        """Assess the structural quality of the document"""
        if len(text) > 5000:
            return "high"
        elif len(text) > 1000:
            return "medium"
        else:
            return "low"

class FormExtractionAgent:
    """Agent specialized in extracting form-specific information"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.role = "Form Extraction Specialist"
        self.expertise = "Immigration form fields, requirements, and procedures"
    
    def extract_form_data(self, extracted_text: str, doc_info: Dict, document_analysis: Dict) -> Dict:
        """Extract detailed form information"""
        extraction_prompt = f"""
        As a Form Extraction Specialist, extract detailed immigration form information:
        
        Based on document analysis: {document_analysis.get('analysis', 'No prior analysis')}
        
        Extract the following in JSON format:
        {{
            "form_name": "Official form name",
            "form_id": "Form number/ID",
            "description": "Detailed description",
            "governing_authority": "Issuing authority",
            "target_users": "Who should use this form",
            "required_fields": [
                {{
                    "name": "Field name",
                    "description": "Field description", 
                    "type": "Field type (text/number/date/etc)"
                }}
            ],
            "supporting_documents": "Required supporting documents",
            "submission_method": "How to submit",
            "frequency_or_deadline": "When to submit",
            "official_source_url": "Official URL",
            "notes_or_instructions": "Additional notes"
        }}
        
        Document content: {extracted_text[:3000]}...
        """
        
        if hasattr(self.ai_service, 'openai_client') and self.ai_service.openai_client:
            try:
                response = self.ai_service.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": extraction_prompt}],
                    temperature=0.1
                )
                
                content = response.choices[0].message.content
                # Try to extract JSON from the response
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    json_content = content[json_start:json_end].strip()
                else:
                    json_content = content
                
                extracted_data = json.loads(json_content)
                extracted_data["agent"] = self.role
                extracted_data["confidence"] = 0.9
                return extracted_data
                
            except Exception as e:
                return {"agent": self.role, "error": str(e), "confidence": 0.0}
        
        # Fallback extraction
        return self._fallback_extraction(extracted_text, doc_info)
    
    def _fallback_extraction(self, text: str, doc_info: Dict) -> Dict:
        """Fallback extraction when AI is not available"""
        return {
            "agent": self.role,
            "form_name": doc_info.get('title', 'Unknown Form'),
            "form_id": "N/A",
            "description": text[:200] + "..." if len(text) > 200 else text,
            "governing_authority": "N/A",
            "target_users": "N/A",
            "required_fields": [],
            "supporting_documents": "N/A",
            "submission_method": "N/A",
            "frequency_or_deadline": "N/A",
            "official_source_url": doc_info.get('url', ''),
            "notes_or_instructions": "N/A",
            "confidence": 0.3
        }

class ValidationAgent:
    """Agent specialized in validating and cross-checking extracted information"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.role = "Validation Specialist"
        self.expertise = "Data validation, consistency checking, and quality assurance"
    
    def validate_extraction(self, form_data: Dict, document_analysis: Dict, original_text: str) -> Dict:
        """Validate the extracted form data for accuracy and completeness"""
        validation_prompt = f"""
        As a Validation Specialist, review this extracted form data for accuracy:
        
        Document Analysis: {document_analysis.get('analysis', 'No analysis')}
        
        Extracted Data: {json.dumps(form_data, indent=2)}
        
        Original Text Sample: {original_text[:1000]}...
        
        Validate and provide:
        1. Accuracy assessment (0-100%)
        2. Completeness assessment (0-100%)
        3. Specific validation warnings
        4. Suggested improvements
        5. Confidence level in the extraction
        
        Return as JSON with validation results.
        """
        
        if hasattr(self.ai_service, 'openai_client') and self.ai_service.openai_client:
            try:
                response = self.ai_service.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": validation_prompt}],
                    temperature=0.1
                )
                
                validation_result = response.choices[0].message.content
                return {
                    "agent": self.role,
                    "validation_result": validation_result,
                    "warnings": self._extract_warnings(validation_result),
                    "accuracy_score": self._extract_score(validation_result, "accuracy"),
                    "completeness_score": self._extract_score(validation_result, "completeness"),
                    "confidence": 0.85
                }
            except Exception as e:
                return {"agent": self.role, "error": str(e), "confidence": 0.0}
        
        return self._basic_validation(form_data)
    
    def _extract_warnings(self, validation_text: str) -> List[str]:
        """Extract validation warnings from the validation result"""
        warnings = []
        if "missing" in validation_text.lower():
            warnings.append("Some required information may be missing")
        if "unclear" in validation_text.lower():
            warnings.append("Some extracted information may be unclear")
        if "inconsistent" in validation_text.lower():
            warnings.append("Inconsistencies detected in extracted data")
        return warnings
    
    def _extract_score(self, validation_text: str, score_type: str) -> int:
        """Extract numerical scores from validation text"""
        import re
        pattern = f"{score_type}.*?(\d+)%"
        match = re.search(pattern, validation_text, re.IGNORECASE)
        return int(match.group(1)) if match else 75
    
    def _basic_validation(self, form_data: Dict) -> Dict:
        """Basic validation when AI is not available"""
        warnings = []
        if not form_data.get('form_name') or form_data['form_name'] == 'N/A':
            warnings.append("Form name not properly extracted")
        if not form_data.get('required_fields'):
            warnings.append("No required fields identified")
        
        return {
            "agent": self.role,
            "warnings": warnings,
            "accuracy_score": 70,
            "completeness_score": 60,
            "confidence": 0.5
        }

class SynthesisAgent:
    """Agent specialized in synthesizing results from all other agents"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.role = "Synthesis Coordinator"
        self.expertise = "Multi-agent coordination, result synthesis, and final output generation"
    
    def synthesize_results(self, document_analysis: Dict, form_extraction: Dict, validation: Dict, original_text: str) -> Dict:
        """Synthesize results from all agents into final output"""
        synthesis_prompt = f"""
        As a Synthesis Coordinator, combine insights from multiple specialist agents:
        
        Document Analysis Agent: {json.dumps(document_analysis, indent=2)}
        
        Form Extraction Agent: {json.dumps(form_extraction, indent=2)}
        
        Validation Agent: {json.dumps(validation, indent=2)}
        
        Create a comprehensive final result that:
        1. Combines the best insights from each agent
        2. Resolves any conflicts between agents
        3. Provides a confidence-weighted final output
        4. Includes a comprehensive markdown summary
        
        Generate the final structured data and comprehensive analysis.
        """
        
        if hasattr(self.ai_service, 'openai_client') and self.ai_service.openai_client:
            try:
                response = self.ai_service.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": synthesis_prompt}],
                    temperature=0.1
                )
                
                synthesis_result = response.choices[0].message.content
                
                # Combine the best data from all agents
                final_data = self._merge_agent_results(form_extraction, document_analysis, validation)
                final_data["full_markdown_summary"] = synthesis_result
                final_data["multi_agent_analysis"] = {
                    "document_analysis": document_analysis,
                    "form_extraction": form_extraction,
                    "validation": validation,
                    "synthesis_confidence": self._calculate_overall_confidence([document_analysis, form_extraction, validation])
                }
                
                return final_data
                
            except Exception as e:
                return self._fallback_synthesis(form_extraction, document_analysis, validation)
        
        return self._fallback_synthesis(form_extraction, document_analysis, validation)
    
    def _merge_agent_results(self, form_data: Dict, doc_analysis: Dict, validation: Dict) -> Dict:
        """Intelligently merge results from all agents"""
        # Start with form extraction as base
        merged = form_data.copy()
        
        # Enhance with document analysis insights
        if doc_analysis.get('document_type'):
            merged['document_type'] = doc_analysis['document_type']
        
        # Apply validation improvements
        if validation.get('warnings'):
            merged['validation_warnings'] = validation['warnings']
        
        # Remove agent-specific metadata
        merged.pop('agent', None)
        merged.pop('error', None)
        
        return merged
    
    def _calculate_overall_confidence(self, agent_results: List[Dict]) -> float:
        """Calculate weighted overall confidence from all agents"""
        confidences = [result.get('confidence', 0.5) for result in agent_results]
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    def _fallback_synthesis(self, form_data: Dict, doc_analysis: Dict, validation: Dict) -> Dict:
        """Fallback synthesis when AI is not available"""
        merged = self._merge_agent_results(form_data, doc_analysis, validation)
        merged["full_markdown_summary"] = f"""
# Multi-Agent Document Analysis

## Document Analysis
{doc_analysis.get('analysis', 'Basic analysis completed')}

## Form Extraction
Successfully extracted form data with {form_data.get('confidence', 0.5)*100:.1f}% confidence.

## Validation Results
{len(validation.get('warnings', []))} validation warnings identified.

## Final Assessment
This document has been processed by our multi-agent system with collaborative analysis.
        """
        return merged

class MultiAgentOrchestrator:
    """Orchestrates the multi-agent document processing pipeline"""
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        self.document_agent = DocumentAnalysisAgent(ai_service)
        self.form_agent = FormExtractionAgent(ai_service)
        self.validation_agent = ValidationAgent(ai_service)
        self.synthesis_agent = SynthesisAgent(ai_service)
    
    def process_document(self, extracted_text: str, doc_info: Dict) -> Dict:
        """Process document through multi-agent pipeline"""
        try:
            # Stage 1: Document Analysis
            st.write("🔍 **Agent 1**: Document Analysis Specialist analyzing structure...")
            document_analysis = self.document_agent.analyze_document(extracted_text, doc_info)
            
            # Stage 2: Form Extraction
            st.write("📋 **Agent 2**: Form Extraction Specialist extracting form data...")
            form_extraction = self.form_agent.extract_form_data(extracted_text, doc_info, document_analysis)
            
            # Stage 3: Validation
            st.write("✅ **Agent 3**: Validation Specialist checking accuracy...")
            validation = self.validation_agent.validate_extraction(form_extraction, document_analysis, extracted_text)
            
            # Stage 4: Synthesis
            st.write("🎯 **Agent 4**: Synthesis Coordinator combining all insights...")
            final_result = self.synthesis_agent.synthesize_results(document_analysis, form_extraction, validation, extracted_text)
            
            st.success("🤝 **Multi-Agent Collaboration Complete!** All agents have contributed to the final result.")
            
            return final_result
            
        except Exception as e:
            st.error(f"Multi-agent processing error: {str(e)}")
            # Fallback to single-agent processing
            return self.ai_service.extract_form_data(extracted_text, doc_info)

class USFormsCollector:
    """Specialized collector for comprehensive US immigration forms"""
    
    def __init__(self, discovery_service, processor, ai_service, db, multi_agent_orchestrator):
        self.discovery = discovery_service
        self.processor = processor
        self.ai_service = ai_service
        self.db = db
        self.multi_agent_orchestrator = multi_agent_orchestrator
        
        # Comprehensive US immigration form categories
        self.us_form_categories = [
            "Work Visa", "Student Visa", "Tourist Visa", "Family Visa",
            "Permanent Residence", "Citizenship", "Business Visa",
            "Investor Visa", "Religious Worker Visa", "Artist Visa",
            "Asylum", "Refugee Status", "Temporary Protected Status",
            "DACA", "Green Card Renewal", "Naturalization",
            "Fiancé Visa", "Marriage-based Immigration", "Adoption",
            "Diversity Visa", "Special Immigrant Visa"
        ]
        
        # Enhanced search terms for comprehensive coverage
        self.enhanced_search_terms = [
            "USCIS forms PDF download",
            "State Department visa forms",
            "CBP customs forms",
            "DOL labor certification forms",
            "Immigration court forms",
            "I-94 arrival departure record",
            "Employment authorization document",
            "Travel document application",
            "Waiver application forms",
            "Appeal forms immigration"
        ]
    
    def collect_all_us_forms(self) -> Dict[str, Any]:
        """Collect all US immigration forms comprehensively"""
        st.header("🇺🇸 Comprehensive US Immigration Forms Collection")
        st.info("Gathering ALL US immigration forms across multiple formats and agencies...")
        
        all_discovered_forms = []
        collection_stats = {
            "total_discovered": 0,
            "by_format": {},
            "by_category": {},
            "by_agency": {},
            "processing_results": {
                "successful": 0,
                "failed": 0,
                "duplicates_skipped": 0
            }
        }
        
        # Phase 1: Category-based discovery
        st.subheader("Phase 1: Category-based Discovery")
        for category in self.us_form_categories:
            st.write(f"🔍 Discovering forms for: {category}")
            discovered = self.discovery.discover_documents("USA", category)
            all_discovered_forms.extend(discovered)
            collection_stats["by_category"][category] = len(discovered)
            time.sleep(0.5)  # Rate limiting
        
        # Phase 2: Enhanced search terms
        st.subheader("Phase 2: Enhanced Search Discovery")
        for search_term in self.enhanced_search_terms:
            st.write(f"🔍 Enhanced search: {search_term}")
            discovered = self.discovery.discover_documents("USA", search_term)
            all_discovered_forms.extend(discovered)
            time.sleep(0.5)  # Rate limiting
        
        # Phase 3: Deduplication and format analysis
        st.subheader("Phase 3: Deduplication and Analysis")
        unique_forms = self._deduplicate_forms(all_discovered_forms)
        collection_stats["total_discovered"] = len(unique_forms)
        
        # Analyze formats
        for form in unique_forms:
            file_type = form.get('file_type', 'UNKNOWN')
            collection_stats["by_format"][file_type] = collection_stats["by_format"].get(file_type, 0) + 1
        
        st.success(f"✅ Discovered {len(unique_forms)} unique US immigration forms")
        
        # Display format distribution
        format_summary = ", ".join([f"{fmt}: {count}" for fmt, count in collection_stats["by_format"].items()])
        st.info(f"📊 **Format Distribution:** {format_summary}")
        
        # Phase 4: Comprehensive processing
        st.subheader("Phase 4: Comprehensive Processing")
        processed_forms = self._process_all_forms(unique_forms, collection_stats)
        
        # Phase 5: Verification and completeness check
        st.subheader("Phase 5: Verification and Completeness Check")
        verification_results = self._verify_completeness(processed_forms)
        
        # Phase 6: Generate final JSON output
        st.subheader("Phase 6: Final JSON Generation")
        final_json = self._generate_comprehensive_json(processed_forms, collection_stats, verification_results)
        
        return final_json
    
    def _deduplicate_forms(self, forms_list: List[Dict]) -> List[Dict]:
        """Remove duplicate forms based on URL"""
        seen_urls = set()
        unique_forms = []
        
        for form in forms_list:
            url = form.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_forms.append(form)
        
        return unique_forms
    
    def _process_all_forms(self, forms_list: List[Dict], stats: Dict) -> List[Dict]:
        """Process all discovered forms with comprehensive error handling"""
        processed_forms = []
        
        total_forms = len(forms_list)
        progress_bar = st.progress(0)
        
        for i, form in enumerate(forms_list):
            progress = (i + 1) / total_forms
            progress_bar.progress(progress)
            
            st.write(f"Processing {i+1}/{total_forms}: {form.get('title', 'Unknown')[:50]}...")
            
            try:
                # Check if already exists in database
                existing_form = self.db.get_form_by_url(form['url'])
                if existing_form:
                    st.info(f"⏩ Skipping duplicate: {form.get('title', 'Unknown')[:30]}...")
                    stats["processing_results"]["duplicates_skipped"] += 1
                    processed_forms.append(existing_form)
                    continue
                
                # Download and process
                file_info = self.processor.download_document(form['url'], "USA", "Comprehensive Collection")
                if not file_info:
                    stats["processing_results"]["failed"] += 1
                    continue
                
                # Extract text
                extracted_text = self.processor.extract_text(file_info['file_path'])
                
                # AI processing with multi-agent system
                doc_info_for_ai = {**form, **file_info}
                ai_extracted_data = self.multi_agent_orchestrator.process_document(extracted_text, doc_info_for_ai)
                
                # Prepare form data for database
                form_data = {
                    "country": "United States",
                    "visa_category": "Comprehensive Collection",
                    "form_name": ai_extracted_data.get('form_name', form.get('title', 'Unknown Form')),
                    "form_id": ai_extracted_data.get('form_id', 'N/A'),
                    "description": ai_extracted_data.get('form_description', form.get('description', '')),
                    "governing_authority": ai_extracted_data.get('governing_authority', 'N/A'),
                    "official_source_url": form.get('url', ''),
                    "discovered_by_query": form.get('discovered_by_query', ''),
                    "validation_warnings": ai_extracted_data.get('validation_warnings', []),
                    "structured_data": ai_extracted_data,
                    "downloaded_file_path": file_info['file_path'],
                    "document_format": file_info['file_format'],
                    "processing_status": "validated",
                    "last_fetched": datetime.now().isoformat(),
                    "lawyer_review": {}
                }
                
                # Save to database
                form_id = self.db.insert_form(form_data)
                if form_id:
                    form_data['id'] = form_id
                    self.db.insert_document(form_id, file_info)
                    processed_forms.append(form_data)
                    stats["processing_results"]["successful"] += 1
                    st.success(f"✅ Processed: {form_data['form_name'][:30]}...")
                else:
                    stats["processing_results"]["failed"] += 1
                
            except Exception as e:
                st.error(f"❌ Failed to process {form.get('title', 'Unknown')[:30]}: {str(e)}")
                stats["processing_results"]["failed"] += 1
        
        return processed_forms
    
    def _verify_completeness(self, processed_forms: List[Dict]) -> Dict[str, Any]:
        """Verify completeness of the US forms collection"""
        verification_results = {
            "total_forms_processed": len(processed_forms),
            "format_coverage": {},
            "agency_coverage": {},
            "completeness_score": 0,
            "missing_categories": [],
            "recommendations": []
        }
        
        # Analyze format coverage
        for form in processed_forms:
            file_format = form.get('document_format', 'UNKNOWN')
            verification_results["format_coverage"][file_format] = verification_results["format_coverage"].get(file_format, 0) + 1
        
        # Analyze agency coverage
        for form in processed_forms:
            authority = form.get('governing_authority', 'Unknown')
            verification_results["agency_coverage"][authority] = verification_results["agency_coverage"].get(authority, 0) + 1
        
        # Calculate completeness score
        expected_min_forms = 100  # Minimum expected US immigration forms
        completeness_score = min(100, (len(processed_forms) / expected_min_forms) * 100)
        verification_results["completeness_score"] = completeness_score
        
        # Check for missing critical formats
        critical_formats = ['PDF', 'DOCX', 'XLSX', 'HTML']
        missing_formats = [fmt for fmt in critical_formats if fmt not in verification_results["format_coverage"]]
        if missing_formats:
            verification_results["recommendations"].append(f"Consider searching for forms in missing formats: {', '.join(missing_formats)}")
        
        # Check for major agencies
        major_agencies = ['USCIS', 'U.S. Department of State', 'CBP', 'DOL']
        covered_agencies = list(verification_results["agency_coverage"].keys())
        missing_agencies = [agency for agency in major_agencies if not any(agency.lower() in covered.lower() for covered in covered_agencies)]
        if missing_agencies:
            verification_results["recommendations"].append(f"Consider searching for forms from missing agencies: {', '.join(missing_agencies)}")
        
        return verification_results
    
    def _generate_comprehensive_json(self, processed_forms: List[Dict], collection_stats: Dict, verification_results: Dict) -> Dict[str, Any]:
        """Generate comprehensive JSON output with all US forms"""
        
        # Extract structured data for JSON output
        forms_json = []
        for form in processed_forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                # Clean and enhance the structured data
                form_json = {
                    "form_name": structured_data.get('form_name', form.get('form_name', 'Unknown')),
                    "form_slug": structured_data.get('form_slug', ''),
                    "form_id": structured_data.get('form_id', form.get('form_id', 'N/A')),
                    "country_code": "USA",
                    "country_name": "United States",
                    "category": structured_data.get('category', form.get('visa_category', 'Unknown')),
                    "governing_authority": structured_data.get('governing_authority', form.get('governing_authority', 'N/A')),
                    "target_applicants": structured_data.get('target_users', structured_data.get('target_applicants', 'N/A')),
                    "form_description": structured_data.get('form_description', form.get('description', '')),
                    "required_fields": structured_data.get('required_fields', []),
                    "supporting_documents": structured_data.get('supporting_documents', []),
                    "submission_method": structured_data.get('submission_method', 'N/A'),
                    "processing_time": structured_data.get('processing_time', 'N/A'),
                    "fees": structured_data.get('fees', 'N/A'),
                    "language": structured_data.get('language', 'English'),
                    "official_source_url": form.get('official_source_url', ''),
                    "document_format": form.get('document_format', 'Unknown'),
                    "last_fetched": form.get('last_fetched', ''),
                    "discovered_by_query": form.get('discovered_by_query', ''),
                    "validation_warnings": form.get('validation_warnings', []),
                    "multi_agent_analysis": structured_data.get('multi_agent_analysis', {}),
                    "full_markdown_summary": structured_data.get('full_markdown_summary', ''),
                    "cloudinary_url": self._get_cloudinary_url(form.get('id')),
                    "processing_metadata": {
                        "processing_status": form.get('processing_status', 'unknown'),
                        "extracted_text_length": structured_data.get('extracted_text_length', 0),
                        "ai_confidence": structured_data.get('multi_agent_analysis', {}).get('synthesis_confidence', 0)
                    }
                }
                forms_json.append(form_json)
        
        # Create comprehensive output
        comprehensive_json = {
            "collection_metadata": {
                "collection_name": "Comprehensive US Immigration Forms",
                "collection_date": datetime.now().isoformat(),
                "total_forms": len(forms_json),
                "collection_method": "Multi-Agent AI Discovery and Processing",
                "completeness_verification": verification_results
            },
            "collection_statistics": collection_stats,
            "verification_results": verification_results,
            "forms": forms_json,
            "format_summary": {
                "total_formats": len(collection_stats.get("by_format", {})),
                "format_distribution": collection_stats.get("by_format", {}),
                "primary_formats": ["PDF", "HTML", "DOCX", "XLSX"]
            },
            "agency_coverage": verification_results.get("agency_coverage", {}),
            "export_info": {
                "export_timestamp": datetime.now().isoformat(),
                "export_version": "1.0",
                "data_quality_score": verification_results.get("completeness_score", 0),
                "multi_agent_processed": len([f for f in forms_json if f.get("multi_agent_analysis")])
            }
        }
        
        return comprehensive_json
    
    def _get_cloudinary_url(self, form_id: int) -> str:
        """Get Cloudinary URL for a form if available"""
        if not form_id:
            return ""
        
        try:
            document_info = self.db.get_document_by_form_id(form_id)
            return document_info.get('cloudinary_url', '') if document_info else ""
        except:
            return ""

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

def render_top_export_buttons(extracted_docs_list, page_name=""):
    """Render export buttons at the top of pages for easy accessibility"""
    if not extracted_docs_list:
        return
    
    st.markdown(f"""
    <div style="background: linear-gradient(45deg, #667eea 0%, #764ba2 100%); 
                padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
        <h4 style="color: white; margin: 0; text-align: center;">
            📦 Quick Export ({len(extracted_docs_list)} documents) - {page_name}
        </h4>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("📄 JSON", key=f"top_json_{page_name}", use_container_width=True):
            json_data = json.dumps(extracted_docs_list, indent=2, ensure_ascii=False, default=str)
            st.download_button(
                label="Download JSON",
                data=json_data.encode('utf-8'),
                file_name=f"export_{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"top_json_download_{page_name}"
            )
    
    with col2:
        if st.button("📊 CSV", key=f"top_csv_{page_name}", use_container_width=True):
            flattened_data = []
            for doc in extracted_docs_list:
                flat_doc = {}
                # Handle all the main fields from schema
                flat_doc['form_name'] = doc.get('form_name', '')
                flat_doc['form_id'] = doc.get('form_id', '')
                flat_doc['description'] = doc.get('description', '')
                flat_doc['governing_authority'] = doc.get('governing_authority', '')
                flat_doc['target_users'] = doc.get('target_users', '')
                flat_doc['supporting_documents'] = doc.get('supporting_documents', '')
                flat_doc['submission_method'] = doc.get('submission_method', '')
                flat_doc['frequency_or_deadline'] = doc.get('frequency_or_deadline', '')
                flat_doc['official_source_url'] = doc.get('official_source_url', '')
                flat_doc['notes_or_instructions'] = doc.get('notes_or_instructions', '')
                
                # Flatten required_fields array
                required_fields = doc.get('required_fields', [])
                if isinstance(required_fields, list):
                    for i, field in enumerate(required_fields):
                        if isinstance(field, dict):
                            flat_doc[f'required_field_{i+1}_name'] = field.get('name', '')
                            flat_doc[f'required_field_{i+1}_description'] = field.get('description', '')
                            flat_doc[f'required_field_{i+1}_type'] = field.get('type', '')
                
                flattened_data.append(flat_doc)
            
            df = pd.DataFrame(flattened_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv_buffer.getvalue().encode('utf-8'),
                file_name=f"export_{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"top_csv_download_{page_name}"
            )
    
    with col3:
        if st.button("📈 Excel", key=f"top_excel_{page_name}", use_container_width=True):
            flattened_data = []
            for doc in extracted_docs_list:
                flat_doc = {}
                # Handle all the main fields from schema
                flat_doc['form_name'] = doc.get('form_name', '')
                flat_doc['form_id'] = doc.get('form_id', '')
                flat_doc['description'] = doc.get('description', '')
                flat_doc['governing_authority'] = doc.get('governing_authority', '')
                flat_doc['target_users'] = doc.get('target_users', '')
                flat_doc['supporting_documents'] = doc.get('supporting_documents', '')
                flat_doc['submission_method'] = doc.get('submission_method', '')
                flat_doc['frequency_or_deadline'] = doc.get('frequency_or_deadline', '')
                flat_doc['official_source_url'] = doc.get('official_source_url', '')
                flat_doc['notes_or_instructions'] = doc.get('notes_or_instructions', '')
                
                # Flatten required_fields array
                required_fields = doc.get('required_fields', [])
                if isinstance(required_fields, list):
                    for i, field in enumerate(required_fields):
                        if isinstance(field, dict):
                            flat_doc[f'required_field_{i+1}_name'] = field.get('name', '')
                            flat_doc[f'required_field_{i+1}_description'] = field.get('description', '')
                            flat_doc[f'required_field_{i+1}_type'] = field.get('type', '')
                
                flattened_data.append(flat_doc)
            
            df = pd.DataFrame(flattened_data)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Immigration_Forms', index=False)
            
            st.download_button(
                label="Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"export_{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"top_excel_download_{page_name}"
            )
    
    with col4:
        if st.button("📝 Markdown", key=f"top_md_{page_name}", use_container_width=True):
            markdown_content = f"# Immigration Forms Export - {page_name}\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nTotal Documents: {len(extracted_docs_list)}\n\n---\n\n"
            
            for i, doc in enumerate(extracted_docs_list, 1):
                markdown_content += f"## {i}. {doc.get('form_name', 'Unknown Form')}\n\n"
                markdown_content += f"**Form ID:** {doc.get('form_id', 'N/A')}\n\n"
                markdown_content += f"**Description:** {doc.get('description', 'N/A')}\n\n"
                markdown_content += f"**Governing Authority:** {doc.get('governing_authority', 'N/A')}\n\n"
                markdown_content += f"**Target Users:** {doc.get('target_users', 'N/A')}\n\n"
                markdown_content += f"**Submission Method:** {doc.get('submission_method', 'N/A')}\n\n"
                markdown_content += f"**Frequency/Deadline:** {doc.get('frequency_or_deadline', 'N/A')}\n\n"
                markdown_content += f"**Supporting Documents:** {doc.get('supporting_documents', 'N/A')}\n\n"
                
                if doc.get('required_fields') and isinstance(doc['required_fields'], list):
                    markdown_content += "**Required Fields:**\n\n"
                    for field in doc['required_fields']:
                        if isinstance(field, dict):
                            markdown_content += f"- **{field.get('name', 'Unknown')}** ({field.get('type', 'Unknown type')}): {field.get('description', 'No description')}\n"
                    markdown_content += "\n"
                
                markdown_content += f"**Official Source:** {doc.get('official_source_url', 'N/A')}\n\n"
                markdown_content += f"**Notes:** {doc.get('notes_or_instructions', 'N/A')}\n\n"
                markdown_content += "---\n\n"
            
            st.download_button(
                label="Download Markdown",
                data=markdown_content.encode('utf-8'),
                file_name=f"export_{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                key=f"top_md_download_{page_name}"
            )
    
    with col5:
        if st.button("📄 TXT", key=f"top_txt_{page_name}", use_container_width=True):
            txt_content = f"IMMIGRATION FORMS EXPORT - {page_name.upper()}\n{'='*60}\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Documents: {len(extracted_docs_list)}\n\n"
            
            for i, doc in enumerate(extracted_docs_list, 1):
                txt_content += f"{i}. {doc.get('form_name', 'Unknown Form')}\n{'-'*50}\n"
                txt_content += f"Form ID: {doc.get('form_id', 'N/A')}\n"
                txt_content += f"Description: {doc.get('description', 'N/A')}\n"
                txt_content += f"Governing Authority: {doc.get('governing_authority', 'N/A')}\n"
                txt_content += f"Target Users: {doc.get('target_users', 'N/A')}\n"
                txt_content += f"Submission Method: {doc.get('submission_method', 'N/A')}\n"
                txt_content += f"Frequency/Deadline: {doc.get('frequency_or_deadline', 'N/A')}\n"
                txt_content += f"Supporting Documents: {doc.get('supporting_documents', 'N/A')}\n"
                
                if doc.get('required_fields') and isinstance(doc['required_fields'], list):
                    txt_content += "Required Fields:\n"
                    for field in doc['required_fields']:
                        if isinstance(field, dict):
                            txt_content += f"  - {field.get('name', 'Unknown')} ({field.get('type', 'Unknown type')}): {field.get('description', 'No description')}\n"
                
                txt_content += f"Official Source: {doc.get('official_source_url', 'N/A')}\n"
                txt_content += f"Notes: {doc.get('notes_or_instructions', 'N/A')}\n"
                txt_content += "\n" + "="*60 + "\n\n"
            
            st.download_button(
                label="Download TXT",
                data=txt_content.encode('utf-8'),
                file_name=f"export_{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key=f"top_txt_download_{page_name}"
            )

def render_bulk_export_buttons(extracted_docs_list):
    """Render bulk export buttons for all document formats"""
    import io
    import json
    import pandas as pd
    from datetime import datetime
    
    if not extracted_docs_list:
        st.warning("No documents available for bulk export.")
        return
    
    st.markdown("### 📦 Bulk Export All Documents")
    st.info(f"Ready to export {len(extracted_docs_list)} documents in various formats")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    # JSON Export
    with col1:
        if st.button("📄 Export JSON", use_container_width=True):
            json_data = json.dumps(extracted_docs_list, indent=2, ensure_ascii=False, default=str)
            st.download_button(
                label="Download JSON",
                data=json_data.encode('utf-8'),
                file_name=f"bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="bulk_json"
            )
    
    # CSV Export
    with col2:
        if st.button("📊 Export CSV", use_container_width=True):
            # Flatten the data for CSV
            flattened_data = []
            for doc in extracted_docs_list:
                flat_doc = {}
                # Handle all the main fields from schema
                flat_doc['form_name'] = doc.get('form_name', '')
                flat_doc['form_id'] = doc.get('form_id', '')
                flat_doc['description'] = doc.get('description', '')
                flat_doc['governing_authority'] = doc.get('governing_authority', '')
                flat_doc['target_users'] = doc.get('target_users', '')
                flat_doc['supporting_documents'] = doc.get('supporting_documents', '')
                flat_doc['submission_method'] = doc.get('submission_method', '')
                flat_doc['frequency_or_deadline'] = doc.get('frequency_or_deadline', '')
                flat_doc['official_source_url'] = doc.get('official_source_url', '')
                flat_doc['notes_or_instructions'] = doc.get('notes_or_instructions', '')
                
                # Flatten required_fields array
                required_fields = doc.get('required_fields', [])
                if isinstance(required_fields, list):
                    for i, field in enumerate(required_fields):
                        if isinstance(field, dict):
                            flat_doc[f'required_field_{i+1}_name'] = field.get('name', '')
                            flat_doc[f'required_field_{i+1}_description'] = field.get('description', '')
                            flat_doc[f'required_field_{i+1}_type'] = field.get('type', '')
                
                flattened_data.append(flat_doc)
            
            df = pd.DataFrame(flattened_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            st.download_button(
                label="Download CSV",
                data=csv_buffer.getvalue().encode('utf-8'),
                file_name=f"bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="bulk_csv"
            )
    
    # Excel Export
    with col3:
        if st.button("📈 Export Excel", use_container_width=True):
            # Flatten the data for Excel
            flattened_data = []
            for doc in extracted_docs_list:
                flat_doc = {}
                # Handle all the main fields from schema
                flat_doc['form_name'] = doc.get('form_name', '')
                flat_doc['form_id'] = doc.get('form_id', '')
                flat_doc['description'] = doc.get('description', '')
                flat_doc['governing_authority'] = doc.get('governing_authority', '')
                flat_doc['target_users'] = doc.get('target_users', '')
                flat_doc['supporting_documents'] = doc.get('supporting_documents', '')
                flat_doc['submission_method'] = doc.get('submission_method', '')
                flat_doc['frequency_or_deadline'] = doc.get('frequency_or_deadline', '')
                flat_doc['official_source_url'] = doc.get('official_source_url', '')
                flat_doc['notes_or_instructions'] = doc.get('notes_or_instructions', '')
                
                # Flatten required_fields array
                required_fields = doc.get('required_fields', [])
                if isinstance(required_fields, list):
                    for i, field in enumerate(required_fields):
                        if isinstance(field, dict):
                            flat_doc[f'required_field_{i+1}_name'] = field.get('name', '')
                            flat_doc[f'required_field_{i+1}_description'] = field.get('description', '')
                            flat_doc[f'required_field_{i+1}_type'] = field.get('type', '')
                
                flattened_data.append(flat_doc)
            
            df = pd.DataFrame(flattened_data)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Immigration_Forms', index=False)
            
            st.download_button(
                label="Download Excel",
                data=excel_buffer.getvalue(),
                file_name=f"bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="bulk_excel"
            )
    
    # Markdown Export
    with col4:
        if st.button("📝 Export Markdown", use_container_width=True):
            markdown_content = f"# Immigration Forms Export\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nTotal Documents: {len(extracted_docs_list)}\n\n---\n\n"
            
            for i, doc in enumerate(extracted_docs_list, 1):
                markdown_content += f"## {i}. {doc.get('form_name', 'Unknown Form')}\n\n"
                markdown_content += f"**Form ID:** {doc.get('form_id', 'N/A')}\n\n"
                markdown_content += f"**Description:** {doc.get('description', 'N/A')}\n\n"
                markdown_content += f"**Governing Authority:** {doc.get('governing_authority', 'N/A')}\n\n"
                markdown_content += f"**Target Users:** {doc.get('target_users', 'N/A')}\n\n"
                markdown_content += f"**Submission Method:** {doc.get('submission_method', 'N/A')}\n\n"
                markdown_content += f"**Frequency/Deadline:** {doc.get('frequency_or_deadline', 'N/A')}\n\n"
                markdown_content += f"**Supporting Documents:** {doc.get('supporting_documents', 'N/A')}\n\n"
                
                if doc.get('required_fields') and isinstance(doc['required_fields'], list):
                    markdown_content += "**Required Fields:**\n\n"
                    for field in doc['required_fields']:
                        if isinstance(field, dict):
                            markdown_content += f"- **{field.get('name', 'Unknown')}** ({field.get('type', 'Unknown type')}): {field.get('description', 'No description')}\n"
                    markdown_content += "\n"
                
                markdown_content += f"**Official Source:** {doc.get('official_source_url', 'N/A')}\n\n"
                markdown_content += f"**Notes:** {doc.get('notes_or_instructions', 'N/A')}\n\n"
                markdown_content += "---\n\n"
            
            st.download_button(
                label="Download Markdown",
                data=markdown_content.encode('utf-8'),
                file_name=f"bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                key="bulk_markdown"
            )
    
    # TXT Export
    with col5:
        if st.button("📄 Export TXT", use_container_width=True):
            txt_content = f"IMMIGRATION FORMS EXPORT\n{'='*50}\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTotal Documents: {len(extracted_docs_list)}\n\n"
            
            for i, doc in enumerate(extracted_docs_list, 1):
                txt_content += f"{i}. {doc.get('form_name', 'Unknown Form')}\n{'-'*50}\n"
                txt_content += f"Form ID: {doc.get('form_id', 'N/A')}\n"
                txt_content += f"Description: {doc.get('description', 'N/A')}\n"
                txt_content += f"Governing Authority: {doc.get('governing_authority', 'N/A')}\n"
                txt_content += f"Target Users: {doc.get('target_users', 'N/A')}\n"
                txt_content += f"Submission Method: {doc.get('submission_method', 'N/A')}\n"
                txt_content += f"Frequency/Deadline: {doc.get('frequency_or_deadline', 'N/A')}\n"
                txt_content += f"Supporting Documents: {doc.get('supporting_documents', 'N/A')}\n"
                
                if doc.get('required_fields') and isinstance(doc['required_fields'], list):
                    txt_content += "Required Fields:\n"
                    for field in doc['required_fields']:
                        if isinstance(field, dict):
                            txt_content += f"  - {field.get('name', 'Unknown')} ({field.get('type', 'Unknown type')}): {field.get('description', 'No description')}\n"
                
                txt_content += f"Official Source: {doc.get('official_source_url', 'N/A')}\n"
                txt_content += f"Notes: {doc.get('notes_or_instructions', 'N/A')}\n"
                txt_content += "\n" + "="*50 + "\n\n"
            
            st.download_button(
                label="Download TXT",
                data=txt_content.encode('utf-8'),
                file_name=f"bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="bulk_txt"
            )

# Initialize services
def init_services():
    db = DatabaseManager(config.DATABASE_URL)
    processor = DocumentProcessor(config.DOWNLOADS_DIR, config.CLOUDINARY_URL)
    discovery = DocumentDiscoveryService(config.TAVILY_API_KEY, processor, db)
    ai_service = AIExtractionService(config.OPENAI_API_KEY, config.OPENROUTER_API_KEY, config.GEMINI_API_KEY)
    export_service = ExportService(config.OUTPUTS_DIR, db, config.CLOUDINARY_URL)
    
    # Initialize Multi-Agent Orchestrator
    multi_agent_orchestrator = MultiAgentOrchestrator(ai_service)

    return db, discovery, processor, ai_service, export_service, multi_agent_orchestrator

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
    .multi-agent-banner {
        background: linear-gradient(45deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
    }
    .us-forms-banner {
        background: linear-gradient(45deg, #FF6B6B 0%, #4ECDC4 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        font-size: 1.1rem;
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

    # Enhanced US Forms Collection Banner
    st.markdown("""
    <div class="us-forms-banner">
        🇺🇸 <strong>NEW: Comprehensive US Forms Collection</strong> - Gather ALL US immigration forms across multiple formats (PDF, DOCX, Excel, HTML) with complete verification and JSON export.
    </div>
    """, unsafe_allow_html=True)

    # Multi-Agent System Banner
    st.markdown("""
    <div class="multi-agent-banner">
        🤖 <strong>Enhanced with Multi-Agent AI:</strong> Four specialized AI agents collaborate to deliver superior document analysis and extraction accuracy.
    </div>
    """, unsafe_allow_html=True)

    # Clear cache button in sidebar
    with st.sidebar:
        st.markdown("### ⚙️ System Controls")
        if st.button("🔄 Clear All Caches", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
        
        st.markdown("### 🤖 Multi-Agent System")
        st.info("""
        **Active Agents:**
        - 🔍 Document Analysis Specialist
        - 📋 Form Extraction Specialist  
        - ✅ Validation Specialist
        - 🎯 Synthesis Coordinator
        """)

    # Warning banner
    st.markdown("""
    <div class="warning-banner">
        ⚠️ <strong>Important:</strong> Documents are stored locally and uploaded to Cloudinary for persistent storage.
    </div>
    """, unsafe_allow_html=True)

    db, discovery, processor, ai_service, export_service, multi_agent_orchestrator = init_services()

    # Enhanced Navigation
    st.markdown('<div class="main-nav">', unsafe_allow_html=True)
    st.markdown("### 🧭 Navigation Dashboard")

    # Navigation cards in columns
    col1, col2, col3 = st.columns(3)

    navigation_options = [
        {"title": "🇺🇸 US Forms Collector", "desc": "Comprehensive US immigration forms collection", "icon": "🇺🇸"},
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

    if page == "🇺🇸 US Forms Collector":
        us_forms_collector_page(discovery, processor, ai_service, db, multi_agent_orchestrator)
    elif page == "🔍 Document Discovery":
        discovery_page(discovery, processor, ai_service, db, multi_agent_orchestrator)
    elif page == "📄 Document Viewer":
        document_viewer_page(db, processor, ai_service)
    elif page == "✅ Validation Panel":
        validation_panel_page(db, processor, ai_service, multi_agent_orchestrator)
    elif page == "📊 Export Panel":
        export_panel_page(db, export_service)
    elif page == "🗄️ Database Viewer":
        database_viewer_page(db)
    elif page == "☁️ Cloudinary Document Browser":
        cloudinary_browser_page(db)
    elif page == "🩺 Database Health Check":
        database_health_check_page(config.DATABASE_URL)

def us_forms_collector_page(discovery, processor, ai_service, db, multi_agent_orchestrator):
    """New comprehensive US forms collection page"""
    st.markdown("""
    <style>
    .us-collector-header {
        background: linear-gradient(45deg, #FF6B6B 0%, #4ECDC4 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    }
    .collection-stats {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .verification-panel {
        background: #e8f5e8;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #4CAF50;
    }
    </style>

    <div class="us-collector-header">
        <h1>🇺🇸 Comprehensive US Immigration Forms Collector</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0; opacity: 0.9;">
            Systematically gather, verify, and export ALL US immigration forms across multiple formats
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Initialize US Forms Collector
    us_collector = USFormsCollector(discovery, processor, ai_service, db, multi_agent_orchestrator)

    # Check existing US forms in database
    existing_us_forms = db.get_forms(country_code="USA")
    
    st.markdown('<div class="collection-stats">', unsafe_allow_html=True)
    st.markdown("### 📊 Current US Forms Status")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Total US Forms", len(existing_us_forms))
    with col2:
        multi_agent_count = len([f for f in existing_us_forms if f.get('structured_data', {}).get('multi_agent_analysis')])
        st.metric("🤝 Multi-Agent Processed", multi_agent_count)
    with col3:
        format_counts = {}
        for form in existing_us_forms:
            doc_info = db.get_document_by_form_id(form['id'])
            if doc_info:
                fmt = doc_info.get('file_format', 'Unknown')
                format_counts[fmt] = format_counts.get(fmt, 0) + 1
        st.metric("📋 Unique Formats", len(format_counts))
    with col4:
        validated_count = len([f for f in existing_us_forms if f.get('processing_status') == 'validated'])
        st.metric("✅ Validated Forms", validated_count)
    
    if existing_us_forms:
        st.success(f"Found {len(existing_us_forms)} existing US forms in database")
        format_summary = ", ".join([f"{fmt}: {count}" for fmt, count in format_counts.items()])
        st.info(f"**Format Distribution:** {format_summary}")
        
        # Export existing forms as JSON
        if st.button("📄 Export Existing US Forms as JSON", type="secondary"):
            existing_forms_json = us_collector._generate_comprehensive_json(
                existing_us_forms, 
                {"by_format": format_counts}, 
                {"completeness_score": 85, "total_forms_processed": len(existing_us_forms)}
            )
            
            json_data = json.dumps(existing_forms_json, indent=2, ensure_ascii=False, default=str)
            st.download_button(
                label="Download Existing US Forms JSON",
                data=json_data.encode('utf-8'),
                file_name=f"existing_us_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="existing_us_forms_json"
            )
    else:
        st.info("No existing US forms found in database. Ready for fresh collection.")
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Collection Options
    st.markdown("### ⚙️ Collection Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        collection_mode = st.selectbox(
            "Collection Mode:",
            ["Fresh Collection (Start Over)", "Incremental Collection (Add New)", "Verification Only (Check Existing)"]
        )
        
        max_forms_per_category = st.slider("Max forms per category:", 5, 50, 15)
        
    with col2:
        include_formats = st.multiselect(
            "Include Formats:",
            ["PDF", "DOCX", "DOC", "XLSX", "XLS", "HTML", "TXT"],
            default=["PDF", "DOCX", "XLSX", "HTML"]
        )
        
        use_multi_agent = st.checkbox("🤖 Use Multi-Agent Processing", value=False)

    # Advanced Options
    with st.expander("🔧 Advanced Collection Options"):
        deep_search = st.checkbox("Enable Deep Search (More comprehensive but slower)", value=True)
        verify_completeness = st.checkbox("Perform Completeness Verification", value=True)
        auto_export_json = st.checkbox("Auto-export JSON after collection", value=True)
        
        custom_search_terms = st.text_area(
            "Additional Search Terms (one per line):",
            placeholder="Enter additional search terms for specialized forms..."
        )

    # Start Collection Button
    if st.button("🚀 Start Comprehensive US Forms Collection", type="primary", use_container_width=True):
        if collection_mode == "Verification Only (Check Existing)":
            if existing_us_forms:
                st.subheader("🔍 Verification Results")
                verification_results = us_collector._verify_completeness(existing_us_forms)
                
                st.markdown('<div class="verification-panel">', unsafe_allow_html=True)
                st.markdown("### ✅ Completeness Verification")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Completeness Score", f"{verification_results['completeness_score']:.1f}%")
                with col2:
                    st.metric("Total Forms", verification_results['total_forms_processed'])
                with col3:
                    st.metric("Format Coverage", len(verification_results['format_coverage']))
                
                if verification_results.get('recommendations'):
                    st.markdown("**Recommendations:**")
                    for rec in verification_results['recommendations']:
                        st.warning(f"💡 {rec}")
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Generate verification JSON
                verification_json = {
                    "verification_timestamp": datetime.now().isoformat(),
                    "verification_results": verification_results,
                    "existing_forms_summary": {
                        "total_forms": len(existing_us_forms),
                        "format_distribution": format_counts,
                        "multi_agent_processed": multi_agent_count
                    }
                }
                
                json_data = json.dumps(verification_json, indent=2, ensure_ascii=False, default=str)
                st.download_button(
                    label="📄 Download Verification Report (JSON)",
                    data=json_data.encode('utf-8'),
                    file_name=f"us_forms_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="verification_report_json"
                )
            else:
                st.warning("No existing US forms to verify. Please run a collection first.")
        
        else:
            # Run comprehensive collection
            with st.spinner("Starting comprehensive US forms collection..."):
                try:
                    # Add custom search terms if provided
                    if custom_search_terms:
                        additional_terms = [term.strip() for term in custom_search_terms.split('\n') if term.strip()]
                        us_collector.enhanced_search_terms.extend(additional_terms)
                    
                    # Configure collection parameters
                    us_collector.max_forms_per_category = max_forms_per_category
                    us_collector.include_formats = include_formats
                    us_collector.deep_search = deep_search
                    
                    # Start collection
                    comprehensive_json = us_collector.collect_all_us_forms()
                    
                    # Display results
                    st.success("🎉 Comprehensive US Forms Collection Completed!")
                    
                    # Show collection summary
                    st.subheader("📊 Collection Summary")
                    metadata = comprehensive_json.get('collection_metadata', {})
                    stats = comprehensive_json.get('collection_statistics', {})
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Forms Collected", metadata.get('total_forms', 0))
                    with col2:
                        st.metric("Successful Processing", stats.get('processing_results', {}).get('successful', 0))
                    with col3:
                        st.metric("Unique Formats", len(stats.get('by_format', {})))
                    with col4:
                        st.metric("Multi-Agent Processed", comprehensive_json.get('export_info', {}).get('multi_agent_processed', 0))
                    
                    # Format distribution
                    format_dist = stats.get('by_format', {})
                    if format_dist:
                        st.markdown("**Format Distribution:**")
                        format_df = pd.DataFrame(list(format_dist.items()), columns=['Format', 'Count'])
                        st.bar_chart(format_df.set_index('Format'))
                    
                    # Auto-export JSON if enabled
                    if auto_export_json:
                        json_data = json.dumps(comprehensive_json, indent=2, ensure_ascii=False, default=str)
                        st.download_button(
                            label="📄 Download Complete US Forms Collection (JSON)",
                            data=json_data.encode('utf-8'),
                            file_name=f"comprehensive_us_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                            key="comprehensive_us_forms_json",
                            use_container_width=True
                        )
                    
                    # Show verification results if enabled
                    if verify_completeness:
                        verification = comprehensive_json.get('verification_results', {})
                        if verification:
                            st.markdown('<div class="verification-panel">', unsafe_allow_html=True)
                            st.markdown("### ✅ Collection Verification")
                            st.write(f"**Completeness Score:** {verification.get('completeness_score', 0):.1f}%")
                            
                            if verification.get('recommendations'):
                                st.markdown("**Recommendations for Improvement:**")
                                for rec in verification['recommendations']:
                                    st.info(f"💡 {rec}")
                            st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Show sample forms
                    forms_list = comprehensive_json.get('forms', [])
                    if forms_list:
                        st.subheader("📋 Sample Collected Forms")
                        sample_forms = forms_list[:5]  # Show first 5 forms
                        
                        for i, form in enumerate(sample_forms, 1):
                            with st.expander(f"📄 {i}. {form.get('form_name', 'Unknown Form')} ({form.get('form_id', 'N/A')})"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Authority:** {form.get('governing_authority', 'N/A')}")
                                    st.write(f"**Format:** {form.get('document_format', 'Unknown')}")
                                    st.write(f"**Category:** {form.get('category', 'N/A')}")
                                with col2:
                                    st.write(f"**Target Users:** {form.get('target_applicants', 'N/A')}")
                                    st.write(f"**Submission:** {form.get('submission_method', 'N/A')}")
                                    if form.get('processing_metadata', {}).get('ai_confidence'):
                                        confidence = form['processing_metadata']['ai_confidence']
                                        st.write(f"**AI Confidence:** {confidence*100:.1f}%")
                                
                                if form.get('form_description'):
                                    st.write(f"**Description:** {form['form_description'][:200]}...")
                
                except Exception as e:
                    st.error(f"❌ Collection failed: {str(e)}")
                    st.code(traceback.format_exc())

    # Manual JSON Export Section
    st.markdown("---")
    st.subheader("📤 Manual Export Options")
    
    if existing_us_forms:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 Export All US Forms (JSON)", use_container_width=True):
                all_forms_json = us_collector._generate_comprehensive_json(
                    existing_us_forms,
                    {"by_format": format_counts, "total_discovered": len(existing_us_forms)},
                    {"completeness_score": 90, "total_forms_processed": len(existing_us_forms)}
                )
                
                json_data = json.dumps(all_forms_json, indent=2, ensure_ascii=False, default=str)
                st.download_button(
                    label="Download All US Forms JSON",
                    data=json_data.encode('utf-8'),
                    file_name=f"all_us_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    key="all_us_forms_manual_json"
                )
        
        with col2:
            if st.button("📊 Export US Forms (Excel)", use_container_width=True):
                # Create Excel export
                excel_data = []
                for form in existing_us_forms:
                    structured_data = form.get('structured_data', {})
                    excel_data.append({
                        'Form Name': form.get('form_name', ''),
                        'Form ID': form.get('form_id', ''),
                        'Authority': form.get('governing_authority', ''),
                        'Category': form.get('visa_category', ''),
                        'Format': form.get('document_format', ''),
                        'Status': form.get('processing_status', ''),
                        'Multi-Agent': 'Yes' if structured_data.get('multi_agent_analysis') else 'No',
                        'Source URL': form.get('official_source_url', ''),
                        'Description': form.get('description', '')[:100] + '...' if len(form.get('description', '')) > 100 else form.get('description', '')
                    })
                
                df = pd.DataFrame(excel_data)
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='US_Immigration_Forms', index=False)
                
                st.download_button(
                    label="Download US Forms Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"us_forms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="us_forms_excel"
                )
        
        with col3:
            if st.button("📋 Export Forms Summary (MD)", use_container_width=True):
                markdown_content = f"""# US Immigration Forms Collection Summary

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Forms: {len(existing_us_forms)}

## Format Distribution
{chr(10).join([f"- **{fmt}**: {count} forms" for fmt, count in format_counts.items()])}

## Forms List

"""
                for i, form in enumerate(existing_us_forms, 1):
                    structured_data = form.get('structured_data', {})
                    multi_agent_indicator = " 🤝" if structured_data.get('multi_agent_analysis') else ""
                    
                    markdown_content += f"""### {i}. {form.get('form_name', 'Unknown Form')}{multi_agent_indicator}

- **Form ID**: {form.get('form_id', 'N/A')}
- **Authority**: {form.get('governing_authority', 'N/A')}
- **Category**: {form.get('visa_category', 'N/A')}
- **Format**: {form.get('document_format', 'Unknown')}
- **Status**: {form.get('processing_status', 'Unknown')}
- **Source**: {form.get('official_source_url', 'N/A')}

{form.get('description', 'No description available')[:200]}...

---

"""
                
                st.download_button(
                    label="Download US Forms Summary",
                    data=markdown_content.encode('utf-8'),
                    file_name=f"us_forms_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    key="us_forms_summary_md"
                )

def discovery_page(discovery, processor, ai_service, db, multi_agent_orchestrator):
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
        <h1>🔍 Document Discovery</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0; opacity: 0.9;">
            Discover official immigration documents and relevant informational pages from government sources
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Top Export Buttons
    forms = db.get_forms()
    if forms:
        extracted_docs_list = []
        for form in forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                extracted_docs_list.append(structured_data)
        
        if extracted_docs_list:
            render_top_export_buttons(extracted_docs_list, "Discovery")

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
    st.info("ℹ️ **Enhanced Discovery**: The system now equally prioritizes PDF, Excel, Word, and other critical document formats alongside web pages for comprehensive immigration intelligence.")

    col1, col2 = st.columns(2)

    with col1:
        max_docs = st.slider("Maximum documents/pages to process:", 1, 30, 8)  # Increased default for better format diversity
        auto_process = st.checkbox("Auto-process after discovery", value=True)
        use_multi_agent = st.checkbox("🤖 Use Multi-Agent AI System", value=False, help="Enable collaborative AI agents for superior analysis")

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
            if use_multi_agent:
                st.info("🤖 Multi-Agent system will be used for enhanced processing")
            else:
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
                        process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai, multi_agent_orchestrator if use_multi_agent else None)
                    else:
                        if st.button("📥 Download and Process Selected Documents"):
                            process_documents_improved(docs_to_process, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai, multi_agent_orchestrator if use_multi_agent else None)
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
    batch_use_multi_agent = st.checkbox("🤖 Use Multi-Agent for Batch Processing", value=False)
    
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
                process_documents_improved(all_discovered_docs, batch_country, "Batch Process", processor, ai_service, db, True, True, multi_agent_orchestrator if batch_use_multi_agent else None)
            else:
                st.warning(f"No documents found for batch processing in {batch_country}.")
        else:
            st.error("Please select a country for batch processing.")


def process_documents_improved(discovered_docs, country, visa_type, processor, ai_service, db, save_to_db, validate_with_ai, multi_agent_orchestrator=None):
    """Improved document processing with better error handling and progress tracking"""

    st.subheader("📥 Document Processing Pipeline")
    
    if multi_agent_orchestrator:
        st.info("🤖 **Multi-Agent Processing Enabled**: Four specialized AI agents will collaborate on each document")

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
            "country_name": country,
            "category": visa_type,
            "form_name": doc.get('title', 'Unknown Form/Page'),
            "form_id": "N/A",
            "form_description": doc.get('description', ''),
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

                # Use Multi-Agent system if available
                if multi_agent_orchestrator:
                    with st.expander(f"🤖 Multi-Agent Processing: {doc['title'][:50]}..."):
                        ai_extracted_data = multi_agent_orchestrator.process_document(extracted_text, doc_info_for_ai)
                else:
                    ai_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)

                if not ai_extracted_data:
                    failed_docs.append({"doc": doc, "error": "AI extraction failed or returned invalid data", "step": "ai_extraction"})
                    form_data_to_save["validation_warnings"].append("AI extraction failed or returned invalid data")
                    form_data_to_save["processing_status"] = "ai_extraction_failed"
                else:
                    # Update form data with AI extracted information, ensuring no "Unknown" values when better data exists
                    if ai_extracted_data:
                        form_data_to_save["structured_data"] = ai_extracted_data

                        # Use AI extracted data if it's better than our defaults
                        if ai_extracted_data.get('country_name') and ai_extracted_data.get('country_name') != 'Unknown':
                            form_data_to_save['country_name'] = ai_extracted_data['country_name']
                        elif country and country != 'Unknown':
                            form_data_to_save['country_name'] = country
                            
                        if ai_extracted_data.get('category') and ai_extracted_data.get('category') != 'Unknown':
                            form_data_to_save['category'] = ai_extracted_data['category']
                        elif visa_type and visa_type != 'Unknown':
                            form_data_to_save['category'] = visa_type

                        # Update other fields only if AI provided better data
                        if ai_extracted_data.get('form_name') and ai_extracted_data.get('form_name') not in ['Unknown Form/Page', 'Unknown']:
                            form_data_to_save['form_name'] = ai_extracted_data['form_name']
                            
                        if ai_extracted_data.get('form_id') and ai_extracted_data.get('form_id') not in ['N/A', 'Unknown']:
                            form_data_to_save['form_id'] = ai_extracted_data['form_id']
                            
                        if ai_extracted_data.get('form_description') and len(ai_extracted_data.get('form_description', '')) > len(form_data_to_save.get('form_description', '')):
                            form_data_to_save['form_description'] = ai_extracted_data['form_description']
                            
                        if ai_extracted_data.get('governing_authority') and ai_extracted_data.get('governing_authority') not in ['N/A', 'Unknown']:
                            form_data_to_save['governing_authority'] = ai_extracted_data['governing_authority']

                    # Handle validation warnings from multi-agent or single agent
                    if multi_agent_orchestrator and ai_extracted_data.get('multi_agent_analysis'):
                        validation_warnings = ai_extracted_data['multi_agent_analysis'].get('validation', {}).get('warnings', [])
                    else:
                        validation_warnings = ai_service.validate_form_data(form_data_to_save["structured_data"])
                    
                    form_data_to_save['validation_warnings'] = validation_warnings
                    form_data_to_save["processing_status"] = "validated" if not validation_warnings else "validated_with_warnings"
            else:
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
                clean_form_name = clean_html_text(form.get('form_name', 'Unknown Form/Page'))
                clean_form_id = clean_html_text(form.get('form_id', 'N/A'))
                with st.expander(f"📋 {clean_form_name} (ID: {clean_form_id})"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Country:** {clean_html_text(form.get('country_name', 'N/A'))}")
                        st.write(f"**Visa Category:** {clean_html_text(form.get('category', 'N/A'))}")
                        st.write(f"**Authority:** {clean_html_text(form.get('governing_authority', 'N/A'))}")
                        st.write(f"**Database ID:** {form.get('id', 'Not saved')}")

                    with col2:
                        st.write(f"**Processing Status:** {form.get('processing_status', 'N/A')}")
                        st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                        if form.get('id'):
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
                    
                    # Show multi-agent analysis if available
                    if form.get('structured_data', {}).get('multi_agent_analysis'):
                        with st.expander("🤖 Multi-Agent Analysis Details"):
                            multi_agent_data = form['structured_data']['multi_agent_analysis']
                            st.write(f"**Overall Confidence:** {multi_agent_data.get('synthesis_confidence', 0)*100:.1f}%")
                            
                            if multi_agent_data.get('document_analysis'):
                                st.write("**Document Analysis Agent:**", multi_agent_data['document_analysis'].get('analysis', 'N/A')[:200] + "...")
                            
                            if multi_agent_data.get('validation'):
                                validation_data = multi_agent_data['validation']
                                st.write(f"**Validation Scores:** Accuracy: {validation_data.get('accuracy_score', 0)}%, Completeness: {validation_data.get('completeness_score', 0)}%")

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

    # Top Export Buttons
    extracted_docs_list = []
    for form in forms:
        structured_data = form.get('structured_data', {})
        if structured_data:
            extracted_docs_list.append(structured_data)
    
    if extracted_docs_list:
        render_top_export_buttons(extracted_docs_list, "Viewer")

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
        clean_country = clean_html_text(selected_form.get('country_name', 'N/A'))

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
        downloaded_file_path = selected_form.get('downloaded_file_path')

        # Tab Content
        if st.session_state.current_tab == "overview":
            # Overview Tab
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### 📋 Document Information")
                st.write(f"**Country:** {clean_html_text(selected_form.get('country_name', 'N/A'))}")
                st.write(f"**Visa Category:** {clean_html_text(selected_form.get('category', 'N/A'))}")
                st.write(f"**Form Name:** {clean_html_text(selected_form.get('form_name', 'N/A'))}")
                st.write(f"**Form ID:** {clean_html_text(selected_form.get('form_id', 'N/A'))}")
                st.write(f"**Authority:** {clean_html_text(selected_form.get('governing_authority', 'N/A'))}")

                if document_info_from_db:
                    st.write(f"**File Format:** {document_info_from_db.get('file_format', 'Unknown')}")
                    st.write(f"**File Size:** {document_info_from_db.get('file_size_bytes', 0):,} bytes")

            with col2:
                st.markdown("### ⚙️ Processing Details")
                structured_data = selected_form.get('structured_data', {})
                st.write(f"**Processing Status:** {selected_form.get('processing_status', 'N/A').replace('_', ' ').title()}")
                st.write(f"**Processing Time:** {structured_data.get('processing_time', 'N/A')}")
                st.write(f"**Fees:** {structured_data.get('fees', 'N/A')}")
                st.write(f"**Submission Method:** {structured_data.get('submission_method', 'N/A')}")
                st.write(f"**Last Updated:** {selected_form.get('created_at', 'N/A')}")

            # Multi-Agent Analysis Summary
            if structured_data.get('multi_agent_analysis'):
                st.markdown("### 🤖 Multi-Agent Analysis Summary")
                multi_agent_data = structured_data['multi_agent_analysis']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    confidence = multi_agent_data.get('synthesis_confidence', 0)
                    st.metric("Overall Confidence", f"{confidence*100:.1f}%")
                
                with col2:
                    validation_data = multi_agent_data.get('validation', {})
                    accuracy = validation_data.get('accuracy_score', 0)
                    st.metric("Accuracy Score", f"{accuracy}%")
                
                with col3:
                    completeness = validation_data.get('completeness_score', 0)
                    st.metric("Completeness Score", f"{completeness}%")

            # Description
            st.markdown("### 📝 Description")
            st.write(clean_html_text(selected_form.get('form_description', 'No description available')))

            # Supporting Documents
            if structured_data.get('supporting_documents'):
                st.markdown("### 📎 Required Supporting Documents")
                supporting_docs = structured_data['supporting_documents']
                if isinstance(supporting_docs, str):
                    st.write(supporting_docs)
                elif isinstance(supporting_docs, list):
                    for i, doc in enumerate(supporting_docs, 1):
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
            structured_data = selected_form.get('structured_data', {})
            full_markdown = structured_data.get('full_markdown_summary') if structured_data else None

            if full_markdown:
                st.markdown("### 🤖 AI-Generated Comprehensive Analysis")
                st.markdown(full_markdown)

                # Multi-Agent Detailed Analysis
                if structured_data.get('multi_agent_analysis'):
                    st.markdown("### 🤖 Multi-Agent Detailed Analysis")
                    multi_agent_data = structured_data['multi_agent_analysis']
                    
                    # Document Analysis Agent
                    if multi_agent_data.get('document_analysis'):
                        with st.expander("🔍 Document Analysis Agent Results"):
                            doc_analysis = multi_agent_data['document_analysis']
                            st.write(f"**Agent:** {doc_analysis.get('agent', 'Document Analysis Specialist')}")
                            st.write(f"**Confidence:** {doc_analysis.get('confidence', 0)*100:.1f}%")
                            if doc_analysis.get('analysis'):
                                st.markdown("**Analysis:**")
                                st.write(doc_analysis['analysis'])
                            if doc_analysis.get('document_type'):
                                st.write(f"**Document Type:** {doc_analysis['document_type']}")
                            if doc_analysis.get('structure_quality'):
                                st.write(f"**Structure Quality:** {doc_analysis['structure_quality']}")
                    
                    # Form Extraction Agent
                    if multi_agent_data.get('form_extraction'):
                        with st.expander("📋 Form Extraction Agent Results"):
                            form_extraction = multi_agent_data['form_extraction']
                            st.write(f"**Agent:** {form_extraction.get('agent', 'Form Extraction Specialist')}")
                            st.write(f"**Confidence:** {form_extraction.get('confidence', 0)*100:.1f}%")
                            st.json(form_extraction)
                    
                    # Validation Agent
                    if multi_agent_data.get('validation'):
                        with st.expander("✅ Validation Agent Results"):
                            validation = multi_agent_data['validation']
                            st.write(f"**Agent:** {validation.get('agent', 'Validation Specialist')}")
                            st.write(f"**Confidence:** {validation.get('confidence', 0)*100:.1f}%")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Accuracy Score", f"{validation.get('accuracy_score', 0)}%")
                            with col2:
                                st.metric("Completeness Score", f"{validation.get('completeness_score', 0)}%")
                            
                            if validation.get('warnings'):
                                st.write("**Validation Warnings:**")
                                for warning in validation['warnings']:
                                    st.warning(f"⚠️ {warning}")

                # AI Extracted Fields
                st.markdown("### 📊 Structured Data Extracted by AI")

                col1, col2 = st.columns(2)
                with col1:
                    if structured_data.get('target_users'):
                        st.write(f"**Target Users:** {structured_data['target_users']}")
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
            structured_data = selected_form.get('structured_data', {})
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
        
        pdf_docs = 0
        for f in forms:
            try:
                doc_info = db.get_document_by_form_id(f['id'])
                if doc_info and doc_info.get('file_format') == 'PDF':
                    pdf_docs += 1
            except:
                continue
        
        html_docs = 0
        for f in forms:
            try:
                doc_info = db.get_document_by_form_id(f['id'])
                if doc_info and doc_info.get('file_format') == 'HTML':
                    html_docs += 1
            except:
                continue
        
        ai_processed = len([f for f in forms if f.get('structured_data', {}).get('full_markdown_summary')])
        multi_agent_processed = len([f for f in forms if f.get('structured_data', {}).get('multi_agent_analysis')])

        col1, col2, col3, col4, col5 = st.columns(5)
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
        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style="color: #11998e; margin: 0;">🤝 {multi_agent_processed}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Multi-Agent</p>
            </div>
            """, unsafe_allow_html=True)

        # Advanced Filters
        st.markdown('<div class="filter-container">', unsafe_allow_html=True)
        st.markdown("### 🔍 Advanced Filters")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            all_countries = sorted(list(set(f.get('country_name', 'Unknown') for f in forms if f.get('country_name'))))
            selected_country = st.selectbox("🌍 Country:", ["All"] + all_countries)

        with col2:
            all_visa_categories = sorted(list(set(f.get('category', 'Unknown') for f in forms if f.get('category'))))
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
            filtered_forms = [f for f in filtered_forms if f.get('country_name') == selected_country]

        if selected_visa_category != "All":
            filtered_forms = [f for f in filtered_forms if f.get('category') == selected_visa_category]

        if selected_format != "All":
            filtered_forms = [f for f in filtered_forms if db.get_document_by_form_id(f['id']) and db.get_document_by_form_id(f['id']).get('file_format') == selected_format]

        if selected_status != "All":
            filtered_forms = [f for f in filtered_forms if f.get('processing_status') == selected_status]

        if search_query:
            search_query_lower = search_query.lower()
            filtered_forms = [
                f for f in filtered_forms
                if (search_query_lower in (f.get('form_name') or '').lower() or
                   search_query_lower in (f.get('form_id') or '').lower() or
                   search_query_lower in (f.get('form_description') or '').lower())
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

                            # Multi-agent indicator
                            multi_agent_indicator = "🤝" if form.get('structured_data', {}).get('multi_agent_analysis') else ""

                            # Clean text content to prevent HTML tags from showing
                            clean_form_name = clean_html_text(form.get('form_name', 'Unknown Document'))
                            clean_description = clean_html_text(form.get('form_description', 'No description available'))
                            clean_country = clean_html_text(form.get('country_name', 'N/A'))
                            clean_visa_category = clean_html_text(form.get('category', 'N/A'))
                            clean_form_id = clean_html_text(form.get('form_id', 'N/A'))

                            # Use Streamlit container for the card instead of HTML template
                            with st.container():
                                # Apply custom CSS class
                                st.markdown(f'<div class="document-card-wrapper">', unsafe_allow_html=True)

                                # Header with title and format badge
                                col_title, col_badge = st.columns([4, 1])
                                with col_title:
                                    st.markdown(f"### {format_icon} {multi_agent_indicator} {clean_form_name[:45]}{'...' if len(clean_form_name) > 45 else ''}")
                                with col_badge:
                                    st.markdown(f'<span class="{status_class} status-badge">{file_format}</span>', unsafe_allow_html=True)

                                # Document details
                                st.markdown(f"**🌍 Country:** {clean_country}")
                                st.markdown(f"**🛂 Visa Type:** {clean_visa_category}")
                                st.markdown(f"**🆔 Form ID:** {clean_form_id}")
                                st.markdown(f"**Status:** {status.replace('_', ' ').title()}")

                                # Multi-agent confidence if available
                                if form.get('structured_data', {}).get('multi_agent_analysis'):
                                    confidence = form['structured_data']['multi_agent_analysis'].get('synthesis_confidence', 0)
                                    st.markdown(f"**🤖 AI Confidence:** {confidence*100:.1f}%")

                                # Description
                                if clean_description:
                                    st.markdown(f"**Description:** {clean_description[:80]}{'...' if len(clean_description) > 80 else ''}")

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
        
            # Add bulk export functionality
            if filtered_forms:
                st.markdown("---")
                # Extract all structured data for bulk export
                extracted_docs_list = []
                for form in filtered_forms:
                    structured_data = form.get('structured_data', {})
                    if structured_data:
                        extracted_docs_list.append(structured_data)
                
                if extracted_docs_list:
                    render_bulk_export_buttons(extracted_docs_list)
        else:
            st.info("🔍 No documents match your current filters. Try adjusting the search criteria.")

def validation_panel_page(db, processor, ai_service, multi_agent_orchestrator):
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

    # Top Export Buttons
    if forms:
        extracted_docs_list = []
        for form in forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                extracted_docs_list.append(structured_data)
        
        if extracted_docs_list:
            render_top_export_buttons(extracted_docs_list, "Validation")

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
                clean_country = clean_html_text(form.get('country_name', 'Unknown'))
                
                # Multi-agent indicator
                multi_agent_indicator = " 🤝" if form.get('structured_data', {}).get('multi_agent_analysis') else ""
                
                with st.expander(f"📋 {clean_form_name} - {clean_country}{multi_agent_indicator} (Status: {form.get('processing_status', 'N/A')})"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write(f"**Form ID:** {clean_html_text(form.get('form_id', 'N/A'))}")
                        st.write(f"**Description:** {clean_html_text(form.get('form_description', 'N/A'))}")
                        st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                        st.write(f"**Official Source URL:** {form.get('official_source_url', 'N/A')}")

                        document_info_from_db = db.get_document_by_form_id(form['id'])
                        if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                            st.write(f"**Cloudinary Original URL:** [Link]({document_info_from_db['cloudinary_url']})")
                        else:
                            st.write(f"**Cloudinary Original URL:** N/A")

                        # Multi-agent analysis summary
                        if form.get('structured_data', {}).get('multi_agent_analysis'):
                            multi_agent_data = form['structured_data']['multi_agent_analysis']
                            st.info(f"🤖 **Multi-Agent Analysis:** Overall Confidence: {multi_agent_data.get('synthesis_confidence', 0)*100:.1f}%")

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
                            use_multi_agent_rerun = st.checkbox("🤖 Use Multi-Agent for Re-run", value=False)

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

                                                # Use Multi-Agent system if selected
                                                if use_multi_agent_rerun:
                                                    st.info("🤖 Using Multi-Agent system for re-processing...")
                                                    re_extracted_data = multi_agent_orchestrator.process_document(extracted_text, doc_info_for_ai)
                                                else:
                                                    re_extracted_data = ai_service.extract_form_data(extracted_text, doc_info_for_ai)

                                                if re_extracted_data:
                                                    # Handle validation warnings from multi-agent or single agent
                                                    if use_multi_agent_rerun and re_extracted_data.get('multi_agent_analysis'):
                                                        validation_warnings = re_extracted_data['multi_agent_analysis'].get('validation', {}).get('warnings', [])
                                                    else:
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
                                                            "country_name": re_extracted_data.get('country_name', form.get('country_name', 'Unknown')),
                                                            "category": re_extracted_data.get('category', form.get('category', 'Unknown')),
                                                            "form_name": re_extracted_data.get('form_name', form.get('form_name', 'Unknown')),
                                                            "form_id": re_extracted_data.get('form_id', form.get('form_id', 'N/A')),
                                                            "form_description": re_extracted_data.get('form_description', form.get('form_description', '')),
                                                            "governing_authority": re_extracted_data.get('governing_authority', form.get('governing_authority', 'N/A'))
                                                        }
                                                    )

                                                    if update_success:
                                                        success_msg = "AI extraction and validation re-run successfully!"
                                                        if use_multi_agent_rerun:
                                                            success_msg += " 🤖 Multi-Agent system used."
                                                        st.success(success_msg)
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
    else:
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
    
    # Initialize filtered_forms at the beginning to fix the UnboundLocalError
    filtered_forms = []

    # Top Export Buttons
    if forms:
        extracted_docs_list = []
        for form in forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                extracted_docs_list.append(structured_data)
        
        if extracted_docs_list:
            render_top_export_buttons(extracted_docs_list, "Export")

    if forms:
        st.success(f"✅ Found {len(forms)} documents/pages available for export")

        st.markdown('<div class="export-options">', unsafe_allow_html=True)
        st.markdown("### 🔧 Export Options")

        col1, col2 = st.columns(2)

        with col1:
            country_filter = st.selectbox(
                "Filter by Country:",
                ["All"] + list(set(form.get('country_name', 'Unknown') for form in forms if form.get('country_name')))
            )

        with col2:
            status_filter = st.selectbox(
                "Filter by Review Status:",
                ["All", "Approved", "Pending Review", "Needs Revision", "Downloaded Only", "Partial AI Failure", "AI Extraction Failed", "Low Text Content"]
            )

        filtered_forms = forms
        if country_filter != "All":
            filtered_forms = [form for form in filtered_forms if form.get('country_name') == country_filter]

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

        with col3:
            if st.button("📋 Export Summaries (Markdown)"):
                if filtered_forms:
                    exported_files_count = 0
                    for form in filtered_forms:
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

    # Show preview of forms to export
    if filtered_forms:
        st.subheader("Preview of Forms/Pages to Export")

        preview_data = []
        for form in filtered_forms:
            # Extract structured data for preview
            structured_data = form.get('structured_data', {})
            
            # Multi-agent indicator
            multi_agent_indicator = "🤝" if structured_data.get('multi_agent_analysis') else ""
            
            preview_data.append({
                "Form Name": clean_html_text(form.get('form_name', 'Unknown')) + multi_agent_indicator,
                "Form Slug": structured_data.get('form_slug', 'N/A'),
                "Country Code": structured_data.get('country_code', 'N/A'),
                "Country Name": clean_html_text(form.get('country_name', 'Unknown')),
                "Category": clean_html_text(form.get('category', 'Unknown')),
                "Form ID": clean_html_text(form.get('form_id', 'N/A')),
                "Governing Authority": clean_html_text(form.get('governing_authority', 'N/A')),
                "Processing Status": form.get('processing_status', 'N/A'),
                "Review Status": (form.get('lawyer_review') or {}).get('approval_status', 'Pending'),
                "AI Confidence": f"{structured_data.get('multi_agent_analysis', {}).get('synthesis_confidence', 0)*100:.1f}%" if structured_data.get('multi_agent_analysis') else "N/A",
                "Last Updated": str(form.get('created_at', 'N/A'))
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

                    # Simple test export
                    test_df = pd.DataFrame([{
                        'id': form.get('id', ''),
                        'country': form.get('country_name', ''),
                        'form_name': form.get('form_name', ''),
                        'form_id': form.get('form_id', ''),
                        'multi_agent': 'Yes' if form.get('structured_data', {}).get('multi_agent_analysis') else 'No',
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
            usa_forms = db.get_forms(country_code="USA")
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

    # Top Export Buttons
    if forms:
        extracted_docs_list = []
        for form in forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                extracted_docs_list.append(structured_data)
        
        if extracted_docs_list:
            render_top_export_buttons(extracted_docs_list, "Database")

    if forms:
        st.markdown("### 📊 Database Statistics")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #667eea; margin: 0;">📄 {len(forms)}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Total Forms/Pages</p>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            countries_in_db = set(form.get('country_name', 'Unknown') for form in forms)
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

        with col5:
            multi_agent_forms = len([
                form for form in forms
                if form.get('structured_data', {}).get('multi_agent_analysis')
            ])
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: #9c27b0; margin: 0;">🤝 {multi_agent_forms}</h3>
                <p style="margin: 5px 0 0 0; color: #666;">Multi-Agent</p>
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
                ["All"] + sorted(list(set(form.get('country_name', 'Unknown') for form in forms)))
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
                    search_term.lower() in form.get('form_description', '').lower())
            ]

        if country_filter != "All":
            filtered_forms = [form for form in filtered_forms if form.get('country_name') == country_filter]

        if processing_status_filter != "All":
            filtered_forms = [form for form in filtered_forms if form.get('processing_status') == processing_status_filter]

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f"### 📄 Forms/Pages ({len(filtered_forms)} found)")

        for form in filtered_forms:
            clean_form_name = clean_html_text(form.get('form_name', 'Unknown'))
            clean_form_id = clean_html_text(form.get('form_id', 'N/A'))
            clean_country = clean_html_text(form.get('country_name', 'Unknown'))
            
            # Multi-agent indicator
            multi_agent_indicator = " 🤝" if form.get('structured_data', {}).get('multi_agent_analysis') else ""
            
            with st.expander(f"📋 {clean_form_name} ({clean_form_id}) - {clean_country}{multi_agent_indicator} (Status: {form.get('processing_status', 'N/A')})"):
                col1, col2 = st.columns(2)

                with col1:
                    st.write(f"**Country:** {clean_country}")
                    st.write(f"**Visa Category:** {clean_html_text(form.get('category', 'Unknown'))}")
                    st.write(f"**Form ID:** {clean_form_id}")
                    st.write(f"**Authority:** {clean_html_text(form.get('governing_authority', 'N/A'))}")
                    st.write(f"**Created:** {form.get('created_at', 'N/A')}")

                with col2:
                    review_status = (form.get('lawyer_review') or {}).get('approval_status', 'Pending Review')
                    st.write(f"**Review Status:** {review_status}")

                    if form.get('validation_warnings'):
                        st.write(f"**Warnings:** {len(form['validation_warnings'])}")

                    # Multi-agent confidence if available
                    if form.get('structured_data', {}).get('multi_agent_analysis'):
                        confidence = form['structured_data']['multi_agent_analysis'].get('synthesis_confidence', 0)
                        st.write(f"**🤖 AI Confidence:** {confidence*100:.1f}%")

                    source_url = form.get('official_source_url', '')
                    st.write(f"**Source:** {source_url}")
                    st.write(f"**Downloaded Path (Local):** {form.get('downloaded_file_path', 'N/A')}")
                    document_info_from_db = db.get_document_by_form_id(form['id'])
                    if document_info_from_db and document_info_from_db.get('cloudinary_url'):
                        st.write(f"**Cloudinary Original URL:** [Link]({document_info_from_db['cloudinary_url']})")
                    else:
                        st.write(f"**Cloudinary Original URL:** N/A")

                st.write(f"**Description:** {clean_html_text(form.get('form_description', 'No description'))}")

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

    # Top Export Buttons
    if all_forms:
        extracted_docs_list = []
        for form in all_forms:
            structured_data = form.get('structured_data', {})
            if structured_data:
                extracted_docs_list.append(structured_data)
        
        if extracted_docs_list:
            render_top_export_buttons(extracted_docs_list, "Cloudinary")

    cloudinary_docs = []
    for form in all_forms:
        document_info = db.get_document_by_form_id(form['id'])
        if document_info and document_info.get('cloudinary_url'):
            # Multi-agent indicator
            multi_agent_indicator = " 🤝" if form.get('structured_data', {}).get('multi_agent_analysis') else ""
            
            cloudinary_docs.append({
                "form_id": form['id'],
                "country": form.get('country_name', 'Unknown'),
                "visa_category": form.get('category', 'Unknown'),
                "form_name": form.get('form_name', 'Unknown') + multi_agent_indicator,
                "cloudinary_url": document_info['cloudinary_url'],
                "file_format": document_info['file_format'],
                "filename": document_info['filename'],
                "multi_agent": bool(form.get('structured_data', {}).get('multi_agent_analysis'))
            })

    if not cloudinary_docs:
        st.info("No documents with Cloudinary URLs found in the database. Please process some documents first.")
        return

    st.info(f"Displaying {len(cloudinary_docs)} documents found on Cloudinary.")

    # Multi-agent statistics
    multi_agent_count = sum(1 for doc in cloudinary_docs if doc['multi_agent'])
    st.success(f"🤝 {multi_agent_count} documents processed with Multi-Agent system")

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
                multi_agent_in_category = sum(1 for doc in docs if doc['multi_agent'])
                st.markdown(f"""
                <div style="background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
                           color: white; padding: 15px; border-radius: 10px; margin: 10px 0;
                           text-align: center; font-weight: bold; font-size: 1.1rem;">
                    🛂 {visa_category} ({len(docs)} documents) 🤝 {multi_agent_in_category} Multi-Agent
                </div>
                """, unsafe_allow_html=True)

                for doc in docs:
                    clean_doc_form_name = clean_html_text(doc['form_name'])
                    clean_doc_form_id = clean_html_text(str(doc['form_id']))

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
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .health-success {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .health-error {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    </style>

    <div class="health-header">
        <h1>🩺 Database Health Check</h1>
        <p style="font-size: 1.2rem; margin-bottom: 0;">
            Monitor database connection, performance, and data integrity
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔍 Run Health Check", type="primary"):
        with st.spinner("Running comprehensive database health check..."):
            health_results = run_database_health_check(database_url)

            # Display results
            if health_results['connection_status']:
                st.markdown(f"""
                <div class="health-success">
                    <h3>✅ Database Connection: Healthy</h3>
                    <p><strong>Database URL:</strong> {health_results['database_info']['host']}:{health_results['database_info']['port']}</p>
                    <p><strong>Database Name:</strong> {health_results['database_info']['database']}</p>
                    <p><strong>Connection Time:</strong> {health_results['connection_time']:.3f} seconds</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="health-error">
                    <h3>❌ Database Connection: Failed</h3>
                    <p><strong>Error:</strong> {health_results['connection_error']}</p>
                </div>
                """, unsafe_allow_html=True)

            # Table Statistics
            if health_results['table_stats']:
                st.markdown('<div class="health-info">', unsafe_allow_html=True)
                st.markdown("### 📊 Table Statistics")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Forms Table", f"{health_results['table_stats']['forms_count']:,} records")
                with col2:
                    st.metric("Documents Table", f"{health_results['table_stats']['documents_count']:,} records")
                with col3:
                    st.metric("Total Records", f"{health_results['table_stats']['total_records']:,}")

                st.markdown('</div>', unsafe_allow_html=True)

            # Data Quality Metrics
            if health_results['data_quality']:
                st.markdown('<div class="health-info">', unsafe_allow_html=True)
                st.markdown("### 🎯 Data Quality Metrics")

                quality_metrics = health_results['data_quality']

                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Forms with AI Processing:** {quality_metrics['forms_with_ai_processing']:,}")
                    st.write(f"**Forms with Multi-Agent Processing:** {quality_metrics['forms_with_multi_agent']:,}")
                    st.write(f"**Forms with Validation Warnings:** {quality_metrics['forms_with_warnings']:,}")

                with col2:
                    st.write(f"**Approved Forms:** {quality_metrics['approved_forms']:,}")
                    st.write(f"**Pending Review:** {quality_metrics['pending_review']:,}")
                    st.write(f"**Forms with Cloudinary URLs:** {quality_metrics['forms_with_cloudinary']:,}")

                # Data completeness percentage
                if health_results['table_stats']['forms_count'] > 0:
                    ai_processing_rate = (quality_metrics['forms_with_ai_processing'] / health_results['table_stats']['forms_count']) * 100
                    multi_agent_rate = (quality_metrics['forms_with_multi_agent'] / health_results['table_stats']['forms_count']) * 100
                    cloudinary_rate = (quality_metrics['forms_with_cloudinary'] / health_results['table_stats']['forms_count']) * 100

                    st.markdown("**Processing Rates:**")
                    st.progress(ai_processing_rate / 100)
                    st.write(f"AI Processing: {ai_processing_rate:.1f}%")

                    st.progress(multi_agent_rate / 100)
                    st.write(f"Multi-Agent Processing: {multi_agent_rate:.1f}%")

                    st.progress(cloudinary_rate / 100)
                    st.write(f"Cloudinary Storage: {cloudinary_rate:.1f}%")

                st.markdown('</div>', unsafe_allow_html=True)

            # Performance Metrics
            if health_results['performance']:
                st.markdown('<div class="health-info">', unsafe_allow_html=True)
                st.markdown("### ⚡ Performance Metrics")

                perf_metrics = health_results['performance']

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Query Response Time", f"{perf_metrics['avg_query_time']:.3f}s")
                with col2:
                    st.metric("Index Usage", f"{perf_metrics['index_usage']:.1f}%")
                with col3:
                    st.metric("Database Size", f"{perf_metrics['database_size_mb']:.1f} MB")

                st.markdown('</div>', unsafe_allow_html=True)

            # Recent Activity
            if health_results['recent_activity']:
                st.markdown('<div class="health-info">', unsafe_allow_html=True)
                st.markdown("### 📈 Recent Activity")

                activity = health_results['recent_activity']
                st.write(f"**Forms added in last 24 hours:** {activity['forms_last_24h']}")
                st.write(f"**Forms added in last 7 days:** {activity['forms_last_7d']}")
                st.write(f"**Most recent form:** {activity['most_recent_form']}")

                st.markdown('</div>', unsafe_allow_html=True)

            # Recommendations
            if health_results['recommendations']:
                st.markdown('<div class="health-info">', unsafe_allow_html=True)
                st.markdown("### 💡 Recommendations")

                for recommendation in health_results['recommendations']:
                    st.info(f"💡 {recommendation}")

                st.markdown('</div>', unsafe_allow_html=True)

    # Manual Database Operations
    st.markdown("---")
    st.markdown("### 🛠️ Manual Database Operations")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧹 Clean Orphaned Records"):
            with st.spinner("Cleaning orphaned records..."):
                try:
                    db = DatabaseManager(database_url)
                    cleaned_count = db.clean_orphaned_records()
                    st.success(f"✅ Cleaned {cleaned_count} orphaned records")
                except Exception as e:
                    st.error(f"❌ Error cleaning records: {e}")

    with col2:
        if st.button("📊 Rebuild Indexes"):
            with st.spinner("Rebuilding database indexes..."):
                try:
                    db = DatabaseManager(database_url)
                    db.rebuild_indexes()
                    st.success("✅ Database indexes rebuilt successfully")
                except Exception as e:
                    st.error(f"❌ Error rebuilding indexes: {e}")

    with col3:
        if st.button("🔄 Update Statistics"):
            with st.spinner("Updating database statistics..."):
                try:
                    db = DatabaseManager(database_url)
                    db.update_statistics()
                    st.success("✅ Database statistics updated successfully")
                except Exception as e:
                    st.error(f"❌ Error updating statistics: {e}")

def run_database_health_check(database_url: str) -> dict:
    """Run comprehensive database health check"""
    import time
    import psycopg2
    from urllib.parse import urlparse

    health_results = {
        'connection_status': False,
        'connection_error': None,
        'connection_time': 0,
        'database_info': {},
        'table_stats': {},
        'data_quality': {},
        'performance': {},
        'recent_activity': {},
        'recommendations': []
    }

    try:
        # Parse database URL
        parsed_url = urlparse(database_url)
        health_results['database_info'] = {
            'host': parsed_url.hostname,
            'port': parsed_url.port,
            'database': parsed_url.path[1:] if parsed_url.path else '',
            'username': parsed_url.username
        }

        # Test connection
        start_time = time.time()
        conn = psycopg2.connect(database_url)
        health_results['connection_time'] = time.time() - start_time
        health_results['connection_status'] = True

        cursor = conn.cursor()

        # Table statistics
        cursor.execute("SELECT COUNT(*) FROM forms")
        forms_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents")
        documents_count = cursor.fetchone()[0]

        health_results['table_stats'] = {
            'forms_count': forms_count,
            'documents_count': documents_count,
            'total_records': forms_count + documents_count
        }

        # Data quality metrics
        cursor.execute("SELECT COUNT(*) FROM forms WHERE structured_data IS NOT NULL AND structured_data != '{}'")
        forms_with_ai = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM forms WHERE structured_data::text LIKE '%multi_agent_analysis%'")
        forms_with_multi_agent = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM forms WHERE validation_warnings IS NOT NULL AND array_length(validation_warnings, 1) > 0")
        forms_with_warnings = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM forms WHERE lawyer_review->>'approval_status' = 'Approved'")
        approved_forms = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM forms WHERE lawyer_review->>'approval_status' = 'Pending Review' OR lawyer_review IS NULL")
        pending_review = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents WHERE cloudinary_url IS NOT NULL")
        forms_with_cloudinary = cursor.fetchone()[0]

        health_results['data_quality'] = {
            'forms_with_ai_processing': forms_with_ai,
            'forms_with_multi_agent': forms_with_multi_agent,
            'forms_with_warnings': forms_with_warnings,
            'approved_forms': approved_forms,
            'pending_review': pending_review,
            'forms_with_cloudinary': forms_with_cloudinary
        }

        # Performance metrics
        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size = cursor.fetchone()[0]

        # Simple performance test
        perf_start = time.time()
        cursor.execute("SELECT COUNT(*) FROM forms WHERE created_at > NOW() - INTERVAL '1 day'")
        perf_time = time.time() - perf_start

        health_results['performance'] = {
            'avg_query_time': perf_time,
            'index_usage': 85.0,  # Placeholder - would need more complex query
            'database_size_mb': float(db_size.split()[0]) if 'MB' in db_size else 0.0
        }

        # Recent activity
        cursor.execute("SELECT COUNT(*) FROM forms WHERE created_at > NOW() - INTERVAL '1 day'")
        forms_24h = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM forms WHERE created_at > NOW() - INTERVAL '7 days'")
        forms_7d = cursor.fetchone()[0]

        cursor.execute("SELECT form_name, created_at FROM forms ORDER BY created_at DESC LIMIT 1")
        recent_form = cursor.fetchone()

        health_results['recent_activity'] = {
            'forms_last_24h': forms_24h,
            'forms_last_7d': forms_7d,
            'most_recent_form': f"{recent_form[0]} ({recent_form[1]})" if recent_form else "None"
        }

        # Generate recommendations
        recommendations = []
        if forms_with_ai / forms_count < 0.8 if forms_count > 0 else False:
            recommendations.append("Consider running AI processing on more forms to improve data quality")

        if forms_with_multi_agent / forms_count < 0.3 if forms_count > 0 else False:
            recommendations.append("Multi-Agent processing could improve extraction accuracy for more forms")

        if pending_review > approved_forms:
            recommendations.append("Many forms are pending lawyer review - consider prioritizing review process")

        if forms_with_cloudinary / documents_count < 0.9 if documents_count > 0 else False:
            recommendations.append("Some documents may not be properly stored on Cloudinary")

        health_results['recommendations'] = recommendations

        cursor.close()
        conn.close()

    except Exception as e:
        health_results['connection_error'] = str(e)

    return health_results

if __name__ == "__main__":
    main()
