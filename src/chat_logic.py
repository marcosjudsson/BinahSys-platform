# src/chat_logic.py (VERSÃO ESTÁVEL - UNIFICADA)

import os
import streamlit as st
import traceback
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.tools.tavily_search import TavilySearchResults

# --- IMPORTS CRÍTICOS (Usando langchain_classic que está instalado) ---
from langchain_classic.chains import create_history_aware_retriever
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

# Imports Internos
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
        debug_log(f"Erro FAISS: {e}")
        return None

# --- RAG CHAIN ---
def get_rag_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    # Vertex AI
    if google_corpus_id and len(str(google_corpus_id)) > 5:
        proj, _ = get_google_config()
        st.toast(f"☁️ Vertex AI", icon="⚡")
        
        def vertex_chain_func(input_dict):
            query = input_dict.get("input", "")
            res = consultar_corpus_vertex(
                query=query, corpus_id=google_corpus_id, 
                system_instruction=persona_prompt, model_id_override=model_id
            )
            debug_log("Vertex Res", data=res)
            
            if isinstance(res, dict):
                return {"result": res.get("text", ""), "source_documents": res.get("citations", [])}
            return {"result": str(res), "source_documents": []}
        
        return RunnableLambda(vertex_chain_func)
    
    # Local FAISS
    llm = get_llm(model_name=model_id)
    vectorstore = load_persistent_vectorstore()
    if not vectorstore: st.error("Sem base local."); st.stop()

    def filter_docs(docs):
        if not allowed_set_ids: return []
        return [d for d in docs if d.metadata.get("set_id") in set(allowed_set_ids)]

    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    
    hist_prompt = ChatPromptTemplate.from_messages([("system", "Reformule a pergunta."), MessagesPlaceholder("chat_history"), ("human", "{input}")])
    hist_retriever = create_history_aware_retriever(llm, retriever, hist_prompt)
    
    qa_prompt = ChatPromptTemplate.from_messages([("system", persona_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")])
    qa_chain = create_stuff_documents_chain(llm, qa_prompt)
    
    return create_retrieval_chain(hist_retriever, qa_chain)

# --- WEB CHAIN ---
def get_web_search_chain(persona_prompt):
    llm = get_llm()
    key = st.secrets.get("TAVILY_API_KEY")
    if not key: return RunnableLambda(lambda x: {"result": "Erro: Sem TAVILY_API_KEY", "context": []})
    
    tool = TavilySearchResults(tavily_api_key=key)
    prompt = ChatPromptTemplate.from_messages([("system", persona_prompt), ("human", "{input}\nWeb: <res>{web_search_results}</res>")])
    
    chain = ({"web_search_results": (lambda x: tool.invoke({"query": x["input"]})), "input": RunnablePassthrough()} | prompt | llm | StrOutputParser())
    return RunnablePassthrough.assign(result=chain, context=lambda x: [])

# --- HYBRID CHAIN ---
def get_hybrid_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    llm = get_llm(model_name=model_id)
    key = st.secrets.get("TAVILY_API_KEY")
    tool = TavilySearchResults(tavily_api_key=key) if key else None
    
    if google_corpus_id:
        def vertex_hybrid(input_dict):
            q = input_dict.get("input", "")
            web_ctx = ""
            if tool:
                try: web_ctx = tool.invoke({"query": q})
                except: pass
            
            res = consultar_corpus_vertex(f"{q} {web_ctx}", google_corpus_id, persona_prompt, model_id)
            if isinstance(res, dict): return {"result": res.get("text"), "source_documents": res.get("citations", [])}
            return {"result": str(res), "source_documents": []}
        return RunnableLambda(vertex_hybrid)

    # Local Fallback
    vectorstore = load_persistent_vectorstore()
    if not vectorstore: return get_web_search_chain(persona_prompt)
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    prompt = ChatPromptTemplate.from_template(persona_prompt)
    
    ctx_chain = RunnablePassthrough.assign(
        context=lambda x: retriever.invoke(x["input"]),
        web_search_results=lambda x: tool.invoke({"query": x["input"]}) if tool else "",
        input=lambda x: x["input"]
    )
    chain = ctx_chain | prompt | llm | StrOutputParser()
    return RunnablePassthrough.assign(result=chain, context=ctx_chain.pick("context"))

# --- SEO ---
def get_seo_analysis_chain(persona_prompt, input_text, keyword, url):
    llm = get_llm()
    tool = TavilySearchResults(tavily_api_key=st.secrets.get("TAVILY_API_KEY"))
    
    # Prompt SEO Simplificado para caber no arquivo sem quebrar
    prompt = ChatPromptTemplate.from_template("""
    Atue como especialista SEO. Reescreva o texto focando em: {keyword}.
    URL: {url}. PageSpeed: {pagespeed_scores}. Legibilidade: {readability_score}.
    Concorrência: {web_search_results}.
    Texto Original: {input_text}
    Saída: Texto Otimizado + Análise Detalhada (Schema, Gaps, KPIs).
    """)
    
    chain = (
        {"web_search_results": lambda x: tool.invoke({"query": x["keyword"]}), 
         "readability_score": lambda x: seo_tools.analyze_readability(x["input_text"]),
         "pagespeed_scores": lambda x: api_integrations.get_psi_data(x["url"]),
         "persona_prompt": lambda x: x["persona_prompt"], "input_text": lambda x: x["input_text"],
         "keyword": lambda x: x["keyword"], "url": lambda x: x["url"]}
        | prompt | llm | StrOutputParser()
    )
    res = chain.invoke({"persona_prompt": persona_prompt, "input_text": input_text, "keyword": keyword, "url": url})
    return {"result": res, "context": []}

# --- ASSISTENTE ---
def gerar_prompt_final_direto(d): return (ChatPromptTemplate.from_template("Crie prompt: {objetivo_final}") | get_llm() | StrOutputParser()).invoke(d)
def gerar_sugestoes(d): return (ChatPromptTemplate.from_template("Sugira abordagens: {objetivo_final}") | get_llm() | StrOutputParser()).invoke(d)
def gerar_prompt_final_com_abordagem(d, a): return (ChatPromptTemplate.from_template("Crie prompt com abordagem {diretriz_abordagem}: {objetivo_final}") | get_llm() | StrOutputParser()).invoke({**d, "diretriz_abordagem": a})

# --- MAIN ---
def process_user_input(user_input, persona, user_id, session_id):
    chain = None
    try:
        acc = persona['access_level']
        if acc == "WEB_ONLY": chain = get_web_search_chain(persona['prompt'])
        elif acc == "HYBRID": chain = get_hybrid_chain(persona['prompt'], [], persona.get('google_corpus_id'), persona.get('model_id'))
        else:
            from src.database import fetch_linked_sets_for_persona
            sets = fetch_linked_sets_for_persona(persona['id'])
            chain = get_rag_chain(persona['prompt'], sets, persona.get('google_corpus_id'), persona.get('model_id'))
            
        if chain:
            res = chain.invoke({"input": user_input, "chat_history": []})
            ans = res.get("result") or res.get("answer") or str(res)
            src = res.get("source_documents", [])
            iid = log_chat_interaction(user_id, persona['id'], session_id, user_input, ans, src)
            return {"result": ans, "source_documents": src, "interaction_id": iid}
        return {"result": "Erro Chain", "source_documents": []}
    except Exception as e:
        debug_log(f"Erro process: {e}")
        traceback.print_exc()
        return {"result": f"Erro: {str(e)}", "source_documents": []}