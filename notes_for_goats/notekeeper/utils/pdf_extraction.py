import logging
from io import BytesIO

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file):
    """
    Extract text from a PDF file
    
    Args:
        pdf_file: A file-like object containing PDF data
        
    Returns:
        tuple: (extracted_text, error_message)
    """
    try:
        # Import PyPDF2 here to avoid dependency issues if not installed
        import PyPDF2
        
        # Read the PDF file
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
        
        # Get the number of pages
        num_pages = len(pdf_reader.pages)
        logger.info(f"PDF has {num_pages} pages")
        
        # Extract text from all pages
        text = ""
        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n\n"
        
        # Check if we got meaningful text
        if not text.strip():
            return "", "Could not extract text from PDF. The PDF might be scanned or contain only images."
        
        # Add metadata showing it's a PDF import
        text += f"\n\n#PDFImport\nPages: {num_pages}"
        
        return text, None
        
    except ImportError:
        return "", "PyPDF2 is not installed. Please install it with 'pip install PyPDF2'."
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}", exc_info=True)
        return "", f"Error processing PDF: {str(e)}" 