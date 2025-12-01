import os
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Carrega variáveis de ambiente (local ou secrets)
load_dotenv()

def get_google_config():
    """Recupera configurações do Google Cloud do ambiente ou secrets."""
    try:
        project_id = os.getenv("GOOGLE_PROJECT_ID") or st.secrets.get("GOOGLE_PROJECT_ID")
        location = os.getenv("GOOGLE_LOCATION") or st.secrets.get("GOOGLE_LOCATION", "europe-west4")
        
        if not project_id:
            raise ValueError("Project ID do Google Cloud não configurado.")
            
        return project_id, location
    except Exception:
        return None, None

def consultar_corpus_vertex(query, corpus_id, project_id=None, location=None):
    """
    Consulta o Vertex AI RAG Engine usando o SDK google-genai v1.0+.
    """
    # 1. Configuração Automática
    env_project, env_location = get_google_config()
    project_id = project_id or env_project
    location = location or env_location

    if not project_id:
        return "Erro de Configuração: GOOGLE_PROJECT_ID não encontrado no .env ou secrets.toml."

    try:
        # 2. Inicializa o Cliente
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location
        )

        # 3. Montagem do Recurso (O Pulo do Gato)
        # Se o usuário passou só o ID (ex: "tutor-diamondone-poc"), montamos o caminho completo.
        # Se já passou o caminho completo, usamos como está.
        if "projects/" not in corpus_id:
            rag_resource_name = f"projects/{project_id}/locations/{location}/ragCorpora/{corpus_id}"
        else:
            rag_resource_name = corpus_id

        # 4. Configuração da Tool (Vertex RAG Store)
        # Atenção: Usamos vertex_rag_store, não vertex_ai_search
        rag_tool = types.Tool(
            retrieval=types.Retrieval(
                vertex_rag_store=types.VertexRagStore(
                    rag_corpora=[rag_resource_name],
                    similarity_top_k=5,  # Traz os 5 trechos mais relevantes
                    vector_distance_threshold=0.5 # Filtra coisas pouco relevantes
                )
            )
        )

        # 5. Definição do Modelo e Prompt
        model_id = "gemini-1.5-flash" # Modelo rápido e eficiente
        
        prompt_texto = (
            f"Use o contexto recuperado da base de conhecimento (RAG) para responder à pergunta do usuário.\n"
            f"Pergunta: {query}\n"
            f"Se a informação não estiver no contexto, diga que não sabe."
        )

        # 6. Geração de Conteúdo
        response = client.models.generate_content(
            model=model_id,
            contents=prompt_texto,
            config=types.GenerateContentConfig(
                tools=[rag_tool],
                temperature=0.3 # Baixa criatividade para ser mais fiel aos dados
            )
        )

        # 7. Extração da Resposta
        if response.text:
            return response.text
        else:
            # Caso raro onde a resposta vem vazia ou bloqueada
            return "O modelo processou a consulta mas não retornou texto (Verifique filtros de segurança)."

    except Exception as e:
        erro_str = str(e)
        # Tratamento de erro amigável
        if "404" in erro_str or "not found" in erro_str.lower():
            return f"Erro: O Corpus '{corpus_id}' não foi encontrado no projeto '{project_id}' (Região: {location}). Verifique o ID."
        elif "403" in erro_str or "permission" in erro_str.lower():
            return f"Erro de Permissão: A conta de serviço não tem acesso ao Vertex AI."
        else:
            return f"Erro na integração com Vertex AI: {erro_str}"