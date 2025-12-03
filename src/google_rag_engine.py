# src/google_rag_engine.py (VERSÃO COM LOGS ESTRUTURADOS)

import os
import json
import tempfile
import streamlit as st
from google import genai
from google.genai import types
from dotenv import load_dotenv
import traceback
from src.config import AVAILABLE_MODELS
from src.utils import debug_log # NOVO

load_dotenv()

def setup_google_credentials():
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"): return
    if "GOOGLE_CREDENTIALS" in st.secrets:
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp_key:
                json.dump(dict(st.secrets["GOOGLE_CREDENTIALS"]), tmp_key)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp_key.name
        except Exception as e:
            debug_log("Erro ao configurar credenciais via secrets", error=e)

def get_google_config():
    setup_google_credentials()
    try:
        pid = os.getenv("GOOGLE_PROJECT_ID") or st.secrets.get("GOOGLE_PROJECT_ID")
        loc = os.getenv("GOOGLE_LOCATION") or st.secrets.get("GOOGLE_LOCATION", "europe-west4")
        return pid, loc
    except: return None, None

def consultar_corpus_vertex(query, corpus_id, system_instruction=None, model_id_override=None):
    env_project, env_rag_location = get_google_config()
    model_location = "us-central1" # Split-Brain Architecture
    
    if not env_project: return {"text": "Erro: Project ID ausente.", "citations": []}

    try:
        client = genai.Client(vertexai=True, project=env_project, location=model_location)

        if "projects/" not in corpus_id:
            rag_resource_name = f"projects/{env_project}/locations/{env_rag_location}/ragCorpora/{corpus_id}"
        else:
            rag_resource_name = corpus_id
        
        rag_tool = types.Tool(
            retrieval=types.Retrieval(
                vertex_rag_store=types.VertexRagStore(
                    rag_corpora=[rag_resource_name],
                    similarity_top_k=5,
                    vector_distance_threshold=0.5
                )
            )
        )

        if model_id_override: model_id = model_id_override
        elif isinstance(AVAILABLE_MODELS, list): model_id = AVAILABLE_MODELS[0]
        elif isinstance(AVAILABLE_MODELS, dict): model_id = list(AVAILABLE_MODELS.keys())[0]
        else: model_id = "gemini-2.0-flash-001"

        debug_log("Iniciando Request Vertex AI", data={"model": model_id, "rag_source": rag_resource_name})

        response = client.models.generate_content(
            model=model_id,
            contents=query, 
            config=types.GenerateContentConfig(
                tools=[rag_tool],
                temperature=0.1, 
                system_instruction=system_instruction
            )
        )

        # --- EXTRAÇÃO DE CITAÇÕES ---
        citations = []
        try:
            if response.candidates:
                candidate = response.candidates[0]
                cand_dict = candidate.to_json_dict() if hasattr(candidate, 'to_json_dict') else {}
                
                grounding_meta = cand_dict.get('grounding_metadata') or cand_dict.get('groundingMetadata')
                
                if grounding_meta:
                    chunks = grounding_meta.get('grounding_chunks') or grounding_meta.get('groundingChunks') or []
                    debug_log(f"Grounding Chunks encontrados: {len(chunks)}")
                    
                    for chunk in chunks:
                        uri = None
                        title = None
                        
                        # 1. Tenta direto do retrieved_context (Padrão Gemini 2.0)
                        rc = chunk.get('retrieved_context') or chunk.get('retrievedContext')
                        if rc:
                            uri = rc.get('uri')
                            title = rc.get('title')
                            
                            # Fallback para rag_chunk
                            if not uri:
                                rag_c = rc.get('rag_chunk') or rc.get('ragChunk')
                                if rag_c:
                                    uri = rag_c.get('uri')
                                    title = title or rag_c.get('title')

                        # 2. Web Fallback
                        if not uri:
                            web = chunk.get('web')
                            if web:
                                uri = web.get('uri') or web.get('url')
                                title = web.get('title')

                        if uri:
                            clean_title = title or uri.split('/')[-1]
                            if not any(c['uri'] == uri for c in citations):
                                citations.append({"uri": uri, "title": clean_title})

        except Exception as e:
            debug_log("Aviso: Falha na extração de citações", error=e)

        debug_log("Citações Finais Extraídas", data=citations)

        return {
            "text": response.text if response.text else "Sem resposta.",
            "citations": citations
        }

    except Exception as e:
        debug_log("Erro Crítico Vertex AI", error=e)
        return {"text": f"ERRO TÉCNICO: {str(e)}", "citations": []}
