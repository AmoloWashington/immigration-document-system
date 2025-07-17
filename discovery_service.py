import requests
from typing import List, Dict, Any
import streamlit as st
from urllib.parse import urlparse
import os
import time

class DocumentDiscoveryService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com/search"
    
    def discover_documents(self, country: str, visa_type: str) -> List[Dict[str, Any]]:
        """Discover immigration documents using Tavily API"""
        
        if not self.api_key:
            st.error("Tavily API key not configured!")
            return []
        
        # Generate comprehensive search queries
        queries = self._generate_search_queries(country, visa_type)
        
        all_results = []
        
        for query in queries:
            try:
                st.info(f"Searching: {query}")
                results = self._search_tavily(query)
                
                # Filter for document links
                document_results = self._filter_document_results(results, query)
                all_results.extend(document_results)
                
                # Add small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                st.error(f"Error searching '{query}': {e}")
        
        # Deduplicate and filter results
        unique_results = self._deduplicate_and_filter_results(all_results)
        
        st.success(f"Found {len(unique_results)} potential documents")
        return unique_results
    
    def _generate_search_queries(self, country: str, visa_type: str) -> List[str]:
        """Generate comprehensive search queries for document discovery"""
        
        base_queries = [
            f"USCIS {visa_type} forms PDF download official",
            f"Form I-129 petition nonimmigrant worker PDF",
            f"Form I-765 employment authorization PDF",
            f"USCIS official forms {visa_type} download",
            f"{country} immigration {visa_type} application forms PDF"
        ]
        
        return base_queries[:4]  # Limit to 4 queries to save API calls
    
    def _search_tavily(self, query: str) -> List[Dict[str, Any]]:
        """Execute search using Tavily API"""
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": 5,
            "include_domains": [
                "uscis.gov",
                "state.gov", 
                "travel.state.gov",
                "cbp.gov",
                "ice.gov",
                "dhs.gov"
            ]
        }
        
        response = requests.post(self.base_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        return response.json().get("results", [])
    
    def _filter_document_results(self, results: List[Dict], query: str) -> List[Dict[str, Any]]:
        """Filter results to find downloadable documents"""
        
        document_results = []
        
        for result in results:
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")
            
            # Skip HTML pages that are not direct document links
            if not self._is_likely_document(url, title, content):
                continue
            
            document_results.append({
                "id": f"doc_{abs(hash(url))}",
                "title": title,
                "description": content[:300] + "..." if len(content) > 300 else content,
                "url": url,
                "source_domain": urlparse(url).netloc,
                "discovered_by_query": query,
                "file_type": self._extract_file_type(url, title)
            })
        
        return document_results
    
    def _is_likely_document(self, url: str, title: str, content: str) -> bool:
        """Check if this is likely a direct document link"""
        
        # Direct PDF links
        if url.lower().endswith('.pdf'):
            return True
        
        # Form-specific keywords in title
        form_keywords = ['form i-', 'form ds-', 'form g-', 'form n-', 'petition', 'application']
        title_lower = title.lower()
        
        if any(keyword in title_lower for keyword in form_keywords):
            return True
        
        # PDF or download mentioned in content
        content_lower = content.lower()
        if 'pdf' in content_lower and ('download' in content_lower or 'form' in content_lower):
            return True
        
        # Skip general information pages
        skip_keywords = ['overview', 'information', 'about', 'general', 'home', 'index']
        if any(keyword in title_lower for keyword in skip_keywords):
            return False
        
        return True
    
    def _extract_file_type(self, url: str, title: str) -> str:
        """Extract likely file type from URL or title"""
        for ext in ['.pdf', '.docx', '.doc', '.xlsx', '.xls']:
            if ext in url.lower() or ext in title.lower():
                return ext.replace('.', '').upper()
        return "PDF"  
    
    def _deduplicate_and_filter_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicates and filter for best results"""
        seen_urls = set()
        unique_results = []
        
        # Sort by relevance (prefer direct PDF links)
        results.sort(key=lambda x: (
            x['url'].lower().endswith('.pdf'),  
            'form' in x['title'].lower(),       
            len(x['description'])              
        ), reverse=True)
        
        for result in results:
            url = result.get("url", "")
            if url not in seen_urls and len(unique_results) < 10:  # Limit to 10 best results
                seen_urls.add(url)
                unique_results.append(result)
        
        return unique_results
