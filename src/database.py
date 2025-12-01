# src/database.py (VERSÃO REVISADA E PADRONIZADA)

import os
from sqlalchemy import create_engine, text
import streamlit as st
from dotenv import load_dotenv

# --- DADOS PADRÃO ---
PERSONAS_PADRAO = {
    "Consultor Geral": {
        "prompt": "Você é um consultor especialista no sistema DiamondOne...",
        "access_level": "RAG_ONLY"
    },
    "Estrategista de Marketing": {
        "prompt": "Você é o 'Marketer DiamondOne', um especialista em marketing...",
        "access_level": "RAG_ONLY"
    },
    "Analista de Implementação": {
        "prompt": "Você é um Analista de Implementação Sênior do DiamondOne...",
        "access_level": "RAG_ONLY"
    },
    "Analista de Conhecimento (Híbrido)": {
        "prompt": "Você é um 'Analista de Conhecimento' sênior...",
        "access_level": "HYBRID"
    }
}

# --- CONEXÃO COM O BANCO ---
@st.cache_resource
def get_db_engine():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error("FATAL: URL do Banco de Dados não encontrada.")
        st.stop()

    connect_args = {
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args
    )

# --- FUNÇÕES DE ESTRUTURA (DDL) ---
def create_tables():
    """Cria as tabelas necessárias no banco de dados se não existirem."""
    engine = get_db_engine()
    try:
        with engine.connect() as connection:
            
            # 1. Tabela de Roles (Antiga Profiles) - Padronizado para 'roles'
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) UNIQUE NOT NULL,
                    description TEXT
                );
            """))

            # 2. Tabela de Usuários
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100),
                    password VARCHAR(255) NOT NULL,
                    role_id INTEGER REFERENCES roles(id),
                    role VARCHAR(20) CHECK (role IN ('admin', 'gerente', 'usuario')) -- Mantido para compatibilidade legada
                );
            """))

            # 3. Tabelas de Permissões (RBAC) - Faltavam na versão anterior
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT
                );
            """))

            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                    permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
                    PRIMARY KEY (role_id, permission_id)
                );
            """))

            # 4. Tabela de Personas
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS personas (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(100) UNIQUE NOT NULL, -- Corrigido para 'nome' (pt-br) conforme queries
                    description TEXT,
                    prompt TEXT NOT NULL,
                    knowledge_set_id INTEGER,
                    criado_por VARCHAR(100),
                    access_level VARCHAR(20) DEFAULT 'RAG_ONLY',
                    google_corpus_id VARCHAR(255),
                    model_id VARCHAR(50) -- Novo campo: Modelo de IA específico
                );
            """))
            
            # 5. Histórico de Personas
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS persona_history (
                    id SERIAL PRIMARY KEY,
                    persona_id INTEGER REFERENCES personas(id) ON DELETE CASCADE,
                    prompt TEXT,
                    access_level VARCHAR(20),
                    changed_by VARCHAR(100),
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))

            # ... (tabelas knowledge_sets, links, documents, chat_history mantidas) ...
            
            # 6. Tabela de Conjuntos de Conhecimento
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS knowledge_sets (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_by VARCHAR(100)
                );
            """))
            
            # 7. Tabela de Links Persona-Conhecimento
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS persona_knowledge_links (
                    persona_id INTEGER REFERENCES personas(id) ON DELETE CASCADE,
                    set_id INTEGER REFERENCES knowledge_sets(id) ON DELETE CASCADE,
                    PRIMARY KEY (persona_id, set_id)
                );
            """))

            # 8. Tabela de Documentos
            # Padronizado para 'filename' para bater com as queries
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL, 
                    set_id INTEGER REFERENCES knowledge_sets(id) ON DELETE CASCADE,
                    UNIQUE(filename, set_id)
                );
            """))

            # 9. Tabela de Histórico de Chat (Antiga chat_logs)
            # Padronizado para 'chat_history' e colunas corretas
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER REFERENCES users(id),
                    persona_id INTEGER REFERENCES personas(id),
                    question TEXT,
                    answer TEXT,
                    context TEXT,
                    feedback VARCHAR(10),
                    feedback_comment TEXT
                );
            """))

            # --- AUTO-MIGRAÇÕES DE SEGURANÇA ---
            try:
                connection.execute(text("ALTER TABLE personas ADD COLUMN google_corpus_id VARCHAR(255);"))
                print("Migração: Coluna google_corpus_id adicionada.")
            except Exception:
                connection.rollback()
                pass

            try:
                connection.execute(text("ALTER TABLE personas ADD COLUMN model_id VARCHAR(50);"))
                print("Migração: Coluna model_id adicionada.")
            except Exception:
                connection.rollback()
                pass
            
            # Garante roles básicos
            try:
                connection.execute(text("INSERT INTO roles (name) VALUES ('admin'), ('gerente'), ('usuario') ON CONFLICT (name) DO NOTHING;"))
                connection.commit()
            except Exception:
                connection.rollback()
                pass

            connection.commit()
            print("Tabelas verificadas/criadas com sucesso.")

    except Exception as e:
        print(f"Erro crítico ao criar tabelas: {e}")
        raise e

# --- FUNÇÕES DE USUÁRIOS ---
def fetch_all_users():
    engine = get_db_engine()
    users = {}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT username, name, password FROM users;"))
            for row in result:
                users[row.username] = {'name': row.name, 'password': row.password}
            return users
    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
        return {}

def create_admin_user(username, name, hashed_password):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Busca ID da role admin
        role_id_result = connection.execute(text("SELECT id FROM roles WHERE name = 'admin'")).scalar_one_or_none()
        
        # Se não existir role, cria (fallback)
        if not role_id_result:
            connection.execute(text("INSERT INTO roles (name) VALUES ('admin')"))
            connection.commit()
            role_id_result = connection.execute(text("SELECT id FROM roles WHERE name = 'admin'")).scalar_one()

        connection.execute(
            text("INSERT INTO users (username, name, password, role_id, role) VALUES (:user, :name, :pwd, :rid, 'admin') ON CONFLICT (username) DO NOTHING;"),
            {"user": username, "name": name, "pwd": hashed_password, "rid": role_id_result}
        )
        connection.commit()

def get_user_id(username):
    engine = get_db_engine()
    with engine.connect() as connection:
        return connection.execute(text("SELECT id FROM users WHERE username = :user"), {"user": username}).scalar_one_or_none()

def get_user_role_name(username):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Tenta pegar pelo JOIN com roles, se falhar, pega a coluna legada 'role'
        try:
            query = text("SELECT r.name FROM roles r JOIN users u ON u.role_id = r.id WHERE u.username = :user;")
            res = connection.execute(query, {"user": username}).scalar_one_or_none()
            if res: return res
            
            # Fallback legado
            return connection.execute(text("SELECT role FROM users WHERE username = :user"), {"user": username}).scalar_one_or_none()
        except:
            return None

@st.cache_data(ttl=60)
def fetch_all_user_details():
    engine = get_db_engine()
    with engine.connect() as connection:
        query = text("SELECT u.id, u.username, u.name, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id ORDER BY u.username;")
        return connection.execute(query).fetchall()

def create_user(username, name, password, role_name):
    engine = get_db_engine()
    with engine.connect() as connection:
        role_id_result = connection.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}).scalar_one_or_none()
        if not role_id_result:
             raise ValueError(f"Perfil '{role_name}' não encontrado.")
        
        connection.execute(
            text("INSERT INTO users (username, name, password, role_id, role) VALUES (:user, :name, :pwd, :rid, :rname);"),
            {"user": username, "name": name, "pwd": password, "rid": role_id_result, "rname": role_name}
        )
        connection.commit()
    st.cache_data.clear()

def update_user_role(username, new_role):
    engine = get_db_engine()
    with engine.connect() as connection:
        role_id = connection.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": new_role}).scalar_one()
        connection.execute(
            text("UPDATE users SET role_id = :rid, role = :rname WHERE username = :user;"),
            {"rid": role_id, "rname": new_role, "user": username}
        )
        connection.commit()
    st.cache_data.clear()

def update_user_password(username, new_password):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(text("UPDATE users SET password = :pwd WHERE username = :user;"), {"pwd": new_password, "user": username})
        connection.commit()
    st.cache_data.clear()

def delete_user(username):
    engine = get_db_engine()
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            # Pega ID
            uid = connection.execute(text("SELECT id FROM users WHERE username = :user"), {"user": username}).scalar_one_or_none()
            if uid:
                connection.execute(text("UPDATE chat_history SET user_id = NULL WHERE user_id = :uid"), {"uid": uid})
                connection.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise e
    st.cache_data.clear()

# --- FUNÇÕES DE PERFIS E PERMISSÕES (RBAC) ---
@st.cache_data(ttl=300)
def get_user_permissions(username):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Busca as permissões baseadas na role do usuário
        query = text("""
            SELECT p.name 
            FROM permissions p 
            JOIN role_permissions rp ON p.id = rp.permission_id 
            JOIN users u ON rp.role_id = u.role_id 
            WHERE u.username = :user;
        """)
        result = connection.execute(query, {"user": username})
        return {row.name for row in result}

@st.cache_data(ttl=300)
def fetch_all_roles():
    engine = get_db_engine()
    with engine.connect() as connection:
        return connection.execute(text("SELECT id, name FROM roles ORDER BY name;")).fetchall()

@st.cache_data(ttl=300)
def fetch_permissions_for_role(role_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Correção Sintaxe text()
        result = connection.execute(
            text("SELECT permission_id FROM role_permissions WHERE role_id = :rid;"), 
            {"rid": role_id}
        )
        return {row.permission_id for row in result}

def update_role_permissions(role_id, new_permission_ids):
    engine = get_db_engine()
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            connection.execute(text("DELETE FROM role_permissions WHERE role_id = :rid;"), {"rid": role_id})
            if new_permission_ids:
                params = [{"rid": role_id, "pid": pid} for pid in new_permission_ids]
                connection.execute(
                    text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid);"),
                    params
                )
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise e
    st.cache_data.clear()

@st.cache_data(ttl=300)
def fetch_all_permissions():
    engine = get_db_engine()
    with engine.connect() as connection:
        return connection.execute(text("SELECT id, name, description FROM permissions ORDER BY name;")).fetchall()

# --- FUNÇÕES DE PERSONAS ---
@st.cache_data(ttl=600)
def fetch_personas():
    engine = get_db_engine()
    personas = {}
    with engine.connect() as connection:
        # Busca nome, prompt, google_corpus_id, model_id
        result = connection.execute(text("SELECT id, nome, prompt, access_level, google_corpus_id, model_id FROM personas ORDER BY nome;"))
        for row in result:
            personas[row.nome] = {
                "id": row.id, 
                "prompt": row.prompt, 
                "access_level": row.access_level,
                "google_corpus_id": row.google_corpus_id,
                "model_id": row.model_id
            }
    return personas

def create_persona(nome, prompt, criador, access_level, google_corpus_id=None, model_id=None):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(
            text("""
                INSERT INTO personas (nome, prompt, criado_por, access_level, google_corpus_id, model_id) 
                VALUES (:nome, :prompt, :criador, :level, :gcid, :mid);
            """), 
            {"nome": nome, "prompt": prompt, "criador": criador, "level": access_level, "gcid": google_corpus_id, "mid": model_id}
        )
        connection.commit()
    st.cache_data.clear()

def update_persona(nome, prompt, access_level, changed_by, save_history=True, google_corpus_id=None, model_id=None):
    engine = get_db_engine()
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            if save_history:
                current_persona = connection.execute(text("SELECT id, prompt, access_level FROM personas WHERE nome = :nome"), {"nome": nome}).first()
                if current_persona:
                    connection.execute(
                        text("""INSERT INTO persona_history (persona_id, prompt, access_level, changed_by) VALUES (:pid, :prompt, :level, :user);"""),
                        {"pid": current_persona.id, "prompt": current_persona.prompt, "level": current_persona.access_level, "user": changed_by}
                    )
            
            connection.execute(
                text("""
                    UPDATE personas 
                    SET prompt = :prompt, access_level = :level, google_corpus_id = :gcid, model_id = :mid
                    WHERE nome = :nome;
                """), 
                {"prompt": prompt, "level": access_level, "gcid": google_corpus_id, "mid": model_id, "nome": nome}
            )
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise e
    st.cache_data.clear()

def delete_persona(nome):
    engine = get_db_engine()
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            persona_id = connection.execute(text("SELECT id FROM personas WHERE nome = :nome;"), {"nome": nome}).scalar_one_or_none()
            if persona_id:
                connection.execute(text("DELETE FROM persona_knowledge_links WHERE persona_id = :pid;"), {"pid": persona_id})
                connection.execute(text("DELETE FROM persona_history WHERE persona_id = :pid;"), {"pid": persona_id})
                connection.execute(text("UPDATE chat_history SET persona_id = NULL WHERE persona_id = :pid;"), {"pid": persona_id})
                connection.execute(text("DELETE FROM personas WHERE id = :pid;"), {"pid": persona_id})
            trans.commit()
        except Exception as e:
            trans.rollback()
            raise e
    st.cache_data.clear()

def fetch_persona_history(persona_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        query = text("SELECT prompt, access_level, changed_by, changed_at FROM persona_history WHERE persona_id = :pid ORDER BY changed_at DESC;")
        # Correção sintaxe
        return connection.execute(query, {"pid": persona_id}).fetchall()

def create_default_personas(criador):
    engine = get_db_engine()
    with engine.connect() as connection:
        for nome, data in PERSONAS_PADRAO.items():
            connection.execute(
                text("INSERT INTO personas (nome, prompt, criado_por, access_level) VALUES (:nome, :prompt, :criador, :level) ON CONFLICT (nome) DO NOTHING;"),
                {"nome": nome, "prompt": data['prompt'], "criador": criador, "level": data['access_level']}
            )
        connection.commit()
    st.cache_data.clear()

# --- FUNÇÕES DE CONHECIMENTO ---
@st.cache_data(ttl=600)
def fetch_knowledge_sets():
    engine = get_db_engine()
    sets = {}
    with engine.connect() as connection:
        result = connection.execute(text("SELECT id, name, description FROM knowledge_sets ORDER BY name;"))
        for row in result:
            sets[row.name] = {"id": row.id, "description": row.description}
    return sets

def create_knowledge_set(name, description, creator):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(
            text("INSERT INTO knowledge_sets (name, description, created_by) VALUES (:name, :desc, :creator);"),
            {"name": name, "desc": description, "creator": creator}
        )
        connection.commit()
    st.cache_data.clear()

def delete_knowledge_set(set_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM knowledge_sets WHERE id = :id;"), {"id": set_id})
        connection.commit()
    st.cache_data.clear()

def add_document_record(filename, set_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(
            text("INSERT INTO documents (filename, set_id) VALUES (:fname, :sid) ON CONFLICT (filename, set_id) DO NOTHING;"),
            {"fname": filename, "sid": set_id}
        )
        connection.commit()
    st.cache_data.clear()

@st.cache_data(ttl=60)
def list_documents_in_set(set_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Correção sintaxe
        result = connection.execute(
            text("SELECT filename FROM documents WHERE set_id = :sid ORDER BY filename;"), 
            {"sid": set_id}
        )
        return [row.filename for row in result]

def delete_document_record(filename, set_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(
            text("DELETE FROM documents WHERE filename = :fname AND set_id = :sid;"), 
            {"fname": filename, "sid": set_id}
        )
        connection.commit()
    st.cache_data.clear()

def link_persona_to_sets(persona_id, set_ids):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM persona_knowledge_links WHERE persona_id = :pid;"), {"pid": persona_id})
        for set_id in set_ids:
            connection.execute(
                text("INSERT INTO persona_knowledge_links (persona_id, set_id) VALUES (:pid, :sid);"),
                {"pid": persona_id, "sid": set_id}
            )
        connection.commit()
    st.cache_data.clear()

@st.cache_data(ttl=600)
def fetch_linked_sets_for_persona(persona_id):
    engine = get_db_engine()
    with engine.connect() as connection:
        # Correção sintaxe
        result = connection.execute(
            text("SELECT set_id FROM persona_knowledge_links WHERE persona_id = :pid;"),
            {"pid": persona_id}
        )
        return [row.set_id for row in result]

# --- FUNÇÕES DE HISTÓRICO E FEEDBACK ---
def log_chat_interaction(user_id, persona_id, session_id, question, answer, context):
    engine = get_db_engine()
    with engine.connect() as connection:
        context_str = "\n---\n".join([f"Fonte: {doc.metadata.get('source', 'N/A')}\n\n{doc.page_content}" for doc in context]) if context else ""
        
        # Inserção correta na tabela chat_history
        result = connection.execute(
            text("""INSERT INTO chat_history (user_id, persona_id, session_id, question, answer, context) 
                    VALUES (:uid, :pid, :sid, :q, :a, :c) RETURNING id;"""),
            { "uid": user_id, "pid": persona_id, "sid": session_id, "q": question, "a": answer, "c": context_str }
        )
        connection.commit()
        return result.scalar_one()

def register_feedback(interaction_id, feedback_score, comment=None):
    engine = get_db_engine()
    with engine.connect() as connection:
        connection.execute(
            text("UPDATE chat_history SET feedback = :score, feedback_comment = :comment WHERE id = :interaction_id;"), 
            {"score": feedback_score, "comment": comment, "interaction_id": interaction_id}
        )
        connection.commit()
    st.cache_data.clear()

@st.cache_data(ttl=300)
def fetch_full_chat_history():
    engine = get_db_engine()
    query = text("""
        SELECT
            ch.id, ch.session_id, u.username, p.nome as persona_name,
            ch.question, ch.answer, ch.context, ch.feedback,
            ch.feedback_comment, ch.timestamp
        FROM chat_history ch
        LEFT JOIN users u ON ch.user_id = u.id
        LEFT JOIN personas p ON ch.persona_id = p.id
        ORDER BY ch.timestamp DESC;
    """)
    try:
        with engine.connect() as connection:
            result = connection.execute(query)
            return result.fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar o histórico de chat: {e}")
        return []

def fetch_all_document_paths():
    engine = get_db_engine()
    with engine.connect() as connection:
        result = connection.execute(text("SELECT filename, set_id FROM documents;"))
        base_path = "temp_uploaded_files"
        return [(os.path.join(base_path, row.filename), row.set_id) for row in result]

def get_user_role(username):
    """
    Função legada para manter compatibilidade com as páginas que chamam get_user_role.
    Apenas redireciona para a nova lógica ou busca diretamente.
    """
    return get_user_role_name(username)