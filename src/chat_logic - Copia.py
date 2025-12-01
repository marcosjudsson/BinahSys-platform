# src/chat_logic.py (VERSÃO ATUALIZADA COM GOOGLE VERTEX AI RAG)

import os
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src import api_integrations
from src import seo_tools
from src.google_rag_engine import consultar_corpus_vertex # Módulo Novo

from langchain_core.output_parsers import StrOutputParser
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import FAISS
from langchain_tavily import TavilySearch
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from src.config import get_llm, get_embeddings_model, FAISS_INDEX_PATH

@st.cache_resource
def load_persistent_vectorstore():
    if not os.path.exists(FAISS_INDEX_PATH): return None
    return FAISS.load_local(FAISS_INDEX_PATH, get_embeddings_model(), allow_dangerous_deserialization=True)

def get_rag_chain(persona_prompt, allowed_set_ids, google_corpus_id=None):
    # --- LÓGICA GOOGLE VERTEX AI (ROTA DA SEDA) ---
    if google_corpus_id:
        def vertex_chain_func(input_dict):
            query = input_dict["input"]
            # Chama o motor nuvem
            resposta = consultar_corpus_vertex(query, google_corpus_id)
            return {"answer": resposta, "context": []} # Retorna dicionário compatível
        
        return RunnableLambda(vertex_chain_func)
    
    # --- LÓGICA LEGADA (FAISS LOCAL) ---
    llm = get_llm()
    vectorstore = load_persistent_vectorstore()
    if vectorstore is None: st.error("Base de conhecimento não criada."); st.stop()

    base_retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 20})

    def filter_documents(docs):
        return [doc for doc in docs if doc.metadata.get("set_id") in set(allowed_set_ids)]

    filtered_retriever = base_retriever | RunnableLambda(filter_documents)

    contextualize_q_prompt = ChatPromptTemplate.from_messages([("system", "Dada a conversa e a pergunta, reformule a pergunta para ser autônoma."), MessagesPlaceholder("chat_history"), ("human", "{input}")])
    history_aware_retriever = create_history_aware_retriever(llm, filtered_retriever, contextualize_q_prompt)

    qa_prompt = ChatPromptTemplate.from_messages([("system", persona_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")])
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    return create_retrieval_chain(history_aware_retriever, question_answer_chain)

def get_web_search_chain(persona_prompt):
    llm = get_llm()
    search_tool = TavilySearch()
    prompt = ChatPromptTemplate.from_messages([("system", persona_prompt), ("human", "Pergunta: {input}\n\nResultados da Web:\n<web_search_results>{web_search_results}</web_search_results>")])

    chain = ({"web_search_results": (lambda x: search_tool.invoke({"query": x["input"]})), "input": RunnablePassthrough()} | prompt | llm | StrOutputParser())

    final_chain = RunnablePassthrough.assign(answer=chain, context=lambda x: [])
    return final_chain

def get_hybrid_chain(persona_prompt, allowed_set_ids, google_corpus_id=None):
    llm = get_llm()
    search_tool = TavilySearch()
    
    # --- LÓGICA GOOGLE VERTEX AI + WEB (HÍBRIDO NUVEM) ---
    if google_corpus_id:
        # Para o modo híbrido nuvem, idealmente faríamos a busca Web e passaríamos para o Gemini junto com o Corpus.
        # Por simplificação e robustez inicial, faremos a chamada ao Corpus Vertex (que já é potente) 
        # e podemos concatenar com busca Web se necessário.
        # Mas o 'consultar_corpus_vertex' encapsula a chamada ao modelo.
        # Então, vamos fazer uma versão simplificada onde a Web Search é injetada no prompt do Vertex?
        # Ou melhor, manteremos o Vertex como fonte primária.
        
        # P.S. O prompt diz "Se preenchido, o sistema ignorará os arquivos locais".
        # Não disse explicitamente como combinar Web + Vertex.
        # Vou implementar: Vertex Corpus (Substituindo FAISS) + Tavily Web Search.
        
        # Como 'consultar_corpus_vertex' já chama o modelo final, fica difícil injetar o contexto da Web nele sem refatorar o engine.
        # DECISÃO ESTRATÉGICA: No modo Híbrido com Google, usamos APENAS o Google Vertex RAG por enquanto, 
        # pois o 'Grounding' do Google pode incluir Web Search se configurado no Agent Builder.
        # Mas para obedecer estritamente "ignorar arquivos locais", retornaremos o Vertex Chain.
        
        def vertex_hybrid_chain_func(input_dict):
            query = input_dict["input"]
            # Poderíamos fazer a busca web aqui e passar como parte da query para o Vertex?
            # Ex: query = f"{query} \n\n Contexto Web: {tavily_result}"
            # Vamos fazer isso para garantir o "Híbrido".
            web_results = search_tool.invoke({"query": query})
            augmented_query = f"Pergunta do usuário: {query}\n\nInformações adicionais da Web (Tavily): {web_results}"
            
            resposta = consultar_corpus_vertex(augmented_query, google_corpus_id)
            return {"answer": resposta, "context": []}

        return RunnableLambda(vertex_hybrid_chain_func)

    # --- LÓGICA LEGADA (FAISS + WEB) ---
    vectorstore = load_persistent_vectorstore()
    if vectorstore is None: st.error("Base de conhecimento não criada."); st.stop()

    base_retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})

    def filter_documents(docs):
        return [doc for doc in docs if doc.metadata.get("set_id") in set(allowed_set_ids)]

    filtered_retriever = base_retriever | RunnableLambda(filter_documents)
    
    prompt = ChatPromptTemplate.from_template(persona_prompt)

    context_chain = RunnablePassthrough.assign(
        context=lambda x: filtered_retriever.invoke(x["input"]),
        web_search_results=lambda x: search_tool.invoke({"query": x["input"]}),
        input=lambda x: x["input"]
    )

    response_chain = context_chain | prompt | llm | StrOutputParser()

    final_chain = RunnablePassthrough.assign(answer=response_chain, context=context_chain.pick("context"))
    return final_chain

from src.config import get_llm, get_embeddings_model, FAISS_INDEX_PATH

def get_seo_analysis_chain(persona_prompt, input_text, keyword, url):
    llm = get_llm()
    embeddings_model = get_embeddings_model()
    search_tool = TavilySearch()

    # Definir o prompt para o agente de SEO, agora incluindo dados de PageSpeed
    prompt_template = ChatPromptTemplate.from_template("""
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
        *   **Instruções para WordPress:** Abaixo do código do schema, adicione uma nota explicando como implementá-lo: "Para usar no WordPress, copie o código JSON-LD acima e cole-o na seção 'Schema' do seu plugin de SEO (Yoast, Rank Math) ou em um bloco 'HTML Personalizado'."
        *   **Sugestões de Elementos Visuais:** Inclua uma subseção com ideias para enriquecer visualmente o post, como infográficos, screenshots de dashboards, tabelas comparativas, e a importância de alt text descritivo para cada um.
        *   **Análise da SERP e Concorrência:** Com base nos `web_search_results`, analise os top 3-5 concorrentes. Identifique padrões de conteúdo, intenção de busca que eles respondem e "gaps de conteúdo" que o post otimizado pode explorar.
        *   **KPIs para Monitoramento:** Sugira 2-3 métricas chave para acompanhar o sucesso do post (ex: Ranking da Palavra-chave Foco, CTR Orgânico, Tempo na Página).
        *   **Recomendações para E-A-T (Expertise, Authoritativeness, Trustworthiness):** Forneça sugestões específicas para fortalecer a autoridade do post (ex: biografia do autor, citações de fontes, links para estudos).
        *   Ofereça sugestões adicionais (outros schemas como 'Article', etc.), priorizando "Quick Wins" sempre que possível.
    """)

    # Criar a cadeia que primeiro busca na web, analisa a legibilidade, verifica o PageSpeed e depois chama o LLM
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

    # Invocar a cadeia para obter a análise inicial do LLM
    initial_analysis = chain.invoke({"persona_prompt": persona_prompt, "input_text": input_text, "keyword": keyword, "url": url})

    # Por enquanto, retornamos apenas a análise inicial do LLM.
    return {"answer": initial_analysis, "context": []}


# --- LÓGICA DO ASSISTENTE DE CRIAÇÃO DE PERSONA ---

# --- V1 (FLUXO DIRETO) ---
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
    """
    Usa o LLM para gerar o prompt final diretamente do diagnóstico fornecido pelo formulário.
    """
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_GERACAO_DIRETA)

    geracao_chain = prompt_template | llm | StrOutputParser()

    # O dicionário 'diagnostico' do formulário é passado diretamente para o prompt.
    return geracao_chain.invoke(diagnostico)

# --- V2 (FLUXO 3-PASSOS) ---

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
    """Usa o LLM para gerar sugestões de abordagens de prompt."""
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_BRAINSTORMING)
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke(diagnostico)

def gerar_prompt_final_com_abordagem(diagnostico: dict, diretriz_abordagem: str) -> str:
    """Usa o LLM para gerar o prompt final com base no diagnóstico e na abordagem escolhida."""
    llm = get_llm()
    prompt_template = ChatPromptTemplate.from_template(PROMPT_ASSISTENTE_EXECUCAO)
    chain = prompt_template | llm | StrOutputParser()

    input_data = {**diagnostico, "diretriz_abordagem": diretriz_abordagem}

    return chain.invoke(input_data)
