import numpy as np
from openai import OpenAI
from django.conf import settings

def generate_embeddings(text):
    """Generate embeddings for given text using OpenAI's embedding model"""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def similarity_search(query_embedding, embeddings_list, top_k=5):
    """Find the most similar documents based on cosine similarity"""
    # Calculate cosine similarity
    similarities = [
        np.dot(query_embedding, doc_embedding) / 
        (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
        for doc_embedding in embeddings_list
    ]
    
    # Get indices of top k similar documents
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    return [(i, similarities[i]) for i in top_indices]
