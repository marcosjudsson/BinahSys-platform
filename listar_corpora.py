import os
from google import genai
from dotenv import load_dotenv
import streamlit as st

# Tenta carregar do .env ou usa o hardcoded para teste rápido
PROJECT_ID = "rota-da-seda-478119"
LOCATION = "europe-west4"

print(f"🔍 Conectando em: Projeto={PROJECT_ID}, Região={LOCATION}...")

try:
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    
    # Lista todos os corpora disponíveis
    pager = client.rag.list_corpora()
    
    print("\n--- CORPORA ENCONTRADOS ---")
    encontrou = False
    for corpus in pager:
        encontrou = True
        print(f"✅ Nome (Display): {corpus.display_name}")
        print(f"🔑 ID REAL (Copie este): {corpus.name}")
        print("-" * 30)
        
    if not encontrou:
        print("❌ Nenhum Corpus encontrado nesta região/projeto.")
        
except Exception as e:
    print(f"💥 Erro fatal: {e}")