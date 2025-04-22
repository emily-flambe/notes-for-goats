import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def fetch_url_content(url):
    """
    Fetch content from a URL and extract the title and main text.
    Returns a tuple of (title, content, error_message)
    """
    try:
        # Add http:// if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Fetch the page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get the title
        title = soup.title.string if soup.title else "Untitled Page"
        
        # Try to get the main content
        # This is a simple approach - websites vary greatly in structure
        main_content = ""
        
        # First try to find article or main content
        article = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
        
        if article:
            # Extract text from the article
            paragraphs = article.find_all('p')
            main_content = "\n\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        # If no article found or no paragraphs in article, get all paragraphs
        if not main_content:
            paragraphs = soup.find_all('p')
            main_content = "\n\n".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        # Add metadata at the bottom
        main_content += f"\n\n#UrlImport\nSource: {url}"
        
        return title, main_content, None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None, None, f"Error fetching URL: {str(e)}"
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        return None, None, f"Error processing content: {str(e)}" 