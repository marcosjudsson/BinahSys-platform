# pages/1_Chat_com_Especialista.py (VERSÃO COM SPINNER DE PROCESSAMENTO)

import streamlit as st
from src.C_auth import check_authentication
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
import uuid
import os
import tempfile
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader

from src.database import (
    get_user_role, fetch_personas, fetch_linked_sets_for_persona,
    get_user_id, log_chat_interaction, register_feedback
)
from src.chat_logic import get_rag_chain, get_web_search_chain, get_hybrid_chain

# --- FUNÇÃO AUXILIAR PARA PROCESSAR ARQUIVO ---
def processar_arquivo_temporario(uploaded_file):
    """Lê o conteúdo de um arquivo enviado e retorna como texto."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        loader = None
        if tmp_file_path.endswith(".pdf"):
            loader = PyPDFLoader(tmp_file_path)
        elif tmp_file_path.endswith(".docx"):
            loader = Docx2txtLoader(tmp_file_path)
        elif tmp_file_path.endswith(".txt"):
            loader = TextLoader(tmp_file_path)

        if loader:
            document = loader.load()
            os.remove(tmp_file_path)
            return "\n".join([doc.page_content for doc in document])
        else:
            os.remove(tmp_file_path)
            return None
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return None

st.set_page_config(page_title="Chat com Especialista", layout="wide")

# --- BLOCO DE SEGURANÇA E INICIALIZAÇÃO ---
check_authentication()

load_dotenv()
username = st.session_state.get("username")
user_id = get_user_id(username)
user_role = get_user_role(username)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'commenting_on' not in st.session_state:
    st.session_state.commenting_on = None

# --- SIDEBAR (sem alterações) ---
with st.sidebar:
    st.header("Configurações do Chat")
    personas_db = fetch_personas()
    if not personas_db:
        st.warning("Nenhuma persona encontrada. Crie uma no Gerenciador de Personas.")
        st.stop()

    persona_selecionada_nome = st.selectbox("Selecione a Persona:", options=list(personas_db.keys()))
    tipo_acesso = personas_db.get(persona_selecionada_nome, {}).get('access_level', 'N/A')
    st.caption(f"Tipo de Acesso: {tipo_acesso.replace('_', ' ').title()}")

    st.divider()

    if st.button("🗑️ Limpar Histórico da Conversa"):
        if persona_selecionada_nome in st.session_state.chat_history:
            st.session_state.chat_history[persona_selecionada_nome] = []
            st.toast("Histórico limpo!")
            st.rerun()

# --- ÁREA PRINCIPAL DO CHAT ---
st.header(f"🤖 Chat com: {persona_selecionada_nome}")

if persona_selecionada_nome not in st.session_state.chat_history:
    st.session_state.chat_history[persona_selecionada_nome] = []

# Exibe o histórico
for message_data in st.session_state.chat_history[persona_selecionada_nome]:
    message = message_data["message"]
    with st.chat_message(message.type):
        st.markdown(message.content)

        if message.type == "ai":
            with st.expander("Copiar Resposta"):
                st.code(message.content, language=None)

        if message.type == "ai" and "context" in message_data and message_data["context"]:
            with st.expander("Ver fontes utilizadas"):
                for doc in message_data["context"]:
                    source_name = os.path.basename(doc.metadata.get('source', 'Fonte desconhecida'))
                    st.info(f"**Fonte:** {source_name}")
                    st.code(doc.page_content, language='text')

        if message.type == "ai" and "interaction_id" in message_data:
            interaction_id = message_data["interaction_id"]
            feedback_key = f"feedback_{interaction_id}"

            if feedback_key not in st.session_state:
                st.session_state[feedback_key] = message_data.get("feedback_value")

            col1, col2, _ = st.columns([1, 1, 10])
            disable_buttons = st.session_state[feedback_key] is not None

            with col1:
                if st.button("👍", key=f"like_{interaction_id}", disabled=disable_buttons):
                    register_feedback(interaction_id, 1, comment="Feedback positivo.")
                    st.session_state[feedback_key] = 1
                    st.toast("Feedback positivo registrado!")
                    st.rerun()
            with col2:
                if st.button("👎", key=f"dislike_{interaction_id}", disabled=disable_buttons):
                    st.session_state.commenting_on = interaction_id
                    st.rerun()

            if st.session_state.commenting_on == interaction_id:
                with st.form(f"comment_form_{interaction_id}"):
                    comment = st.text_area("Por favor, descreva o motivo do seu feedback:", key=f"comment_input_{interaction_id}")
                    if st.form_submit_button("Enviar Comentário"):
                        register_feedback(interaction_id, -1, comment=comment)
                        st.session_state[feedback_key] = -1
                        st.session_state.commenting_on = None
                        st.toast("Feedback e comentário enviados. Obrigado!")
                        st.rerun()

# Campo de input do usuário

arquivo_temporario = st.file_uploader(
    "Anexar um documento para esta sessão (temporário)",
    type=["pdf", "docx", "txt"],
    help="O documento será usado apenas para a próxima pergunta e não será salvo na base de conhecimento."
)

if prompt_usuario := st.chat_input("Faça sua pergunta aqui..."):

    conteudo_arquivo = None

    if arquivo_temporario:
        with st.spinner("Processando o documento anexado..."):
            conteudo_arquivo = processar_arquivo_temporario(arquivo_temporario)

    # Prepara o prompt final, incluindo o conteúdo do arquivo se houver
    prompt_final = prompt_usuario

    if conteudo_arquivo:
        st.info("Analisando com base no documento anexado.")
        prompt_final = f"""
Use o seguinte documento como contexto principal para responder à pergunta.

--- CONTEÚDO DO DOCUMENTO ---

{conteudo_arquivo}

--- PERGUNTA DO USUÁRIO ---

{prompt_usuario}
"""

    st.session_state.chat_history[persona_selecionada_nome].append({"message": HumanMessage(content=prompt_usuario)})

    with st.chat_message("human"):
        st.markdown(prompt_usuario)

    with st.chat_message("ai"):
        with st.spinner("Pensando..."):
            try:
                persona_data = personas_db[persona_selecionada_nome]
                persona_id, persona_prompt_texto, access_level = persona_data['id'], persona_data['prompt'], persona_data['access_level']
                
                # ATUALIZADO: Extraindo Google Corpus ID e Model ID
                google_corpus_id = persona_data.get('google_corpus_id')
                model_id = persona_data.get('model_id') # Novo campo

                chat_history_for_chain = [d["message"] for d in st.session_state.chat_history[persona_selecionada_nome][:-1]]

                chain = None

                if access_level == "RAG_ONLY":
                    allowed_set_ids = fetch_linked_sets_for_persona(persona_id)
                    # ATUALIZADO: Só erro se não tiver conjuntos E não tiver Google Corpus
                    if not allowed_set_ids and not google_corpus_id: 
                        st.error(f"Persona '{persona_selecionada_nome}' sem vínculo a Conjuntos de Conhecimento."); st.stop()
                    
                    # ATUALIZADO: Passando o ID e o Model ID
                    chain = get_rag_chain(persona_prompt_texto, allowed_set_ids, google_corpus_id, model_id)

                elif access_level == "WEB_ONLY":
                    # Web Only geralmente usa o padrão ou podemos passar o model_id se get_web_search_chain suportar (não implementado nesta task, mas idealmente deveria)
                    chain = get_web_search_chain(persona_prompt_texto)

                elif access_level == "HYBRID":
                    allowed_set_ids = fetch_linked_sets_for_persona(persona_id)
                    # ATUALIZADO: Passando o ID e o Model ID
                    chain = get_hybrid_chain(persona_prompt_texto, allowed_set_ids, google_corpus_id, model_id)

                if chain:
                    response = chain.invoke({"input": prompt_final, "chat_history": chat_history_for_chain})

                    resposta_completa = response.get("answer", "Não foi possível gerar uma resposta.")
                    contexto_usado = response.get("context", [])

                    st.markdown(resposta_completa)

                    if resposta_completa:
                        interaction_id = log_chat_interaction(
                            user_id=user_id, persona_id=persona_id, session_id=st.session_state.session_id,
                            question=prompt_usuario, answer=resposta_completa, context=contexto_usado
                        )

                        st.session_state.chat_history[persona_selecionada_nome].append({
                            "message": AIMessage(content=resposta_completa),
                            "interaction_id": interaction_id,
                            "context": contexto_usado,
                            "feedback_value": None
                        })
                        st.rerun()
                else:
                    st.error("Tipo de acesso da persona desconhecido.")

            except Exception as e:
                st.error(f"Ocorreu um erro ao gerar a resposta: {e}")
