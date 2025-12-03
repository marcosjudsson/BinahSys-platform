# src/chat_logic.py

import os
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.tools.tavily_search import TavilySearchResults

# --- CORREÇÃO DE IMPORTS (CAMINHOS ESPECÍFICOS) ---
# Isso resolve o erro "ModuleNotFoundError: No module named 'langchain.chains'"
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Importações internas do projeto
from src import api_integrations
from src import seo_tools
from src.config import get_llm, get_embeddings_model, FAISS_INDEX_PATH
from src.google_rag_engine import consultar_corpus_vertex, get_google_config
from src.database import log_chat_interaction

@st.cache_resource
def load_persistent_vectorstore():
    if not os.path.exists(FAISS_INDEX_PATH): return None
    try:
        return FAISS.load_local(FAISS_INDEX_PATH, get_embeddings_model(), allow_dangerous_deserialization=True)
    except Exception as e:
        print(f"Erro ao carregar índice FAISS: {e}")
        return None

# --- CADEIA RAG (Google Vertex OU Local) ---
def get_rag_chain(persona_prompt, allowed_set_ids, google_corpus_id=None, model_id=None):
    
    # 1. LÓGICA GOOGLE VERTEX AI (NUVEM)
    if google_corpus_id and len(str(google_corpus_id)) > 5:
        proj, _ = get_google_config()
        st.toast(f"☁️ Vertex AI ({proj})", icon="⚡")
        
        def vertex_chain_func(input_dict):
            query = input_dict.get("input", "")
            resposta_dados = consultar_corpus_vertex(
                query=query, 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id=model_id
            )
            
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
                except:
                    pass
            
            augmented_query = f"{query} {web_context}"
            
            resposta_dados = consultar_corpus_vertex(
                query=augmented_query, 
                corpus_id=google_corpus_id, 
                system_instruction=persona_prompt,
                model_id=model_id
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
SEO_PROMPT_FULL = """
    Você é um especialista em SEO de alto nível e um copywriter excepcional. Sua tarefa é REESCREVER COMPLETAMENTE o rascunho de post fornecido, com dois objetivos principais:
    1.  **Otimização para SEO:** Com base na palavra-chave foco, URL e análise da concorrência.
    2.  **Melhora da Legibilidade:** O texto final DEVE ser mais fácil de ler que o original.

    Após reescrever o post, forneça uma ANÁLISE DETALHADA das otimizações realizadas.

    --- INFORMAÇÕES PARA OTIMIZAÇÃO ---
    Tópico/Palavra-chave Foco: {keyword}
    URL de Referência (ou do post): {url}
    Scores de Performance (PageSpeed Insights): {pagespeed_scores}
    Score de Legibilidade do Rascunho (Flesch Reading Ease): {readability_score}
    **META DE LEGIBILIDADE:** O score do texto otimizado deve ser **superior a 60** e, idealmente, maior que o score do rascunho original.

    Resultados da Web da Concorrência:
    <web_search_results>{web_search_results}</web_search_results>

    Rascunho Original:
    {input_text}

    --- INSTRUÇÕES DE SAÍDA ---
    1.  **TEXTO OTIMIZADO DO POST:** Comece diretamente com o artigo completo e reescrito.
        *   **Estrutura:** Título (H1), meta descrição, introdução, subtítulos (H2, H3), corpo do texto, um Call-to-Action (CTA) forte e, no final, uma seção de **"Perguntas Frequentes (FAQ)"** com 3 a 5 perguntas e respostas relevantes.
        *   **Legibilidade:** Use frases curtas, parágrafos concisos, listas e negritos para facilitar a leitura. A linguagem deve ser clara e direta.
        *   **SEO:** Incorpore a palavra-chave foco e termos semânticos relevantes de forma natural.
    2.  **ANÁLISE DETALHADA:** Após o texto otimizado, insira a linha `--- ANÁLISE DETALHADA ---`.
        *   Nesta seção, explique as otimizações feitas.
        *   **Schema Markup:** Inclua uma subseção chamada "Schema Markup (JSON-LD)" contendo o código completo do schema para o FAQ gerado.
        *   **Instruções para WordPress:** Abaixo do código do schema, adicione uma nota explicando como implementá-lo.
        *   **Sugestões de Elementos Visuais:** Inclua uma subseção com ideias para enriquecer visualmente o post.
        *   **Análise da SERP e Concorrência:** Com base nos `web_search_results`, analise os top 3-5 concorrentes.
        *   **KPIs para Monitoramento:** Sugira 2-3 métricas chave.
        *   **Recomendações para E-A-T:** Forneça sugestões para fortalecer a autoridade.
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
        | prompt_template
        | llm
        | StrOutputParser()
    )
    initial_analysis = chain.invoke({"persona_prompt": persona_prompt, "input_text": input_text, "keyword": keyword, "url": url})
    return {"result": initial_analysis, "context": []}
    
    # --- LÓGICA DO ASSISTENTE DE CRIAÇÃO DE PERSONA ---

PROMPT_ASSISTENTE_GERACAO_DIRETA = """
# IDENTIDADE E OBJETIVO
Você é o "Mestre Criador de Agentes" (MeCA), um especialista sênior em engenharia de prompts. Seu único objetivo é gerar um prompt final de alta performance com base no diagnóstico do usuário.

# PROCESSO
Analise o diagnóstico e crie o melhor prompt possível para a tarefa. Sua resposta deve ser APENAS o texto do prompt, sem comentários, explicações ou blocos de código.

# REGRAS
1. O prompt gerado deve ser completo e autocontido.
2. O prompt deve incluir as variáveis corretas ({{context}}, {{web_search_results}}, {{input}}) com base na "Fonte de Conhecimento" definida no diagnóstico.
---
DIAGNÓSTICO FORNECIDO PELO USUÁRIO:
- **Objetivo Final do Agente:** {objetivo_final}
- **Público-Alvo do Agente:** {usuario_final}
- **Persona e Tom do Agente:** {persona_e_tom}
- **Formato de Saída Desejado:** {formato_saida}
- **Fonte de Conhecimento Principal:** {fonte_conhecimento}
---
Agora, gere o prompt final.
"""

def gerar_prompt_final_direto(diagnostico: dict) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_GERACAO_DIRETA)
    geracao_chain = prompt_template | llm | StrOutputParser()
    return geracao_chain.invoke(diagnostico)

PROMPT_ASSISTENTE_BRAINSTORMING = """
# IDENTIDADE E OBJETIVO
Você é o "Mestre Criador de Agentes" (MeCA), um especialista sênior em engenharia de prompts. Seu objetivo é atuar como um "Parceiro Criativo" para o usuário.

# PROCESSO
Com base no diagnóstico fornecido, sugira 2 a 3 abordagens ou estratégias diferentes para a estrutura do prompt final. Apresente os prós e contras de cada uma de forma clara e concisa. Estruture sua resposta usando Markdown e separe as abordagens com '---'.

# EXEMPLO DE RESPOSTA
**Abordagem 1: Resposta Direta**
- **Prós:** Simples, rápido, eficiente em tokens.
- **Contras:** Pode ser menos detalhado.
---
**Abordagem 2: Chain of Thought (CoT)**
- **Prós:** Gera respostas mais elaboradas e lógicas.
- **Contras:** Usa mais tokens e pode ser mais lento.
---
DIAGNÓSTICO FORNECIDO PELO USUÁRIO:
- **Objetivo Final do Agente:** {objetivo_final}
- **Público-Alvo do Agente:** {usuario_final}
- **Persona e Tom do Agente:** {persona_e_tom}
- **Formato de Saída Desejado:** {formato_saida}
- **Fonte de Conhecimento Principal:** {fonte_conhecimento}
---
Agora, gere as sugestões de abordagem.
"""

PROMPT_ASSISTENTE_EXECUCAO = """
# IDENTIDADE E OBJETIVO
Você é o "Mestre Criador de Agentes" (MeCA), um especialista sênior em engenharia de prompts. Seu objetivo é gerar um prompt final de alta performance com base no diagnóstico do usuário e na diretriz de abordagem que ele escolheu.

# PROCESSO
Analise o diagnóstico e a diretriz de abordagem. Crie o melhor prompt final possível para a tarefa. Sua resposta deve ser APENAS o texto do prompt, sem comentários, explicações ou blocos de código.

# REGRAS
1. O prompt gerado deve ser completo e autocontido.
2. **CRÍTICO:** O prompt DEVE incluir as variáveis corretas ({{context}}, {{web_search_results}}, {{input}}) com base na "Fonte de Conhecimento" definida no diagnóstico. **Exemplo: Se a fonte é RAG_ONLY, o prompt DEVE conter {{context}} e {{input}}.**
---
DIAGNÓSTICO FORNECIDO PELO USUÁRIO:
- **Objetivo Final do Agente:** {objetivo_final}
- **Público-Alvo do Agente:** {usuario_final}
- **Persona e Tom do Agente:** {persona_e_tom}
- **Formato de Saída Desejado:** {formato_saida}
- **Fonte de Conhecimento Principal:** {fonte_conhecimento}

DIRETRIZ DE ABORDAGEM ESCOLHIDA:
{diretriz_abordagem}
---
Agora, gere o prompt final.
"""

def gerar_sugestoes(diagnostico: dict) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_BRAINSTORMING)
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke(diagnostico)

def gerar_prompt_final_com_abordagem(diagnostico: dict, diretriz_abordagem: str) -> str:
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_EXECUCAO)
    chain = prompt_template | llm | StrOutputParser()
    input_data = {**diagnostico, "diretriz_abordagem": diretriz_abordagem}
    return chain.invoke(input_data)

# --- FUNÇÃO ORQUESTRADORA PRINCIPAL ---
# Esta é a função que a interface (1_Chat_com_Especialista.py) chama.
def process_user_input(user_input, persona, user_id, session_id):
    """
    Função principal chamada pela interface.
    """
    chain = None
    
    # Extrai metadados
    access_level = persona['access_level']
    persona_prompt = persona['prompt']
    google_corpus_id = persona.get('google_corpus_id')
    model_id = persona.get('model_id')

    try:
        # Seleção de Chain
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
            # Executa
            result = chain.invoke({
                "input": user_input,
                "chat_history": [] 
            })
            
            # Normaliza resposta
            answer_text = result.get("result") or result.get("answer") or str(result)
            sources = result.get("source_documents", [])
            
            # Log
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
        return {"result": f"Erro no processamento: {str(e)}", "source_documents": []}