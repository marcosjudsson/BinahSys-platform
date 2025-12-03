# BinahSys - Plataforma de IA Conversacional

## Visão Geral

O BinahSys é uma plataforma inteligente que integra modelos de linguagem de larga escala (LLMs) com bases de conhecimento para fornecer respostas precisas e contextualizadas. Ele suporta tanto bases de conhecimento locais (FAISS) quanto integração com serviços de RAG na nuvem (Google Vertex AI).

---

## 🚀 Como Executar Localmente

1.  **Clone o repositório:**
    `git clone <URL_DO_REPOSITORIO>`
    `cd BinahSys`

2.  **Crie e ative o ambiente virtual:**
    `python -m venv venv`
    `.\venv\Scripts\activate` (Windows PowerShell)
    `source venv/bin/activate` (Linux/macOS)

3.  **Instale as dependências:**
    `pip install -r requirements.txt`

4.  **Configure as variáveis de ambiente:**
    Crie um arquivo `.env` na raiz do projeto ou configure as variáveis diretamente no `st.secrets`.

5.  **Execute o Streamlit:**
    `streamlit run app.py`

---

## ⚙️ Variáveis de Ambiente Críticas

Estas variáveis devem ser configuradas no arquivo `.env` (para execução local) ou na seção `Secrets` do Streamlit Cloud (para deploy):

*   **`DATABASE_URL`**: URL de conexão com o banco de dados PostgreSQL.
    *   Ex: `postgresql://user:password@host:port/database`
*   **`GOOGLE_PROJECT_ID`**: ID do seu projeto no Google Cloud Platform.
*   **`GOOGLE_LOCATION`**: Região onde seu Vertex AI RAG Corpus está hospedado (ex: `europe-west4`).
*   **`TAVILY_API_KEY`**: Chave da API Tavily Search para buscas na web.
*   **`PAGESPEED_API_KEY`**: Chave da API Google PageSpeed Insights.
*   **`GOOGLE_CREDENTIALS`**: **APENAS para Streamlit Cloud.** Chave JSON da sua Service Account do GCP, formatada como TOML no `st.secrets`.
    *   *Exemplo no `st.secrets`:*
        ```toml
        [GOOGLE_CREDENTIALS]
        type = "service_account"
        project_id = "seu-projeto-id"
        private_key_id = "..."
        private_key = "-----BEGIN PRIVATE KEY-----\n..."
        client_email = "..."
        client_id = "..."
        auth_uri = "https://accounts.google.com/o/oauth2/auth"
        token_uri = "https://oauth2.googleapis.com/token"
        auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
        client_x509_cert_url = "..."
        universe_domain = "googleapis.com"
        ```

---

## 🛠️ Dependências Críticas

*   **`langchain` / `langchain-classic`**: Frameworks para construção de aplicações com LLMs.
*   **`google-genai`**: SDK oficial para integração com modelos Gemini da Google.
*   **`python-docx`**: Para geração de documentos `.docx`.
*   **`psycopg2-binary`**: Driver PostgreSQL para conexão com o banco de dados.
*   **`streamlit`**: Framework para construção da interface de usuário.

---

## 🧩 Arquitetura

Consulte `3. Recursos/DiamondOne/ARCHITECTURE.md` para uma visão detalhada da arquitetura do sistema, incluindo a estratégia de RAG Híbrida e a Arquitetura Cross-Region.

---

## ⚠️ Solução de Problemas

Consulte `3. Recursos/DiamondOne/TROUBLESHOOTING.md` para problemas comuns e suas soluções.
