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

        # Display format distribution for transparency
        if unique_results:
            format_counts = {}
            for result in unique_results:
                file_type = result.get('file_type', 'UNKNOWN')
                format_counts[file_type] = format_counts.get(file_type, 0) + 1

            format_summary = ", ".join([f"{fmt}: {count}" for fmt, count in sorted(format_counts.items())])
            st.success(f"Found {len(unique_results)} potential documents/pages")
            st.info(f"📊 **Format Distribution:** {format_summary}")
        else:
            st.warning("No relevant documents found")

        return unique_results
    
    def _generate_search_queries(self, country: str, visa_type: str) -> List[str]:
        """Generate comprehensive search queries targeting ALL critical document formats equally."""

        # Queries explicitly targeting different document formats
        queries = [
            # PDF-focused queries (often contain official forms and comprehensive guides)
            f"{country} {visa_type} visa application forms PDF official government",
            f"{country} immigration {visa_type} requirements PDF guide government",
            f"{country} {visa_type} visa checklist PDF official documents",
            f"{country} {visa_type} visa instructions PDF embassy consulate",

            # Excel/Spreadsheet-focused queries (often contain fee schedules, requirements matrices)
            f"{country} {visa_type} visa fee schedule Excel official government",
            f"{country} immigration {visa_type} requirements spreadsheet official",
            f"{country} {visa_type} visa document checklist Excel government",

            # Word document queries (often contain detailed application guides)
            f"{country} {visa_type} visa application guide DOCX official",
            f"{country} immigration {visa_type} instructions Word document official",
            f"{country} {visa_type} visa manual DOCX government guide",

            # General document queries (catch downloadable files)
            f"{country} {visa_type} visa documents download official government",
            f"{country} immigration {visa_type} official documents PDF DOCX Excel",
            f"{country} {visa_type} visa application package download official",

            # Web-based information (but lower priority)
            f"{country} {visa_type} visa eligibility guide government website",
            f"{country} {visa_type} visa application process official site",
            f"{country} official immigration website {visa_type} documents"
        ]

        # Format-specific queries for common visa types
        if "family" in visa_type.lower():
            queries.extend([
                f"{country} family reunification visa forms PDF official",
                f"{country} spouse visa requirements Excel checklist government"
            ])
        if "work" in visa_type.lower():
            queries.extend([
                f"{country} work permit application forms PDF official",
                f"{country} work visa requirements DOCX guide government"
            ])
        if "student" in visa_type.lower():
            queries.extend([
                f"{country} student visa application forms PDF official",
                f"{country} student visa requirements Excel government"
            ])

        # Prioritize diversity and limit to reasonable number
        return list(set(queries))[:18]  # Increased to capture more format diversity
    
    def _search_tavily(self, query: str, country: str) -> List[Dict]: # Now accepts country
        """Execute search using Tavily API, with dynamic domain filtering."""
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",  # Deeper search for more comprehensive results
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 20,  # Increased to find more diverse document types
            "include_images": False,  # Focus on documents, not images
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
        Enhanced relevance detection prioritizing ALL critical document formats equally.
        """
        url_lower = url.lower()
        title_lower = title.lower()
        content_lower = content.lower()

        # PRIORITY 1: Direct document formats - these are almost always relevant if from official sources
        high_value_formats = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.ppt', '.pptx']
        if any(url_lower.endswith(ext) or ext in url_lower for ext in high_value_formats):
            # Additional relevance check for document files
            critical_doc_terms = [
                'visa', 'immigration', 'form', 'application', 'petition', 'guide',
                'instruction', 'manual', 'requirements', 'checklist', 'schedule',
                'fee', 'eligibility', 'process', 'citizenship', 'residence'
            ]
            if any(term in title_lower or term in content_lower for term in critical_doc_terms):
                return True

            # For official domains, be more lenient with document files
            domain = urlparse(url).netloc.lower()
            if any(indicator in domain for indicator in ['gov', 'official', 'embassy', 'consulate']):
                return True

        # PRIORITY 2: Comprehensive keyword relevance for all content types
        # Core immigration terms (high relevance)
        core_immigration_terms = [
            'visa', 'immigration', 'immigrant', 'nonimmigrant', 'citizenship',
            'residence', 'passport', 'permit', 'travel', 'border'
        ]

        # Document-specific terms (high relevance)
        document_terms = [
            'form', 'application', 'petition', 'requirements', 'instructions',
            'guide', 'manual', 'checklist', 'schedule', 'fees', 'eligibility'
        ]

        # Official source terms (medium relevance)
        official_terms = [
            'government', 'ministry', 'department', 'authority', 'consulate',
            'embassy', 'official', 'federal', 'national', 'state'
        ]

        # Calculate relevance score
        relevance_score = 0

        # Check title (weighted higher)
        for term in core_immigration_terms:
            if term in title_lower:
                relevance_score += 3
        for term in document_terms:
            if term in title_lower:
                relevance_score += 2
        for term in official_terms:
            if term in title_lower:
                relevance_score += 1

        # Check content (weighted lower but still important)
        for term in core_immigration_terms:
            if term in content_lower:
                relevance_score += 2
        for term in document_terms:
            if term in content_lower:
                relevance_score += 1

        # High relevance threshold
        if relevance_score >= 3:
            return True

        # PRIORITY 3: Special handling for HTML pages (stricter requirements)
        if url_lower.endswith(('.html', '.htm', '.php', '.asp', '.aspx')):
            domain = urlparse(url).netloc.lower()

            # Exclude non-official domains for HTML content
            excluded_domains = [
                'blog', 'news', 'forum', 'wikipedia', 'quora', 'youtube',
                'medium', 'reddit', 'facebook', 'twitter', 'linkedin',
                'stackexchange', 'pinterest', 'instagram'
            ]
            if any(excluded in domain for excluded in excluded_domains):
                return False

            # For HTML, require stronger immigration relevance AND official-looking domain
            has_strong_immigration_terms = any(term in title_lower or term in content_lower
                                             for term in core_immigration_terms)
            has_official_domain = any(indicator in domain
                                    for indicator in ['gov', '.edu', 'official', 'embassy', 'consulate'])

            return has_strong_immigration_terms and (has_official_domain or relevance_score >= 4)

        return False
    
    def _extract_file_type(self, url: str, title: str) -> str:
        """Enhanced file type detection for comprehensive format recognition."""
        url_lower = url.lower()
        title_lower = title.lower()

        # Enhanced format detection with better pattern matching
        format_patterns = {
            'PDF': ['.pdf', 'pdf', 'portable document'],
            'DOCX': ['.docx', 'docx', 'word document', 'microsoft word'],
            'DOC': ['.doc', ' doc ', 'word doc'],
            'XLSX': ['.xlsx', 'xlsx', 'excel', 'spreadsheet', 'microsoft excel'],
            'XLS': ['.xls', ' xls ', 'excel'],
            'PPT': ['.ppt', '.pptx', 'powerpoint', 'presentation'],
            'TXT': ['.txt', 'text file'],
            'RTF': ['.rtf', 'rich text']
        }

        # Check URL and title for format indicators
        for format_type, patterns in format_patterns.items():
            for pattern in patterns:
                if pattern in url_lower or pattern in title_lower:
                    return format_type

        # Check for HTML/web pages
        if url_lower.endswith(('.html', '.htm', '.php', '.asp', '.aspx')) or \
           not any(ext in url_lower for ext in ['.pdf', '.doc', '.xls', '.ppt', '.txt']):
            return "HTML"

        return "UNKNOWN"

    def _deduplicate_and_filter_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and filter for best results, with balanced prioritization of ALL critical formats."""
        seen_urls = set()
        unique_results = []

        def get_document_priority_score(result):
            """Calculate priority score for balanced document format representation."""
            score = 0
            file_type = result.get('file_type', '').upper()
            title = result.get('title', '').lower()
            domain = result.get('source_domain', '').lower()

            # BALANCED FORMAT SCORING - All critical formats get high scores
            format_scores = {
                'PDF': 100,      # Official forms, guides, instructions
                'DOCX': 95,      # Detailed application guides, manuals
                'DOC': 90,       # Legacy Word documents with instructions
                'XLSX': 95,      # Fee schedules, requirement matrices, checklists
                'XLS': 90,       # Legacy Excel with important data
                'HTML': 60       # Web information (lower but still valuable)
            }
            score += format_scores.get(file_type, 30)

            # CONTENT RELEVANCE SCORING - Higher priority for core immigration terms
            high_value_terms = ['form', 'application', 'instruction', 'guide', 'manual',
                              'checklist', 'requirements', 'fees', 'schedule', 'petition']
            medium_value_terms = ['visa', 'immigration', 'eligibility', 'process', 'documents']

            for term in high_value_terms:
                if term in title:
                    score += 20
            for term in medium_value_terms:
                if term in title:
                    score += 10

            # OFFICIAL SOURCE BONUS - Government and official domains get priority
            official_indicators = ['gov', '.edu', 'official', 'embassy', 'consulate']
            for indicator in official_indicators:
                if indicator in domain:
                    score += 25
                    break

            # CONTENT LENGTH BONUS - More detailed content typically more valuable
            description_length = len(result.get('description', ''))
            if description_length > 300:
                score += 15
            elif description_length > 150:
                score += 10

            return score

        # Sort by comprehensive priority score rather than simple format hierarchy
        results.sort(key=get_document_priority_score, reverse=True)

        # Ensure format diversity in final results
        format_counts = {}
        for result in results:
            url = result.get("url", "")
            file_type = result.get('file_type', 'UNKNOWN')

            if url not in seen_urls and len(unique_results) < 30:  # Increased limit for better diversity
                # Limit each format to prevent over-representation
                max_per_format = {'PDF': 10, 'DOCX': 8, 'DOC': 6, 'XLSX': 8, 'XLS': 6, 'HTML': 12}
                current_count = format_counts.get(file_type, 0)

                if current_count < max_per_format.get(file_type, 5):
                    seen_urls.add(url)
                    unique_results.append(result)
                    format_counts[file_type] = current_count + 1

        return unique_results
