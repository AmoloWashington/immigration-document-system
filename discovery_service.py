import requests
from typing import List, Dict, Any
import streamlit as st
from urllib.parse import urlparse
import os
import time
from document_processor import DocumentProcessor
from database import DatabaseManager

class DocumentDiscoveryService:
    def __init__(self, api_key: str, processor: DocumentProcessor, db_manager: DatabaseManager):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com/search"
        self.processor = processor
        self.db_manager = db_manager
    
    def discover_documents(self, country: str, visa_type: str) -> List[Dict[str, Any]]:
        """Discover immigration documents and relevant informational pages using Tavily API"""
        
        if not self.api_key:
            st.error("Tavily API key not configured!")
            return []
        
        queries = self._generate_search_queries(country, visa_type)
        
        all_results = []
        
        for query in queries:
            try:
                st.info(f"Searching: {query}")
                results = self._search_tavily(query)
                
                # Filter for relevant links and validate URLs
                document_results = self._filter_document_results(results, query)
                all_results.extend(document_results)
                
                # Add small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                st.error(f"Error searching '{query}': {e}")
        
        # Deduplicate and filter results
        unique_results = self._deduplicate_and_filter_results(all_results)
        
        st.success(f"Found {len(unique_results)} potential documents/information pages")
        return unique_results
    
    def _generate_search_queries(self, country: str, visa_type: str) -> List[str]:
        """Generate comprehensive search queries for document and information discovery"""
        
        # Base queries for forms
        queries = [
            f"{country} {visa_type} visa application forms official",
            f"{country} immigration {visa_type} requirements PDF",
            f"{country} {visa_type} visa eligibility guide",
        ]
        
        # Add more general informational queries
        queries.extend([
            f"{country} {visa_type} visa application process",
            f"{country} {visa_type} visa supporting documents",
            f"{country} immigration official website {visa_type}",
            f"{country} government {visa_type} visa information",
        ])

        # Specific queries for common visa types if selected
        if "family" in visa_type.lower():
            queries.append(f"{country} family reunification visa requirements")
            queries.append(f"{country} spouse visa application process")
        if "work" in visa_type.lower():
            queries.append(f"{country} work permit application guide")
        if "student" in visa_type.lower():
            queries.append(f"{country} student visa application checklist")
        
        # Limit to a reasonable number of diverse queries
        return list(set(queries))[:8] # Use set to remove duplicates, limit to 8 for efficiency
    
    def _search_tavily(self, query: str) -> List[Dict]:
        """Execute search using Tavily API"""
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic", # Basic search is usually sufficient for initial discovery
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 10, # Increase max results to get more options
            "include_domains": [ # Keep to official government domains for reliability
                "uscis.gov", "state.gov", "travel.state.gov", "cbp.gov", "ice.gov", "dhs.gov",
                "canada.ca", "cic.gc.ca", # Canada
                "gov.uk", "homeoffice.gov.uk", # UK
                "immi.homeaffairs.gov.au", # Australia
                "bamf.de", "auswaertiges-amt.de", # Germany
                "france-visas.gouv.fr", # France
                # Add more official domains as needed for other countries
            ]
        }
        
        response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.json().get("results", [])
    
    def _filter_document_results(self, results: List[Dict], query: str) -> List[Dict[str, Any]]:
        """Filter results to find downloadable documents and relevant informational pages, validating their URLs."""
        
        document_results = []
        
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            
            # Validate URL accessibility before considering it
            is_valid, status_code, error_msg = self.processor.validate_url(url)
            if not is_valid:
                st.warning(f"Skipping invalid URL '{url}' (Status: {status_code}, Error: {error_msg})")
                continue
            
            # Now, determine if it's a relevant document or informational page
            if not self._is_relevant_page(url, title, content):
                continue
            
            document_results.append({
                "id": f"doc_{abs(hash(url))}",
                "title": title,
                "description": content[:500] + "..." if len(content) > 500 else content, # Capture more description
                "url": url,
                "source_domain": urlparse(url).netloc,
                "discovered_by_query": query,
                "file_type": self._extract_file_type(url, title) # This will now correctly identify HTML too
            })
            
            # Insert into sources table for all relevant discovered URLs
            if self.db_manager:
                self.db_manager.insert_source(url, title, content, urlparse(url).netloc)
        
        return document_results
    
    def _is_relevant_page(self, url: str, title: str, content: str) -> bool:
        """
        Determines if a page is relevant for immigration intelligence,
        including direct documents and informational HTML pages.
        """
        # Always include direct document links
        if any(url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']):
            return True
        
        # Keywords indicating relevance for informational pages
        relevant_keywords = [
            'visa', 'immigration', 'form', 'application', 'petition', 'requirements',
            'eligibility', 'process', 'guide', 'checklist', 'instructions', 'official'
        ]
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Check if any relevant keyword is in the title or content
        if any(keyword in title_lower for keyword in relevant_keywords):
            return True
        if any(keyword in content_lower for keyword in relevant_keywords):
            return True
        
        # If it's an HTML page and contains general immigration terms, consider it relevant
        if url.lower().endswith(('.html', '.htm')):
            if any(term in title_lower for term in ['immigrant', 'nonimmigrant', 'citizen', 'residence', 'travel']):
                return True
            if any(term in content_lower for term in ['immigrant', 'nonimmigrant', 'citizen', 'residence', 'travel']):
                return True

        # If it's a general page from an official domain, but no specific keywords,
        # we might still want to include it if it's not clearly irrelevant.
        # For now, rely on keywords to avoid too much noise.
        
        return False # Default to not relevant if no strong indicators
    
    def _extract_file_type(self, url: str, title: str) -> str:
        """Extract likely file type from URL or title, including HTML."""
        for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']:
            if ext in url.lower() or ext in title.lower():
                return ext.replace('.', '').upper()
        if url.lower().endswith(('.html', '.htm')):
            return "HTML"
        return "UNKNOWN" # Default if no clear type found

    def _deduplicate_and_filter_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and filter for best results, prioritizing forms and then comprehensive info."""
        seen_urls = set()
        unique_results = []
        
        # Sort by relevance: direct documents > HTML info pages > others
        results.sort(key=lambda x: (
            x['file_type'] == 'PDF',        # PDFs first
            x['file_type'] == 'DOCX',       # DOCX second
            x['file_type'] == 'HTML',       # HTML info pages third
            'form' in x['title'].lower(),   # Forms in title
            len(x['description'])           # More description is better
        ), reverse=True)
        
        for result in results:
            url = result.get("url", "")
            if url not in seen_urls and len(unique_results) < 15:  # Increase limit to 15 best results
                seen_urls.add(url)
                unique_results.append(result)
        
        return unique_results
