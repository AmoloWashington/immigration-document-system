import openai
from typing import Dict, Any, List
import json
import streamlit as st
from datetime import datetime

class AIExtractionService:
    def __init__(self, openai_api_key: str, openrouter_api_key: str = None):
        self.openai_client = None
        self.openrouter_client = None

        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
            st.success("OpenAI client initialized.")
        else:
            st.warning("OpenAI API key not configured. OpenAI service will be unavailable.")
        
        if openrouter_api_key:
            self.openrouter_client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_api_key,
            )
            st.success("OpenRouter client initialized.")
        else:
            st.warning("OpenRouter API key not configured. OpenRouter fallback will be unavailable.")

        if not self.openai_client and not self.openrouter_client:
            st.error("No AI service clients initialized. AI processing will fail.")
    
    def _call_ai_service(self, client, system_prompt, user_prompt, model_name="gpt-4o-mini", max_tokens: int = 1500, response_format={"type": "json_object"}):
        """Helper to call a specific AI client."""
        if not client:
            return None, "AI client not initialized."
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=max_tokens, # Use the passed max_tokens parameter
                response_format=response_format
            )
            return response.choices[0].message.content, None
        except openai.APIStatusError as e:
            return None, f"API error (Status {e.status_code}): {e.response}"
        except Exception as e:
            return None, f"Unexpected error: {e}"

    def extract_form_data(self, document_text: str, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured form data using GPT-4 with OpenRouter fallback"""
        
        if not self.openai_client and not self.openrouter_client:
            st.error("AI service not initialized due to missing API keys.")
            return {}
        
        if not document_text or len(document_text.strip()) < 50:
            st.error("Insufficient text content for AI processing (min 50 chars required).")
            return {}
        
        system_prompt = """You are an expert immigration document analyzer. Extract structured information from immigration forms and documents.

Return a JSON object with the following schema:
{
    "country": "Country name",
    "visa_category": "Type of visa/immigration category",
    "form_name": "Official form name",
    "form_id": "Official form number/ID",
    "description": "Brief description of the form's purpose",
    "governing_authority": "Government agency responsible",
    "target_applicants": "Who should use this form",
    "required_fields": [{"name": "field name", "type": "text/number/date/etc", "description": "field description"}],
    "supporting_documents": ["list of required supporting documents"],
    "submission_method": "How to submit the form",
    "processing_time": "Expected processing time",
    "fees": "Required fees",
    "language": "Primary language of the document"
}

Be thorough and accurate. If information is not available, use null or empty values. Ensure the JSON is valid and complete."""

        # Truncate text to avoid token limits
        max_text_length = 6000
        if len(document_text) > max_text_length:
            document_text = document_text[:max_text_length] + "\n... [Document text truncated due to length]"

        user_prompt = f"""Analyze this immigration document and extract structured information:

Document Info:
- Filename: {document_info.get('filename', 'Unknown')}
- Source URL: {document_info.get('download_url', 'Unknown')}
- File Type: {document_info.get('file_format', 'Unknown')}

Document Text:
{document_text}

Extract all relevant information according to the JSON schema. Provide a valid JSON object."""

        response_content = None
        error_message = None

        # Try OpenAI first
        if self.openai_client:
            st.info("Attempting AI extraction with OpenAI...")
            response_content, error_message = self._call_ai_service(self.openai_client, system_prompt, user_prompt, max_tokens=1500) # Pass max_tokens
            if response_content:
                st.success("AI extraction successful using OpenAI.")
            else:
                st.warning(f"OpenAI extraction failed: {error_message}. Attempting OpenRouter fallback...")
        
        # Fallback to OpenRouter if OpenAI failed or was not available
        if not response_content and self.openrouter_client:
            response_content, error_message = self._call_ai_service(self.openrouter_client, system_prompt, user_prompt, max_tokens=1500) # Pass max_tokens
            if response_content:
                st.success("AI extraction successful using OpenRouter fallback.")
            else:
                st.error(f"OpenRouter extraction also failed: {error_message}.")
        
        if not response_content:
            st.error(f"AI extraction failed after trying all available services. Last error: {error_message}")
            return {}

        try:
            extracted_data = json.loads(response_content)
            
            # Add metadata
            extracted_data.update({
                "official_source_url": document_info.get('download_url'),
                "downloaded_file_path": document_info.get('file_path'),
                "document_format": document_info.get('file_format'),
                "last_fetched": datetime.now().isoformat(),
                "discovered_by_query": document_info.get('discovered_by_query', ''),
                "extracted_text_length": len(document_text)
            })
            
            st.success(f"AI extraction completed: {extracted_data.get('form_name', 'Unknown Form')}")
            return extracted_data
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing AI response as JSON: {e}")
            st.error(f"Raw response (first 500 chars): {response_content[:500]}...")
            return {}
        except Exception as e:
            st.error(f"Error processing extracted data: {e}")
            return {}
    
    def validate_form_data(self, form_data: Dict[str, Any]) -> List[str]:
        """Validate extracted form data and return warnings using GPT-4 with OpenRouter fallback"""
        
        if not self.openai_client and not self.openrouter_client:
            return ["AI validation skipped due to missing API keys."]
        
        validation_prompt = f"""Review this extracted immigration form data for completeness and accuracy:

{json.dumps(form_data, indent=2)}

Check for:
1. Missing required information (fees, processing times, submission methods)
2. Inconsistencies or contradictions
3. Unclear or ambiguous information
4. Potential errors in extraction

Return a JSON array of validation warnings. Each warning should be a clear, specific string describing the issue.
If no issues are found, return an empty array.

Example: ["Fee amount missing", "Processing time not specified", "Submission method unclear"]"""

        response_content = None
        error_message = None

        # Try OpenAI first
        if self.openai_client:
            st.info("Attempting AI validation with OpenAI...")
            response_content, error_message = self._call_ai_service(
                self.openai_client, 
                "You are an expert immigration document validator. Respond only with a JSON array.", 
                validation_prompt, 
                max_tokens=800 # Pass max_tokens
            )
            if response_content:
                st.success("AI validation successful using OpenAI.")
            else:
                st.warning(f"OpenAI validation failed: {error_message}. Attempting OpenRouter fallback...")
        
        # Fallback to OpenRouter if OpenAI failed or was not available
        if not response_content and self.openrouter_client:
            response_content, error_message = self._call_ai_service(
                self.openrouter_client, 
                "You are an expert immigration document validator. Respond only with a JSON array.", 
                validation_prompt, 
                max_tokens=800 # Pass max_tokens
            )
            if response_content:
                st.success("AI validation successful using OpenRouter fallback.")
            else:
                st.error(f"OpenRouter validation also failed: {error_message}.")
        
        if not response_content:
            st.error(f"AI validation failed after trying all available services. Last error: {error_message}")
            return [f"AI validation failed: {error_message}"]

        try:
            warnings_dict = json.loads(response_content)
            warnings = warnings_dict.get('validation_warnings', [])
            
            if isinstance(warnings, list):
                st.success(f"AI validation completed: {len(warnings)} warnings found")
                return warnings
            else:
                st.error(f"Validation response format error: Expected 'validation_warnings' to be a list within the JSON object. Received: {warnings_dict}")
                return [f"Validation response format error: {str(warnings_dict)}"]
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing validation response as JSON: {e}")
            st.error(f"Raw validation response (first 500 chars): {response_content[:500]}...")
            return [f"Validation parsing error: {str(e)}"]
        except Exception as e:
            st.error(f"Error processing validation data: {e}")
            return [f"Validation error: {str(e)}"]
