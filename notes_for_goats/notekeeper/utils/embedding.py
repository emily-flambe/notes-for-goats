import numpy as np
from openai import OpenAI
from django.conf import settings
import re

def generate_embeddings(text):
    """Generate embeddings for given text using OpenAI's embedding model"""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def count_tokens(text):
    """
    Estimate token count - a simplified approach without requiring tiktoken
    Approximation: ~4 chars per token for English text
    """
    return len(text) // 4

def chunk_text(text, max_tokens=8000):
    """
    Split text into chunks of approximately max_tokens
    Returns a list of chunks
    """
    # Check if chunking is needed
    estimated_tokens = count_tokens(text)
    if estimated_tokens <= max_tokens:
        return [text]
    
    # Simple chunking strategy - split by paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    for para in paragraphs:
        para_tokens = count_tokens(para)
        
        # If a single paragraph exceeds the limit, split it by sentences
        if para_tokens > max_tokens:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                sentence_tokens = count_tokens(sentence)
                
                # If adding this sentence would exceed the limit, start a new chunk
                if current_tokens + sentence_tokens > max_tokens and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = sentence
                    current_tokens = sentence_tokens
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
                    current_tokens += sentence_tokens
            
        # If adding this paragraph would exceed the limit, start a new chunk
        elif current_tokens + para_tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = para
            current_tokens = para_tokens
        else:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
            current_tokens += para_tokens
    
    # Add the final chunk if there's anything left
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def generate_chunked_embeddings(text):
    """
    Generate embeddings for chunks of text that exceeds the token limit
    Returns a list of (chunk_text, embedding) tuples
    """
    chunks = chunk_text(text)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    results = []
    for chunk in chunks:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=chunk
        )
        embedding = response.data[0].embedding
        results.append((chunk, embedding))
    
    return results

def similarity_search(query_embedding, embeddings_list, top_k=5):
    """
    Find the most similar documents based on cosine similarity
    Args:
        query_embedding: Embedding vector for the query
        embeddings_list: List of embedding vectors to search through
        top_k: Number of top results to return
    Returns:
        List of (index, similarity_score) tuples for the top_k most similar items
    """
    query_array = np.array(query_embedding)
    similarities = []
    
    for i, embedding in enumerate(embeddings_list):
        if embedding:
            embedding_array = np.array(embedding)
            similarity = np.dot(query_array, embedding_array) / (
                np.linalg.norm(query_array) * np.linalg.norm(embedding_array)
            )
            similarities.append((i, similarity))
    
    # Sort by similarity (highest first) and return top k
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]
