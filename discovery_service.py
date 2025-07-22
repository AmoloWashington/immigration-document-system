import requests
from typing import List, Dict, Any
import streamlit as st
from urllib.parse import urlparse
import os
import time
from document_processor import DocumentProcessor
from database import DatabaseManager

class DocumentDiscoveryService:
    # Comprehensive mapping of countries to their primary official immigration/government domains
    # This list can be expanded over time as needed.
    COUNTRY_DOMAINS_MAP = {
        "USA": [
            "uscis.gov", "state.gov", "travel.state.gov", "cbp.gov", "ice.gov", "dhs.gov", 
            "dol.gov", "justice.gov" # Dept of Labor, Justice
        ],
        "Canada": [
            "canada.ca", "cic.gc.ca", "ircc.canada.ca" # Immigration, Refugees and Citizenship Canada
        ],
        "UK": [
            "gov.uk", "homeoffice.gov.uk" # Home Office
        ],
        "Australia": [
            "homeaffairs.gov.au", "immi.homeaffairs.gov.au" # Department of Home Affairs
        ],
        "Germany": [
            "bamf.de", "auswaertiges-amt.de", "make-it-in-germany.com" # Federal Office for Migration and Refugees, Federal Foreign Office
        ],
        "France": [
            "france-visas.gouv.fr", "interieur.gouv.fr", "diplomatie.gouv.fr" # Official visa portal, Ministry of Interior, Ministry for Europe and Foreign Affairs
        ],
        "United Arab Emirates": [
            "mohre.gov.ae", "gdrfad.gov.ae", "uaecabinet.ae", "government.ae", "mofaic.gov.ae" # Ministry of Human Resources & Emiratisation, GDRFA, UAE Cabinet
        ],
        "India": [
            "indianvisaonline.gov.in", "mea.gov.in", "mha.gov.in", "boi.gov.in" # Indian Visa Online, Ministry of External Affairs, Home Affairs, Bureau of Immigration
        ],
        "Mexico": [
            "inm.gob.mx", "gob.mx/inm" # National Migration Institute (INM)
        ],
        "Brazil": [
            "gov.br/mre", "gov.br/mj" # Ministry of Foreign Affairs, Ministry of Justice
        ],
        "China": [
            "nia.gov.cn", "mps.gov.cn" # National Immigration Administration, Ministry of Public Security
        ],
        "Japan": [
            "moj.go.jp/isa", "mofa.go.jp/j_info/visit/visa" # Immigration Services Agency, Ministry of Foreign Affairs
        ],
        "South Korea": [
            "immigration.go.kr", "moj.go.kr" # Korea Immigration Service, Ministry of Justice
        ],
        "South Africa": [
            "dha.gov.za" # Department of Home Affairs
        ],
        "New Zealand": [
            "immigration.govt.nz" # Immigration New Zealand
        ],
        "Singapore": [
            "ica.gov.sg" # Immigration & Checkpoints Authority
        ],
        "Philippines": [
            "immigration.gov.ph", "dfa.gov.ph" # Bureau of Immigration, Department of Foreign Affairs
        ]
        # Continue adding more countries and their key official domains here
    }

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
                # Pass country to the search method to allow dynamic domain filtering
                results = self._search_tavily(query, country) 
                
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
        """Generate comprehensive search queries for document and information discovery,
        now explicitly guiding towards official sources to complement domain filtering."""
        
        # Queries for forms and official information
        queries = [
            f"{country} {visa_type} visa application forms official government",
            f"{country} immigration {visa_type} requirements PDF official",
            f"{country} {visa_type} visa eligibility guide government website",
            f"{country} {visa_type} visa application process official site",
            f"{country} {visa_type} visa supporting documents government",
            f"{country} ministry of immigration {visa_type} visa",
            f"{country} department of home affairs {visa_type} visa information",
            f"{country} official immigration website {visa_type}",
            f"{country} embassy {visa_type} visa application", # Added embassy/consulate terms
            f"{country} consulate {visa_type} visa application"
        ]

        # Specific queries for common visa types if selected
        if "family" in visa_type.lower():
            queries.append(f"{country} family reunification visa requirements official")
            queries.append(f"{country} spouse visa application process government")
        if "work" in visa_type.lower():
            queries.append(f"{country} work permit application guide official")
        if "student" in visa_type.lower():
            queries.append(f"{country} student visa application checklist government")
        
        # Limit to a reasonable number of diverse queries
        return list(set(queries))[:12] # Increased limit for more diverse results
    
    def _search_tavily(self, query: str, country: str) -> List[Dict]: # Now accepts country
        """Execute search using Tavily API, with dynamic domain filtering."""
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic", 
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 15, 
        }

        # Dynamically set include_domains based on country
        if country in self.COUNTRY_DOMAINS_MAP:
            payload["include_domains"] = self.COUNTRY_DOMAINS_MAP[country]
            st.info(f"Filtering search to official domains for {country}: {', '.join(payload['include_domains'])}")
        else:
            # For "Other" countries or those not in map, search broadly with a warning
            st.warning(f"Country '{country}' not in predefined official domains map. Searching broadly without domain filter, results may be less precise.")
            # No 'include_domains' key in payload means Tavily searches all domains
        
        response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
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
                st.warning(f"Skipping inaccessible or invalid URL '{url}' (Status: {status_code}, Error: {error_msg})")
                continue
            
            # Now, determine if it's a relevant document or informational page
            # This relevance check acts as a final filter on the content, even if domain was correct
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
        # Always include direct document links (PDF, DOCX, etc.)
        if any(url.lower().endswith(ext) for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']):
            return True
        
        # Keywords indicating relevance for informational pages
        # Expanded to include more terms for immigration and official bodies
        relevant_keywords = [
            'visa', 'immigration', 'form', 'application', 'petition', 'requirements',
            'eligibility', 'process', 'guide', 'checklist', 'instructions', 'official',
            'government', 'ministry', 'department', 'authority', 'consulate', 'embassy',
            'citizenship', 'residence', 'passport', 'permit', 'travel'
        ]
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        # Check if any relevant keyword is in the title or content
        if any(keyword in title_lower for keyword in relevant_keywords):
            return True
        if any(keyword in content_lower for keyword in relevant_keywords):
            return True
        
        # Specific check for HTML pages: must contain core immigration terms AND be from a somewhat official-looking domain
        if url.lower().endswith(('.html', '.htm')):
            domain = urlparse(url).netloc.lower()
            # Basic check to exclude common non-official domains (blogs, news, forums)
            if any(s in domain for s in ['blog', 'news', 'forum', 'wikipedia', 'quora', 'youtube', 'medium', 'reddit', 'facebook', 'twitter', 'linkedin', 'stackexchange']):
                return False

            # Further check for core immigration terms in title or content for HTML pages
            if any(term in title_lower for term in ['immigrant', 'nonimmigrant', 'citizen', 'residence', 'travel', 'visa']):
                return True
            if any(term in content_lower for term in ['immigrant', 'nonimmigrant', 'citizen', 'residence', 'travel', 'visa']):
                return True

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
        # Improved sorting to prioritize official sources and detailed content
        results.sort(key=lambda x: (
            x['file_type'] == 'PDF',        # PDFs first (most likely official forms)
            x['file_type'] == 'DOCX',       # DOCX second
            x['file_type'] == 'HTML' and 'gov' in x['source_domain'].lower() or 'org' in x['source_domain'].lower(), # Official HTML sources
            'form' in x['title'].lower() or 'application' in x['title'].lower(),   # Forms/applications in title
            len(x['description'])           # More description usually means more content
        ), reverse=True)
        
        for result in results:
            url = result.get("url", "")
            if url not in seen_urls and len(unique_results) < 25:  # Increased limit to 25 best results for more breadth
                seen_urls.add(url)
                unique_results.append(result)
        
        return unique_results
