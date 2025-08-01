import openai
import google.generativeai as genai
from typing import Dict, Any, List, Tuple, Optional
import json
import streamlit as st
from datetime import datetime
import re # For extracting potential JSON from Markdown if needed (future proofing)
import requests

class AIExtractionService:
    """Enhanced AI service with priority order: Gemini → OpenRouter → OpenAI"""
    
    def __init__(self, openai_api_key: str = "", openrouter_api_key: str = "", gemini_api_key: str = ""):
        # Initialize clients based on available API keys
        self.openai_client = None
        self.openrouter_client = None
        self.gemini_model = None
        
        # Priority order: Gemini → OpenRouter → OpenAI
        self.active_service = None
        
        # Initialize Gemini (highest priority)
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self.active_service = "Gemini"
                print("✅ Gemini AI initialized successfully (Priority 1)")
            except Exception as e:
                print(f"❌ Gemini initialization failed: {e}")
        
        # Initialize OpenRouter (second priority)
        if openrouter_api_key and not self.active_service:
            try:
                self.openrouter_client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_api_key,
                )
                # Test the connection
                test_response = self.openrouter_client.models.list()
                self.active_service = "OpenRouter"
                print("✅ OpenRouter AI initialized successfully (Priority 2)")
            except Exception as e:
                print(f"❌ OpenRouter initialization failed: {e}")
                self.openrouter_client = None
        
        # Initialize OpenAI (third priority)
        if openai_api_key and not self.active_service:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                # Test the connection
                test_response = self.openai_client.models.list()
                self.active_service = "OpenAI"
                print("✅ OpenAI initialized successfully (Priority 3)")
            except Exception as e:
                print(f"❌ OpenAI initialization failed: {e}")
                self.openai_client = None
        
        if not self.active_service:
            print("⚠️ No AI services available. Please provide valid API keys.")
    
    def get_active_service(self) -> str:
        """Get the currently active AI service"""
        return self.active_service or "None"
    
    def extract_form_data(self, extracted_text: str, doc_info: Dict) -> Dict[str, Any]:
        """Extract form data using the active AI service with intelligent fallback"""
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            return self._create_fallback_response(doc_info, "Insufficient text content")
        
        # Try services in priority order with automatic fallback
        services_to_try = []
        
        if self.gemini_model:
            services_to_try.append(("Gemini", self._extract_with_gemini))
        if self.openrouter_client:
            services_to_try.append(("OpenRouter", self._extract_with_openrouter))
        if self.openai_client:
            services_to_try.append(("OpenAI", self._extract_with_openai))
        
        for service_name, extract_func in services_to_try:
            try:
                print(f"Attempting AI extraction with {service_name}...")
                result = extract_func(extracted_text, doc_info)
                if result and isinstance(result, dict) and result.get('form_name'):
                    print(f"AI extraction successful using {service_name}.")
                    self.active_service = service_name  # Update active service
                    return result
                else:
                    print(f"AI extraction with {service_name} returned invalid data, trying next service...")
            except Exception as e:
                print(f"AI extraction failed with {service_name}: {str(e)}")
                continue
        
        # If all services fail, return fallback
        print("All AI services failed, returning fallback response.")
        return self._create_fallback_response(doc_info, "All AI services failed")
    
    def _extract_with_gemini(self, extracted_text: str, doc_info: Dict) -> Dict[str, Any]:
        """Extract using Gemini AI"""
        
        prompt = self._create_enhanced_extraction_prompt(extracted_text, doc_info)
        
        response = self.gemini_model.generate_content(prompt)
        response_text = response.text
        
        # Try to extract JSON from response
        return self._parse_ai_response(response_text, doc_info)
    
    def _extract_with_openrouter(self, extracted_text: str, doc_info: Dict) -> Dict[str, Any]:
        """Extract using OpenRouter AI"""
        
        prompt = self._create_enhanced_extraction_prompt(extracted_text, doc_info)
        
        response = self.openrouter_client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet",  # High-quality model
            messages=[
                {"role": "system", "content": "You are an expert immigration document analyst. Extract structured information from documents and return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        response_text = response.choices[0].message.content
        return self._parse_ai_response(response_text, doc_info)
    
    def _extract_with_openai(self, extracted_text: str, doc_info: Dict) -> Dict[str, Any]:
        """Extract using OpenAI"""
        
        prompt = self._create_enhanced_extraction_prompt(extracted_text, doc_info)
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert immigration document analyst. Extract structured information from documents and return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        response_text = response.choices[0].message.content
        return self._parse_ai_response(response_text, doc_info)
    
    def _create_enhanced_extraction_prompt(self, extracted_text: str, doc_info: Dict) -> str:
        """Create an enhanced extraction prompt with intelligent context"""
        
        # Analyze URL and filename for context
        url = doc_info.get('download_url', doc_info.get('url', ''))
        filename = doc_info.get('filename', '')
        file_format = doc_info.get('file_format', 'Unknown')
        
        # Smart form ID detection from URL/filename
        form_id_hints = self._extract_form_id_from_url(url, filename)
        
        # Authority mapping based on URL
        authority_hint = self._map_authority_from_url(url)
        
        # Category intelligence from URL/content
        category_hint = self._infer_category_from_context(url, filename, extracted_text[:500])
        
        prompt = f"""
You are an expert immigration document analyst. Analyze this document and extract structured information.

DOCUMENT CONTEXT:
- URL: {url}
- Filename: {filename}
- Format: {file_format}
- Likely Form ID: {form_id_hints}
- Likely Authority: {authority_hint}
- Likely Category: {category_hint}

DOCUMENT CONTENT:
{extracted_text[:3000]}

Extract the following information and return ONLY valid JSON:

{{
    "form_name": "Official form name (use context clues if not explicit)",
    "form_slug": "url-friendly-form-name",
    "form_id": "Form number/ID (check URL, filename, and content)",
    "country_code": "3-letter country code (USA, CAN, GBR, etc.)",
    "country_name": "Full country name",
    "category": "Immigration category (Work Visa, Student Visa, etc.)",
    "governing_authority": "Issuing government agency",
    "target_applicants": "Who should use this form",
    "form_description": "Detailed description of the form's purpose",
    "required_fields": [
        {{
            "name": "Field name",
            "description": "Field description",
            "type": "text/number/date/select/checkbox",
            "required": true/false,
            "example_value": "Example if available"
        }}
    ],
    "supporting_documents": "List of required supporting documents",
    "submission_method": "How to submit (online/mail/in-person)",
    "processing_time": "Expected processing time",
    "fees": "Application fees",
    "language": "Primary language",
    "notes_or_instructions": "Additional important notes",
    "extracted_text_length": {len(extracted_text)},
    "full_markdown_summary": "Comprehensive markdown summary of the document"
}}

IMPORTANT INSTRUCTIONS:
1. Use the URL and filename context to improve form_id detection
2. Map the authority based on the domain (e.g., uscis.gov → USCIS)
3. Infer missing information intelligently from context
4. If exact information isn't available, use "N/A" rather than making up data
5. Ensure all JSON is properly formatted and valid
6. The full_markdown_summary should be comprehensive and well-formatted
"""
        
        return prompt
    
    def _extract_form_id_from_url(self, url: str, filename: str) -> str:
        """Smart form ID extraction from URL and filename"""
        
        # Common form ID patterns
        patterns = [
            r'[I]-\d+',           # I-129, I-485, etc.
            r'[N]-\d+',           # N-400, etc.
            r'[G]-\d+',           # G-325A, etc.
            r'[AR]-\d+',          # AR-11, etc.
            r'DS-\d+',            # DS-160, etc.
            r'[A-Z]+-\d+',        # General pattern
            r'form[-_]?\d+',      # form123, form-123
            r'[A-Z]\d+[A-Z]?'     # I94, etc.
        ]
        
        text_to_search = f"{url} {filename}".upper()
        
        for pattern in patterns:
            matches = re.findall(pattern, text_to_search)
            if matches:
                return matches[0]
        
        return "N/A"
    
    def _map_authority_from_url(self, url: str) -> str:
        """Map government authority based on URL domain"""
        
        url_lower = url.lower()
        
        authority_mapping = {
            'uscis.gov': 'U.S. Citizenship and Immigration Services (USCIS)',
            'state.gov': 'U.S. Department of State',
            'cbp.gov': 'U.S. Customs and Border Protection (CBP)',
            'dol.gov': 'U.S. Department of Labor (DOL)',
            'ice.gov': 'U.S. Immigration and Customs Enforcement (ICE)',
            'canada.ca': 'Immigration, Refugees and Citizenship Canada (IRCC)',
            'cic.gc.ca': 'Immigration, Refugees and Citizenship Canada (IRCC)',
            'gov.uk': 'UK Home Office',
            'homeaffairs.gov.au': 'Australian Department of Home Affairs',
            'border.gov.au': 'Australian Border Force',
            'bamf.de': 'Federal Office for Migration and Refugees (BAMF)',
            'diplomatie.gouv.fr': 'Ministry for Europe and Foreign Affairs (France)',
            'ica.gov.ae': 'Federal Authority for Identity and Citizenship (UAE)',
            'mea.gov.in': 'Ministry of External Affairs (India)',
            'gob.mx': 'Government of Mexico',
            'inm.gob.mx': 'National Institute of Migration (Mexico)',
            'gov.br': 'Government of Brazil',
            'mfa.gov.cn': 'Ministry of Foreign Affairs (China)',
            'mofa.go.jp': 'Ministry of Foreign Affairs (Japan)',
            'hikorea.go.kr': 'Korea Immigration Service',
            'dha.gov.za': 'Department of Home Affairs (South Africa)',
            'immigration.govt.nz': 'Immigration New Zealand',
            'ica.gov.sg': 'Immigration & Checkpoints Authority (Singapore)',
            'dfa.gov.ph': 'Department of Foreign Affairs (Philippines)'
        }
        
        for domain, authority in authority_mapping.items():
            if domain in url_lower:
                return authority
        
        return "N/A"
    
    def _infer_category_from_context(self, url: str, filename: str, content_sample: str) -> str:
        """Infer immigration category from context"""
        
        text_to_analyze = f"{url} {filename} {content_sample}".lower()
        
        category_keywords = {
            'Work Visa': ['work', 'employment', 'h1b', 'h-1b', 'l1', 'l-1', 'o1', 'o-1', 'eb', 'labor', 'job'],
            'Student Visa': ['student', 'f1', 'f-1', 'm1', 'm-1', 'study', 'education', 'school', 'university'],
            'Tourist Visa': ['tourist', 'visitor', 'b1', 'b-1', 'b2', 'b-2', 'travel', 'vacation'],
            'Family Visa': ['family', 'spouse', 'marriage', 'k1', 'k-1', 'cr1', 'cr-1', 'ir1', 'ir-1', 'relative'],
            'Permanent Residence': ['green card', 'permanent', 'resident', 'i485', 'i-485', 'adjustment'],
            'Citizenship': ['citizenship', 'naturalization', 'n400', 'n-400', 'citizen'],
            'Business Visa': ['business', 'investor', 'eb5', 'eb-5', 'e1', 'e-1', 'e2', 'e-2'],
            'Asylum': ['asylum', 'refugee', 'persecution', 'protection'],
            'Transit Visa': ['transit', 'c1', 'c-1', 'crew', 'd1', 'd-1']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return category
        
        return "Unknown"
    
    def _parse_ai_response(self, response_text: str, doc_info: Dict) -> Dict[str, Any]:
        """Enhanced AI response parsing with robust fallback"""
        
        try:
            # Try to extract JSON from response
            if "\`\`\`json" in response_text:
                json_start = response_text.find("\`\`\`json") + 7
                json_end = response_text.find("\`\`\`", json_start)
                json_content = response_text[json_start:json_end].strip()
            elif "{" in response_text and "}" in response_text:
                # Find the JSON object
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                json_content = response_text[start:end]
            else:
                json_content = response_text
            
            # Parse JSON
            extracted_data = json.loads(json_content)
            
            # Validate and enhance the extracted data
            return self._validate_and_enhance_data(extracted_data, doc_info)
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response text: {response_text[:500]}...")
            return self._create_fallback_response(doc_info, f"JSON parsing failed: {str(e)}")
        except Exception as e:
            print(f"Response parsing error: {e}")
            return self._create_fallback_response(doc_info, f"Response parsing failed: {str(e)}")
    
    def _validate_and_enhance_data(self, data: Dict, doc_info: Dict) -> Dict[str, Any]:
        """Validate and enhance extracted data with URL-based intelligence"""
        
        # URL-based enhancements
        url = doc_info.get('download_url', doc_info.get('url', ''))
        filename = doc_info.get('filename', '')
        
        # Enhance form_id if missing or generic
        if not data.get('form_id') or data.get('form_id') == 'N/A':
            form_id_from_url = self._extract_form_id_from_url(url, filename)
            if form_id_from_url != 'N/A':
                data['form_id'] = form_id_from_url
        
        # Enhance authority if missing
        if not data.get('governing_authority') or data.get('governing_authority') == 'N/A':
            authority_from_url = self._map_authority_from_url(url)
            if authority_from_url != 'N/A':
                data['governing_authority'] = authority_from_url
        
        # Enhance country information
        if not data.get('country_name') or data.get('country_name') == 'Unknown':
            country_from_url = self._infer_country_from_url(url)
            if country_from_url:
                data['country_name'] = country_from_url['name']
                data['country_code'] = country_from_url['code']
        
        # Ensure required fields exist with defaults
        required_fields = [
            'form_name', 'form_id', 'country_name', 'category', 'governing_authority',
            'target_applicants', 'form_description', 'supporting_documents',
            'submission_method', 'processing_time', 'fees', 'language',
            'notes_or_instructions', 'full_markdown_summary'
        ]
        
        for field in required_fields:
            if field not in data or not data[field]:
                data[field] = self._get_smart_default(field, doc_info, data)
        
        # Ensure required_fields is a list
        if not isinstance(data.get('required_fields'), list):
            data['required_fields'] = []
        
        # Add metadata
        data['extracted_text_length'] = len(doc_info.get('extracted_text', ''))
        data['extraction_timestamp'] = datetime.now().isoformat()
        data['ai_service_used'] = self.active_service
        
        return data
    
    def _infer_country_from_url(self, url: str) -> Optional[Dict[str, str]]:
        """Infer country from URL domain"""
        
        url_lower = url.lower()
        
        country_mapping = {
            'uscis.gov': {'name': 'United States', 'code': 'USA'},
            'state.gov': {'name': 'United States', 'code': 'USA'},
            'cbp.gov': {'name': 'United States', 'code': 'USA'},
            'canada.ca': {'name': 'Canada', 'code': 'CAN'},
            'cic.gc.ca': {'name': 'Canada', 'code': 'CAN'},
            'gov.uk': {'name': 'United Kingdom', 'code': 'GBR'},
            'homeaffairs.gov.au': {'name': 'Australia', 'code': 'AUS'},
            'bamf.de': {'name': 'Germany', 'code': 'DEU'},
            'diplomatie.gouv.fr': {'name': 'France', 'code': 'FRA'},
            'ica.gov.ae': {'name': 'United Arab Emirates', 'code': 'ARE'},
            'mea.gov.in': {'name': 'India', 'code': 'IND'},
            'gob.mx': {'name': 'Mexico', 'code': 'MEX'},
            'gov.br': {'name': 'Brazil', 'code': 'BRA'},
            'mfa.gov.cn': {'name': 'China', 'code': 'CHN'},
            'mofa.go.jp': {'name': 'Japan', 'code': 'JPN'},
            'hikorea.go.kr': {'name': 'South Korea', 'code': 'KOR'},
            'dha.gov.za': {'name': 'South Africa', 'code': 'ZAF'},
            'immigration.govt.nz': {'name': 'New Zealand', 'code': 'NZL'},
            'ica.gov.sg': {'name': 'Singapore', 'code': 'SGP'},
            'dfa.gov.ph': {'name': 'Philippines', 'code': 'PHL'}
        }
        
        for domain, country_info in country_mapping.items():
            if domain in url_lower:
                return country_info
        
        return None
    
    def _get_smart_default(self, field: str, doc_info: Dict, extracted_data: Dict) -> str:
        """Get smart defaults based on context"""
        
        url = doc_info.get('download_url', doc_info.get('url', ''))
        
        defaults = {
            'form_name': doc_info.get('title', 'Immigration Document'),
            'form_id': self._extract_form_id_from_url(url, doc_info.get('filename', '')),
            'country_name': 'Unknown',
            'category': 'Immigration',
            'governing_authority': self._map_authority_from_url(url),
            'target_applicants': 'Immigration applicants',
            'form_description': f"Immigration document from {doc_info.get('source_domain', 'government source')}",
            'supporting_documents': 'Refer to official instructions',
            'submission_method': 'Refer to official instructions',
            'processing_time': 'Varies',
            'fees': 'Refer to official fee schedule',
            'language': 'English',
            'notes_or_instructions': 'Please refer to the official source for complete instructions',
            'full_markdown_summary': f"# {extracted_data.get('form_name', 'Immigration Document')}\n\nThis document was processed from {url}\n\nFor complete information, please refer to the original source."
        }
        
        return defaults.get(field, 'N/A')
    
    def _create_fallback_response(self, doc_info: Dict, error_reason: str) -> Dict[str, Any]:
        """Create a fallback response when AI extraction fails"""
        
        url = doc_info.get('download_url', doc_info.get('url', ''))
        
        return {
            "form_name": doc_info.get('title', 'Unknown Document'),
            "form_slug": "unknown-document",
            "form_id": self._extract_form_id_from_url(url, doc_info.get('filename', '')),
            "country_code": "UNK",
            "country_name": "Unknown",
            "category": "Unknown",
            "governing_authority": self._map_authority_from_url(url),
            "target_applicants": "N/A",
            "form_description": doc_info.get('description', 'Document description not available'),
            "required_fields": [],
            "supporting_documents": "N/A",
            "submission_method": "N/A",
            "processing_time": "N/A",
            "fees": "N/A",
            "language": "Unknown",
            "notes_or_instructions": f"AI extraction failed: {error_reason}",
            "extracted_text_length": 0,
            "extraction_timestamp": datetime.now().isoformat(),
            "ai_service_used": self.active_service or "None",
            "extraction_error": error_reason,
            "full_markdown_summary": f"""# {doc_info.get('title', 'Unknown Document')}

**Source:** {url}

**Note:** This document could not be fully processed by AI services.

**Error:** {error_reason}

Please refer to the original source for complete information.
"""
        }
    
    def validate_form_data(self, form_data: Dict) -> List[str]:
        """Validate extracted form data and return warnings"""
        
        warnings = []
        
        # Check for missing critical fields
        critical_fields = ['form_name', 'governing_authority', 'country_name']
        for field in critical_fields:
            if not form_data.get(field) or form_data[field] in ['N/A', 'Unknown', '']:
                warnings.append(f"Missing or unclear {field}")
        
        # Check for generic/placeholder values
        generic_values = ['N/A', 'Unknown', 'Refer to official instructions', 'Varies']
        for field, value in form_data.items():
            if isinstance(value, str) and value in generic_values:
                warnings.append(f"{field} contains generic placeholder value")
        
        # Check required_fields structure
        if 'required_fields' in form_data:
            if not isinstance(form_data['required_fields'], list):
                warnings.append("required_fields should be a list")
            elif len(form_data['required_fields']) == 0:
                warnings.append("No required fields identified")
        
        # Check for extraction errors
        if form_data.get('extraction_error'):
            warnings.append(f"AI extraction error: {form_data['extraction_error']}")
        
        return warnings
