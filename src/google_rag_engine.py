# src/google_rag_engine.py (VERSÃO FINAL: ARQUITETURA CROSS-REGION)

import os
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import traceback

# Carrega variáveis de ambiente
load_dotenv()

def get_google_config():
    """
    Recupera configurações.
    Retorna (Project ID, Região dos DADOS).
    """
    try:
        project_id = os.getenv("GOOGLE_PROJECT_ID") or st.secrets.get("GOOGLE_PROJECT_ID")
        # Esta location é onde estão os DADOS (RAG Corpus), ex: europe-west4
        rag_location = os.getenv("GOOGLE_LOCATION") or st.secrets.get("GOOGLE_LOCATION", "europe-west4")
        return project_id, rag_location
    except Exception:
        return None, None

from src.config import AVAILABLE_MODELS

def consultar_corpus_vertex(query, corpus_id, system_instruction=None, model_id_override=None):
    """
    Consulta o Vertex AI RAG usando arquitetura Cross-Region.
    Dados na Europa -> Processamento nos EUA.
    """
    # 1. Configuração
    env_project, env_rag_location = get_google_config()
    
    # --- A SOLUÇÃO DEFINITIVA: FORÇAR CÉREBRO NOS EUA ---
    # A região us-central1 sempre tem os modelos mais recentes e estáveis.
    # Isso não move seus dados, apenas envia a pergunta para ser processada lá.
    model_location = "us-central1"

    print(f"\n--- 🧠 GOOGLE RAG ENGINE (CROSS-REGION) ---")
    print(f"1. Projeto: {env_project}")
    print(f"2. Dados (RAG): {env_rag_location}")
    print(f"3. Cérebro (LLM): {model_location}")
    
    if not env_project:
        return "Erro Crítico: Project ID do Google Cloud não configurado."

    try:
        # 2. Inicializa o Cliente na região do CÉREBRO (EUA)
        # Isso evita o erro 404 de "Model Not Found" na Europa.
        client = genai.Client(vertexai=True, project=env_project, location=model_location)

        # 3. Montagem do Nome do Recurso RAG (Apontando para a EUROPA)
        # O cliente dos EUA consegue ler dados da Europa se passarmos o caminho completo.
        if "projects/" not in corpus_id:
            rag_resource_name = f"projects/{env_project}/locations/{env_rag_location}/ragCorpora/{corpus_id}"
        else:
            rag_resource_name = corpus_id
        
        print(f"4. Alvo RAG: {rag_resource_name}")

        # 4. Configuração da Ferramenta RAG
        rag_tool = types.Tool(
            retrieval=types.Retrieval(
                vertex_rag_store=types.VertexRagStore(
                    rag_corpora=[rag_resource_name],
                    similarity_top_k=5,
                    vector_distance_threshold=0.5
                )
            )
        )

        # 5. Definição do Modelo (Dinâmico)
        # Prioridade: Override (Persona) > Padrão do Config > Hardcoded Fallback
        if model_id_override:
            model_id = model_id_override
        elif AVAILABLE_MODELS:
            model_id = AVAILABLE_MODELS[0]
        else:
            model_id = "gemini-2.0-flash-001"

        print(f"5. Modelo Selecionado: {model_id}")

        # 6. Configuração da Geração (Persona + RAG)
        generate_config = types.GenerateContentConfig(
            tools=[rag_tool],
            temperature=0.1, 
            system_instruction=system_instruction
        )

        # 7. Execução
        response = client.models.generate_content(
            model=model_id,
            contents=query, 
            config=generate_config
        )

        print("6. Resposta recebida com sucesso.")
        
        if response.text:
            return response.text
        else:
            return "O modelo processou a consulta mas retornou vazio (Verifique filtros de segurança)."

    except Exception as e:
        print(f"\n❌ ERRO FATAL NO ENGINE:")
        traceback.print_exc()
        # Retorna mensagem amigável mas técnica para debug na tela
        return f"ERRO TÉCNICO (Vertex AI): {str(e)}"