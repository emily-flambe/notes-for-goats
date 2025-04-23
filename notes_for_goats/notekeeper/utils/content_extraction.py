import logging
import requests
from bs4 import BeautifulSoup
from readability import Document
import html2text
from django.conf import settings
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

def extract_content_from_html(html_content, base_url=None, title=None):
    """
    Extract content from HTML string (similar to fetch_url_content but for local HTML)
    
    Args:
        html_content: Raw HTML content string
        base_url: Original URL (helps with resolving relative links)
        title: Optional title override
        
    Returns:
        tuple: (title, content, error)
    """
    try:
        logger.info("Processing HTML content")
        
        # Use Mozilla's Readability to extract the main content
        doc = Document(html_content)
        
        # Extract title if not provided
        if not title:
            title = doc.title()
        
        # Extract the main content
        content_html = doc.summary()
        
        # Convert HTML to markdown
        h2t = html2text.HTML2Text()
        h2t.ignore_links = False
        h2t.ignore_images = False
        h2t.ignore_tables = False
        h2t.body_width = 0  # Don't wrap text
        
        # If base_url is provided, make it absolute
        if base_url:
            soup = BeautifulSoup(content_html, 'html.parser')
            
            # Fix relative URLs in links and images
            for tag in soup.find_all(['a', 'img']):
                if tag.name == 'a' and tag.has_attr('href'):
                    tag['href'] = urljoin(base_url, tag['href'])
                elif tag.name == 'img' and tag.has_attr('src'):
                    tag['src'] = urljoin(base_url, tag['src'])
            
            content_html = str(soup)
        
        # Convert the cleaned HTML to markdown
        markdown_content = h2t.handle(content_html)
        
        # Clean up markdown content
        markdown_content = markdown_content.strip()
        
        # Return the extracted content
        return title, markdown_content, None
        
    except Exception as e:
        logger.error(f"Error extracting content from HTML: {str(e)}")
        return None, None, f"Error processing HTML content: {str(e)}" 