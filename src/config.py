# src/config.py

import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv() # Carrega as variáveis de ambiente do .env

# --- CONSTANTES COMPARTILHADAS ---
FAISS_INDEX_PATH = "faiss_index"

# Modelos aprovados para uso no Sistema (Vertex AI / Google AI)
# O primeiro da lista será o padrão (default).
AVAILABLE_MODELS = [
    "gemini-2.0-flash-001",     # Padrão atual (Rápido e eficiente)
    "gemini-2.0-flahs-lite",       # Alta inteligência, janela grande
    "gemini-2.5-flash",     # Versão anterior otimizada
    "gemini-2.5-pro",         # Legacy (backup)
]

# --- MODELOS COMPARTILHADOS ---

@st.cache_resource
def get_llm(model_name=None):
    """
    Retorna o modelo de linguagem (LLM).
    Args:
        model_name (str, optional): Nome do modelo específico a ser usado. 
                                    Se None, usa o primeiro de AVAILABLE_MODELS.
    """
    # Se nenhum modelo for especificado, usa o primeiro da lista aprovada (Default)
    selected_model = model_name if model_name else AVAILABLE_MODELS[0]
    
    return ChatGoogleGenerativeAI(model=selected_model, temperature=0.5, streaming=True)

@st.cache_resource
def get_embeddings_model():
    """Retorna o modelo de embeddings."""
    return HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')