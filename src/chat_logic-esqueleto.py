# src/chat_logic.py (VERSÃO CORRIGIDA - IMPORTS EXATOS)

import os
import streamlit as st
import traceback
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.tools.tavily_search import TavilySearchResults

# --- CORREÇÃO DOS IMPORTS (O ERRO ESTAVA AQUI) ---
# Importando dos caminhos específicos para não quebrar
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Importações internas
from src import api_integrations
from src import seo_tools
from src.config import get_llm, get_embeddings_model, FAISS_INDEX_PATH
from src.google_rag_engine import consultar_corpus_vertex, get_google_config
from src.database import log_chat_interaction
from src.utils import debug_log

@st.cache_resource
def load_persistent_vectorstore():
    if not os.path.exists(FAISS_INDEX_PATH): return None
    try:
        return FAISS.load_local(FAISS_INDEX_PATH, get_embeddings_model(), allow_dangerous_deserialization=True)
    except Exception as e:
        debug_log(f"Erro ao carregar índice FAISS: {e}")
        return None

# --- CADEIA RAG (Google Vertex OU Local) ---
def get_rag_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    
    # 1. LÓGICA GOOGLE VERTEX AI (NUVEM)
    if google_corpus_id and len(str(google_corpus_id)) > 5:
        proj, _ = get_google_config()
        st.toast(f"☁️ Vertex AI", icon="⚡")
        
        def vertex_chain_func(input_dict):
            query = input_dict.get("input", "")
            
            # Chama motor Google
            resposta_dados = consultar_corpus_vertex(
                query=query, 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id_override=model_id
            )
            
            debug_log("Resposta Bruta Vertex", data=resposta_dados)

            if isinstance(resposta_dados, dict):
                resposta_final = resposta_dados.get("text", "")
                citations = resposta_dados.get("citations", [])
            else:
                resposta_final = str(resposta_dados)
                citations = []

            return {"result": resposta_final, "context": [], "source_documents": citations} 
        
        return RunnableLambda(vertex_chain_func)
    
    # 2. LÓGICA LEGADA (FAISS LOCAL)
    llm = get_llm(model_name=model_id)
    vectorstore = load_persistent_vectorstore()
    
    if vectorstore is None: 
        st.error("Base de conhecimento local não encontrada.")
        st.stop()

    def filter_documents(docs):
        if not allowed_set_ids: return []
        return [doc for doc in docs if doc.metadata.get("set_id") in set(allowed_set_ids)]

    base_retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})
    
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", "Reformule a pergunta para ser autônoma baseada no histórico."),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    history_aware_retriever = create_history_aware_retriever(llm, base_retriever, contextualize_q_prompt)

    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", persona_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    return create_retrieval_chain(history_aware_retriever, question_answer_chain)

# --- CADEIA WEB SEARCH ---
def get_web_search_chain(persona_prompt):
    llm = get_llm()
    tavily_key = st.secrets.get("TAVILY_API_KEY")
    if not tavily_key:
        return RunnableLambda(lambda x: {"result": "Erro: TAVILY_API_KEY não configurada.", "context": []})

    search_tool = TavilySearchResults(tavily_api_key=tavily_key)
    prompt = ChatPromptTemplate.from_messages([
        ("system", persona_prompt),
        ("human", "Pergunta: {input}\n\nResultados da Web:\n<web_search_results>{web_search_results}</web_search_results>")
    ])

    chain = (
        {"web_search_results": (lambda x: search_tool.invoke({"query": x["input"]})), "input": RunnablePassthrough()} 
        | prompt 
        | llm 
        | StrOutputParser()
    )

    final_chain = RunnablePassthrough.assign(result=chain, context=lambda x: [])
    return final_chain

# --- CADEIA HÍBRIDA ---
def get_hybrid_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    llm = get_llm(model_name=model_id)
    tavily_key = st.secrets.get("TAVILY_API_KEY")
    search_tool = TavilySearchResults(tavily_api_key=tavily_key) if tavily_key else None
    
    if google_corpus_id and len(str(google_corpus_id)) > 5:
        def vertex_hybrid_chain_func(input_dict):
            query = input_dict.get("input", "")
            
            web_context = ""
            if search_tool:
                try:
                    web_results = search_tool.invoke({"query": query})
                    web_context = f"\nWeb Info: {web_results}\n"
                except: pass
            
            resposta_dados = consultar_corpus_vertex(
                query=f"{query} {web_context}", 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id_override=model_id
            )

            if isinstance(resposta_dados, dict):
                return {"result": resposta_dados.get("text", ""), "context": [], "source_documents": resposta_dados.get("citations", [])}
            return {"result": str(resposta_dados), "context": [], "source_documents": []}

        return RunnableLambda(vertex_hybrid_chain_func)

    # Fallback Local
    vectorstore = load_persistent_vectorstore()
    if vectorstore is None: return get_web_search_chain(persona_prompt)

    base_retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})
    prompt = ChatPromptTemplate.from_template(persona_prompt)
    context_chain = RunnablePassthrough.assign(
        context=lambda x: base_retriever.invoke(x["input"]),
        web_search_results=lambda x: search_tool.invoke({"query": x["input"]}) if search_tool else "",
        input=lambda x: x["input"]
    )
    response_chain = context_chain | prompt | llm | StrOutputParser()
    final_chain = RunnablePassthrough.assign(result=response_chain, context=context_chain.pick("context"))
    return final_chain

# --- CADEIA SEO ---
SEO_PROMPT_FULL = """
    Você é um especialista em SEO. Reescreva o texto focando na palavra-chave: {keyword}.
    URL: {url}. PageSpeed: {pagespeed_scores}. Legibilidade: {readability_score}.
    Concorrência: {web_search_results}.
    Texto Original: {input_text}
    Saída: Texto Otimizado + Análise Detalhada (Schema, Gaps, KPIs).
"""

def get_seo_analysis_chain(persona_prompt, input_text, keyword, url):
    llm = get_llm()
    search_tool = TavilySearchResults(tavily_api_key=st.secrets.get("TAVILY_API_KEY"))
    prompt_template = ChatPromptTemplate.from_template(SEO_PROMPT_FULL)

    chain = (
        {
            "web_search_results": lambda x: search_tool.invoke({"query": x["keyword"]}),
            "readability_score": lambda x: seo_tools.analyze_readability(x["input_text"]),
            "pagespeed_scores": lambda x: api_integrations.get_psi_data(x["url"]),
            "persona_prompt": lambda x: x["persona_prompt"],
            "input_text": lambda x: x["input_text"],
            "keyword": lambda x: x["keyword"],
            "url": lambda x: x["url"],
        }
        | prompt_template | llm | StrOutputParser()
    )
    initial_analysis = chain.invoke({"persona_prompt": persona_prompt, "input_text": input_text, "keyword": keyword, "url": url})
    return {"result": initial_analysis, "context": []}

# --- ASSISTENTE PERSONA ---
PROMPT_ASSISTENTE_GERACAO_DIRETA = """Crie um prompt de sistema para IA com base nisto: {objetivo_final}, {usuario_final}, {persona_e_tom}, {fonte_conhecimento}."""
def gerar_prompt_final_direto(diagnostico: dict) -> str:
    llm = get_llm()
    return (ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_GERACAO_DIRETA) | llm | StrOutputParser()).invoke(diagnostico)

PROMPT_ASSISTENTE_BRAINSTORMING = """Sugira 3 abordagens de prompt para: {objetivo_final}..."""
def gerar_sugestoes(diagnostico: dict) -> str:
    llm = get_llm()
    return (ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_BRAINSTORMING) | llm | StrOutputParser()).invoke(diagnostico)

PROMPT_ASSISTENTE_EXECUCAO = """Crie prompt final baseado em: {objetivo_final} e abordagem {diretriz_abordagem}"""
def gerar_prompt_final_com_abordagem(diagnostico: dict, diretriz: str) -> str:
    llm = get_llm()
    return (ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_EXECUCAO) | llm | StrOutputParser()).invoke({**diagnostico, "diretriz_abordagem": diretriz})

# --- FUNÇÃO ORQUESTRADORA PRINCIPAL ---
def process_user_input(user_input, persona, user_id, session_id):
    chain = None
    try:
        access_level = persona['access_level']
        google_corpus_id = persona.get('google_corpus_id')
        model_id = persona.get('model_id')

        if access_level == "WEB_ONLY":
            chain = get_web_search_chain(persona['prompt'])
        elif access_level == "HYBRID":
            allowed_set_ids = []
            chain = get_hybrid_chain(persona['prompt'], [], google_corpus_id, model_id)
        else: # RAG_ONLY
            from src.database import fetch_linked_sets_for_persona
            allowed_set_ids = fetch_linked_sets_for_persona(persona['id'])
            chain = get_rag_chain(persona['prompt'], allowed_set_ids, google_corpus_id, model_id)

        if chain:
            # Executa
            result = chain.invoke({"input": user_input, "chat_history": []})
            
            # Normaliza resposta
            answer_text = result.get("result") or result.get("answer") or str(result)
            sources = result.get("source_documents", [])
            
            interaction_id = log_chat_interaction(user_id, persona['id'], session_id, user_input, answer_text, sources)
            return {"result": answer_text, "source_documents": sources, "interaction_id": interaction_id}
        
        else:
            return {"result": "Erro: Chain não inicializada.", "source_documents": []}

    except Exception as e:
        debug_log(f"Erro process_user_input: {e}")
        traceback.print_exc()
        return {"result": f"Erro no processamento: {str(e)}", "source_documents": []}