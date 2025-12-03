# src/chat_logic.py (VERSÃO REESTRUTURADA E ESTÁVEL)

import os
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.tools.tavily_search import TavilySearchResults

# --- CORREÇÃO DE IMPORTS LANGCHAIN (Blindagem) ---
try:
    from langchain_classic.chains import create_history_aware_retriever
    from langchain_classic.chains import create_retrieval_chain
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
except ImportError:
    # Fallback defensivo para outras estruturas LangChain (v0.2+)
    try:
        from langchain.chains import create_history_aware_retriever, create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
    except ImportError as e:
        debug_log(f"Erro crítico: Não foi possível importar funções essenciais do LangChain. Verifique a instalação de 'langchain-classic' ou 'langchain'.", error=e)
        st.error(f"Erro crítico: Não foi possível carregar o LangChain. Contacte o suporte.")
        st.stop()

# Importações internas do projeto (Refatorado)
from src import api_integrations
from src import seo_tools
from src.config import get_llm, get_embeddings_model, FAISS_INDEX_PATH
from src.google_rag_engine import consultar_corpus_vertex, get_google_config
from src.database import log_chat_interaction
from src.utils import debug_log # Observabilidade
from src.prompts import SEO_PROMPT_FULL # NOVO: Importa prompts
from src.assistant_logic import ( # NOVO: Importa lógica do assistente
    gerar_prompt_final_direto,
    gerar_sugestoes,
    gerar_prompt_final_com_abordagem
)


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
        debug_log(f"Conectando ao Vertex AI no projeto: {proj}")
        
        def vertex_chain_func(input_dict):
            query = input_dict.get("input", "")
            
            resposta_dados = consultar_corpus_vertex(
                query=query, 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id_override=model_id
            )
            
            debug_log("Resposta Bruta Vertex AI", data=resposta_dados)

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
        ("system", "Dada a conversa e a pergunta, reformule a pergunta para ser autônoma."),
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

# --- CADEIA HÍBRIDA (Google Vertex + Web) ---
def get_hybrid_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    llm = get_llm(model_name=model_id)
    tavily_key = st.secrets.get("TAVILY_API_KEY")
    search_tool = TavilySearchResults(tavily_api_key=tavily_key) if tavily_key else None
    
    # 1. HÍBRIDO NUVEM
    if google_corpus_id and len(str(google_corpus_id)) > 5:
        def vertex_hybrid_chain_func(input_dict):
            query = input_dict.get("input", "")
            
            web_context = ""
            if search_tool:
                try:
                    web_results = search_tool.invoke({"query": query})
                    web_context = f"\n\nInformações RECENTES da Web (Tavily):\n{web_results}\n"
                except Exception as e:
                    debug_log("Erro na busca Web Híbrida", error=e)
            
            augmented_query = f"{query} {web_context}"
            
            resposta_dados = consultar_corpus_vertex(
                query=augmented_query, 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id_override=model_id
            )

            if isinstance(resposta_dados, dict):
                resposta_final = resposta_dados.get("text", "")
                citations = resposta_dados.get("citations", [])
            else:
                resposta_final = str(resposta_dados)
                citations = []

            return {"result": resposta_final, "context": [], "source_documents": citations}

        return RunnableLambda(vertex_hybrid_chain_func)

    # 2. HÍBRIDO LOCAL
    vectorstore = load_persistent_vectorstore()
    if vectorstore is None: 
        return get_web_search_chain(persona_prompt)

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

# --- CADEIA DE AGENTE SEO ---
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
        | prompt_template
        | llm 
        | StrOutputParser()
    )
    initial_analysis = chain.invoke({"persona_prompt": persona_prompt, "input_text": input_text, "keyword": keyword, "url": url})
    return {"result": initial_analysis, "context": []}


# --- LÓGICA DO ASSISTENTE DE CRIAÇÃO DE PERSONA ---
# Funções movidas para src/assistant_logic.py
# Prompts movidos para src/prompts.py

# --- FUNÇÃO ORQUESTRADORA (process_user_input) ---
def process_user_input(user_input, persona, user_id, session_id):
    chain = None
    
    access_level = persona['access_level']
    persona_prompt = persona['prompt']
    google_corpus_id = persona.get('google_corpus_id')
    model_id = persona.get('model_id')

    try:
        if access_level == "WEB_ONLY":
            chain = get_web_search_chain(persona_prompt)
        elif access_level == "HYBRID":
            allowed_set_ids = []
            chain = get_hybrid_chain(persona_prompt, allowed_set_ids, google_corpus_id, model_id)
        else: # RAG_ONLY
            from src.database import fetch_linked_sets_for_persona
            allowed_set_ids = fetch_linked_sets_for_persona(persona['id'])
            chain = get_rag_chain(persona_prompt, allowed_set_ids, google_corpus_id, model_id)

        if chain:
            debug_log(f"Iniciando chain para modelo: {model_id or 'default'}")
            result = chain.invoke({
                "input": user_input,
                "chat_history": [] 
            })
            
            answer_text = result.get("result") or result.get("answer") or str(result)
            sources = result.get("source_documents", [])
            
            interaction_id = log_chat_interaction(
                user_id, persona['id'], session_id, user_input, answer_text, sources
            )
            
            return {
                "result": answer_text,
                "source_documents": sources,
                "interaction_id": interaction_id
            }
        
        else:
            return {"result": "Erro: Cadeia de processamento não inicializada.", "source_documents": []}

    except Exception as e:
        import traceback
        traceback.print_exc()
        debug_log(f"Erro no process_user_input: {e}")
        return {"result": f"Erro no processamento: {str(e)}", "source_documents": []}