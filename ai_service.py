import openai
import google.generativeai as genai
from typing import Dict, Any, List, Tuple, Optional
import json
import streamlit as st
from datetime import datetime
import re # For extracting potential JSON from Markdown if needed (future proofing)

class AIExtractionService:
    def __init__(self, openai_api_key: str, openrouter_api_key: str = None, gemini_api_key: str = None):
        self.openai_client = None
        self.openrouter_client = None
        self.gemini_model = None # Using model directly for Gemini

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

        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') # Use a capable Gemini model
                st.success("Gemini client initialized.")
            except Exception as e:
                st.error(f"Error configuring Gemini API: {e}. Gemini service will be unavailable.")
                self.gemini_model = None
        else:
            st.warning("Gemini API key not configured. Gemini fallback will be unavailable.")

        if not self.openai_client and not self.openrouter_client and not self.gemini_model:
            st.error("No AI service clients initialized. AI processing will fail.")
    
    def _call_openai_compatible_service(self, client: openai.OpenAI, system_prompt: str, user_prompt: str, model_name: str, max_tokens: int, response_format: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Helper to call OpenAI-compatible clients (OpenAI, OpenRouter)."""
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
                max_tokens=max_tokens,
                response_format=response_format
            )
            return response.choices[0].message.content, None
        except openai.APIStatusError as e:
            return None, f"API error (Status {e.status_code}): {e.response}"
        except Exception as e:
            return None, f"Unexpected error: {e}"

    def _call_gemini_service(self, model: genai.GenerativeModel, system_prompt: str, user_prompt: str, max_tokens: int) -> Tuple[Optional[str], Optional[str]]:
        """Helper to call Gemini service."""
        if not model:
            return None, "Gemini model not initialized."
        try:
            # Gemini's system instructions are part of the prompt in earlier versions
            # Or can be set using tools, but for simple text, often combined or set in prompt.
            # For JSON output, it's best to guide it strongly in the prompt.
            combined_prompt = f"System Instruction: {system_prompt}\n\nUser Query: {user_prompt}"
            
            # Use generation_config for max_tokens and response_mime_type (for JSON)
            generation_config = {
                "temperature": 0.1,
                "max_output_tokens": max_tokens,
                "response_mime_type": "application/json" # Explicitly request JSON for Gemini
            }

            response = model.generate_content(
                combined_prompt,
                generation_config=generation_config
            )
            return response.text, None
        except Exception as e:
            return None, f"Gemini error: {e}"

    def extract_form_data(self, document_text: str, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured form data and a detailed Markdown summary using AI."""
        
        if not self.openai_client and not self.openrouter_client and not self.gemini_model:
            st.error("AI service not initialized due to missing API keys.")
            return {}
        
        if not document_text or len(document_text.strip()) < 50:
            st.error("Insufficient text content for AI processing (min 50 chars required).")
            return {}
        
        # Define the desired JSON schema for the AI's output
        # It includes both structured fields AND a full_markdown_summary
        json_schema = {
            "country": "Country name (e.g., USA, Canada)",
            "visa_category": "Type of visa/immigration category (e.g., Work Visa, Student Visa)",
            "form_name": "Official form name (e.g., Petition for a Nonimmigrant Worker)",
            "form_id": "Official form number/ID (e.g., I-129)",
            "description": "Brief, concise description of the form's purpose.",
            "governing_authority": "Government agency responsible (e.g., USCIS, IRCC)",
            "target_applicants": "Who should use this form (e.g., Employers filing for nonimmigrant workers)",
            "required_fields": [{"name": "field name", "type": "text/number/date/etc", "description": "field description", "example_value": "example data"}],
            "supporting_documents": ["list of required supporting documents (e.g., Passport, Birth Certificate)"],
            "submission_method": "How to submit the form (e.g., Online, Mail, In-person)",
            "processing_time": "Expected processing time (e.g., 6-12 months, 30 days)",
            "fees": "Required fees (e.g., $460, Varies)",
            "language": "Primary language of the document (e.g., English, French)",
            "full_markdown_summary": "A comprehensive, detailed summary of the document, formatted in Markdown. This field should elaborate on all aspects of the form, including its purpose, detailed instructions, eligibility, process, and any other relevant information found in the document, even if it doesn't fit into the structured fields above. Use Markdown headings (##, ###), lists, and bold text for clarity and readability. Ensure this summary is exhaustive and captures all nuances, acting as the primary source of truth for detailed document intelligence. If information is found that doesn't fit the specific structured keys, include it here."
        }

        system_prompt = f"""You are an expert immigration document analyzer. Your task is to extract highly detailed and structured information from immigration forms and documents.

Return a JSON object that strictly adheres to the following schema.
For the "full_markdown_summary" field, provide an extensive summary of the document, formatted in Markdown, capturing ALL available details, instructions, and nuances. For other fields, be concise.

JSON Schema:
{json.dumps(json_schema, indent=2)}

Be thorough, accurate, and comprehensive. If information is not available for a specific structured field, use null or empty values, but ensure the 'full_markdown_summary' is always populated with meaningful content about the document. Ensure the entire output is a valid JSON object."""

        # Truncate text to avoid token limits
        max_text_length = 6000
        if len(document_text) > max_text_length:
            document_text = document_text[:max_text_length] + "\n... [Document text truncated due to length]"

        user_prompt = f"""Analyze this immigration document and extract structured information and a comprehensive Markdown summary:

Document Info:
- Filename: {document_info.get('filename', 'Unknown')}
- Source URL: {document_info.get('download_url', 'Unknown')}
- File Type: {document_info.get('file_format', 'Unknown')}

Document Text:
{document_text}

Extract all relevant information according to the JSON schema provided in the system prompt. Pay special attention to populating the 'full_markdown_summary' field with all details from the document, using proper Markdown formatting."""

        response_content = None
        error_message = None

        # Try OpenAI first
        if self.openai_client:
            st.info("Attempting AI extraction with OpenAI...")
            response_content, error_message = self._call_openai_compatible_service(
                self.openai_client, system_prompt, user_prompt, model_name="gpt-4o-mini", max_tokens=2500, response_format={"type": "json_object"}
            )
            if response_content:
                st.success("AI extraction successful using OpenAI.")
            else:
                st.warning(f"OpenAI extraction failed: {error_message}. Attempting OpenRouter fallback...")
        
        # Fallback to OpenRouter if OpenAI failed or was not available
        if not response_content and self.openrouter_client:
            st.info("Attempting AI extraction with OpenRouter...")
            response_content, error_message = self._call_openai_compatible_service(
                self.openrouter_client, system_prompt, user_prompt, model_name="openai/gpt-4o-mini", max_tokens=2500, response_format={"type": "json_object"}
            ) # Use OpenRouter's model name convention
            if response_content:
                st.success("AI extraction successful using OpenRouter fallback.")
            else:
                st.warning(f"OpenRouter extraction also failed: {error_message}. Attempting Gemini fallback...")
        
        # Fallback to Gemini if OpenRouter failed or was not available
        if not response_content and self.gemini_model:
            st.info("Attempting AI extraction with Gemini...")
            response_content, error_message = self._call_gemini_service(
                self.gemini_model, system_prompt, user_prompt, max_tokens=2500
            ) # Gemini handles JSON response directly via generation_config
            if response_content:
                st.success("AI extraction successful using Gemini fallback.")
            else:
                st.error(f"Gemini extraction also failed: {error_message}.")

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
        """Validate extracted form data and return warnings using AI with fallback."""
        
        if not self.openai_client and not self.openrouter_client and not self.gemini_model:
            return ["AI validation skipped due to missing API keys."]
        
        # Use the full_markdown_summary if available for comprehensive validation context
        context_data = form_data.get('full_markdown_summary', json.dumps(form_data, indent=2))

        validation_prompt = f"""Review this extracted immigration form data for completeness and accuracy:

{context_data}

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
            response_content, error_message = self._call_openai_compatible_service(
                self.openai_client, 
                "You are an expert immigration document validator. Respond only with a JSON array named 'validation_warnings'.", 
                validation_prompt, 
                model_name="gpt-4o-mini", 
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            if response_content:
                st.success("AI validation successful using OpenAI.")
            else:
                st.warning(f"OpenAI validation failed: {error_message}. Attempting OpenRouter fallback...")
        
        # Fallback to OpenRouter if OpenAI failed or was not available
        if not response_content and self.openrouter_client:
            st.info("Attempting AI validation with OpenRouter...")
            response_content, error_message = self._call_openai_compatible_service(
                self.openrouter_client, 
                "You are an expert immigration document validator. Respond only with a JSON array named 'validation_warnings'.", 
                validation_prompt, 
                model_name="openai/gpt-4o-mini", 
                max_tokens=800,
                response_format={"type": "json_object"}
            )
            if response_content:
                st.success("AI validation successful using OpenRouter fallback.")
            else:
                st.warning(f"OpenRouter validation also failed: {error_message}. Attempting Gemini fallback...")
        
        # Fallback to Gemini if OpenRouter failed or was not available
        if not response_content and self.gemini_model:
            st.info("Attempting AI validation with Gemini...")
            response_content, error_message = self._call_gemini_service(
                self.gemini_model, 
                "You are an expert immigration document validator. Respond only with a JSON object containing a 'validation_warnings' array.", 
                validation_prompt, 
                max_tokens=800
            ) # Gemini explicitly requests JSON via response_mime_type
            if response_content:
                st.success("AI validation successful using Gemini fallback.")
            else:
                st.error(f"Gemini validation also failed: {error_message}.")

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
