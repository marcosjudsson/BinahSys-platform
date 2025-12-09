# Projeto: Automação de Ingestão de Documentos para IA

## 1. Objetivo

Este projeto implementa um pipeline de automação para resolver o desafio de transformar documentos estáticos (manuais, tickets, etc.) em uma base de conhecimento "viva" e "conversável", que pode ser utilizada por uma Inteligência Artificial.

O objetivo da Prova de Conceito (PoC) é demonstrar um fluxo de trabalho "mágico" e de baixa manutenção, onde um usuário simplesmente coloca um arquivo em uma pasta específica no Google Drive e ele se torna automaticamente parte do conhecimento de um "Tutor" de IA, sem intervenção manual.

## 2. Como Funciona (Visão Geral)

O fluxo de trabalho para o usuário final é extremamente simples:

1.  **Adicionar Arquivo:** Um usuário coloca um ou mais arquivos (ex: `Manual Diamond.pdf`) na pasta `D1 - Manuais` dentro do Drive Compartilhado `Rota da Seda/Transporte - IA`.

2.  **Automação Agendada:** A cada hora, um "robô" (GitHub Actions) é acionado automaticamente. Ele verifica a pasta `D1 - Manuais` em busca de novos arquivos.

3.  **Processamento e Ingestão:** O robô identifica os novos arquivos, faz o download e os envia para a API do Gemini. A API do Gemini processa e indexa o conteúdo, tornando-o pesquisável.

4.  **Confirmação Visual:** Após o envio bem-sucedido para o Gemini, o robô move o arquivo original da pasta `D1 - Manuais` para a pasta `D1 - Manuais (Processados)`. Isso serve como uma confirmação visual clara de que o arquivo foi processado.

O robô também mantém um registro (`processed_files.json`) dos arquivos que já processou para não fazer o trabalho em duplicidade.

## 3. Arquitetura Técnica

| Componente              | Tecnologia / Abordagem                                                                                             | Justificativa                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Repositório**         | GitHub (Privado)                                                                                                   | Controle de versão e base para a automação.                                                               |
| **Linguagem**           | Python 3                                                                                                           | Linguagem versátil e com excelente suporte das bibliotecas do Google e Gemini.                            |
| **Automação**           | GitHub Actions                                                                                                     | Solução serverless e integrada ao repositório, que contorna a necessidade de um faturamento no Google Cloud para a PoC. |
| **Agendamento**         | `schedule: cron` (a cada hora)                                                                                     | Execução periódica e automática do pipeline.                                                              |
| **Autenticação (Drive)**| Google Service Account                                                                                             | Autenticação não interativa, ideal para ambientes automatizados como o GitHub Actions.                    |
| **Autenticação (Gemini)**| Chave de API (API Key)                                                                                             | Método de autenticação padrão para a API do Gemini.                                                       |
| **Gerenciamento de Segredos** | GitHub Secrets (`GCP_SA_KEY`, `GEMINI_API_KEY`)                                                                    | Armazenamento seguro das credenciais, que não ficam expostas no código.                                    |
| **Lógica do Script**    | `main.py`                                                                                                          | Orquestra todo o fluxo: autenticação, listagem, download, upload e movimentação dos arquivos.             |
| **Rastreamento de Estado**  | `processed_files.json` (persistido via `actions/cache`)                                                            | Mecanismo simples e eficaz para evitar reprocessamento de arquivos, usando o cache do GitHub Actions.     |

## 4. Próximos Passos

Com o pipeline de ingestão de dados 100% funcional, o próximo passo é construir a interface do **"Tutor da Academia DiamondOne"**. Esta será uma aplicação (ex: em Streamlit) onde os usuários poderão fazer perguntas e receber respostas baseadas no conteúdo dos documentos que foram processados por esta automação.

---

# 📘 Manual Técnico: Pipeline de Ingestão Automatizada para RAG

**Projeto:** Rota da Seda (ID: `rota-da-seda-478119`)
**Status:** Em Produção
**Região de Processamento:** `europe-west4` (Holanda)
**Região de Dados:** `southamerica-east1` (Brasil)

---

## 1. Visão Geral da Arquitetura

Este sistema automatiza a ingestão de documentos PDF para uma base de conhecimento de Inteligência Artificial (RAG - Retrieval Augmented Generation). O fluxo é totalmente **Serverless** (sem servidores para gerenciar) e **Event-Driven** (baseado em eventos).

### O Fluxo de Dados:
1.  **Entrada (Humana):** Usuário coloca um PDF na pasta "RAG - Entrada" no Google Drive.
2.  **Ponte (Google Apps Script):** Um script roda a cada 5 minutos, pega o arquivo, envia para o Cloud Storage (Bucket Inbox) e move o original para "RAG - Processados" no Drive.
3.  **Gatilho (Eventarc):** Detecta a chegada do arquivo no Bucket Inbox (Brasil) e aciona o serviço na Europa.
4.  **Processamento (Cloud Run):**
    *   Recebe o evento.
    *   Move o arquivo do bucket `inbox` para `processed` (para evitar loops e duplicatas).
    *   Envia o arquivo para o **Vertex AI RAG Engine**.
5.  **Indexação (Vertex AI):** O documento é convertido em vetores e armazenado no Corpus `Tutor DiamondOne - Prod EU`.

---

## 2. Tecnologias e Ferramentas

*   **Google Apps Script:** Automação low-code integrada ao Workspace. Atua como "entregador" entre Drive e Cloud.
*   **Google Cloud Storage (GCS):** Armazenamento de objetos.
    *   `...-pdf-inbox`: Área de pouso (Gatilho ativo).
    *   `...-pdf-processed`: Arquivo final (Armazenamento frio).
*   **Google Cloud Run:** Computação containerizada. Roda nosso código Python.
    *   Configurado com `min-instances: 1` para evitar "Cold Start".
    *   Localizado em `europe-west4` para evitar bloqueios de capacidade dos EUA.
*   **Eventarc:** Sistema de mensageria que conecta o Storage ao Cloud Run com autenticação segura.
*   **Vertex AI RAG Engine:** Banco de dados vetorial gerenciado pelo Google que permite busca semântica.

---

## 3. Configuração e Deploy (Como foi feito)

### 3.1. O Código Python (`main.py`)
O coração do sistema. Principais características implementadas:
*   **Arquitetura Move-to-Process:** O arquivo é movido de bucket antes de ser processado. Isso garante que o Eventarc não dispare em loop infinito.
*   **Retry Logic:** Se o Vertex AI estiver ocupado, o código espera e tenta novamente (Backoff exponencial).
*   **Patch Defensivo:** Ignora erros de compatibilidade de biblioteca (`Unknown field: result`), garantindo que o sucesso no servidor seja refletido no cliente.

### 3.2. O Gatilho Cross-Region
Como os dados estão no Brasil e o processamento na Europa, usamos um gatilho especial:
*   **Filtro:** Bucket no Brasil (`southamerica-east1`).
*   **Destino:** Serviço na Europa (`europe-west4`).
*   **Autenticação:** Usa a Service Account `sa-rag-pipeline` para garantir segurança (sem acesso público).

---

## 4. Guia de Operação (Dia a Dia)

### Como inserir novos documentos:
1.  Acesse a pasta **"RAG - Entrada"** no Google Drive.
2.  Arraste seus arquivos PDF para lá.
3.  Aguarde até 5 minutos.
4.  Verifique a pasta **"RAG - Processados"**. Se o arquivo estiver lá, ele foi enviado para o Cloud.

### Como verificar se foi indexado:
1.  Acesse o **Vertex AI Console** (Link na seção 7).
2.  Certifique-se de selecionar a região **`europe-west4` (Netherlands)** no topo.
3.  Clique no Corpus `Tutor DiamondOne - Prod EU`.
4.  Verifique se o arquivo está na lista com status verde.

---

## 5. Comandos de Manutenção e Verificação (Cheat Sheet)

Execute estes comandos no terminal (Cloud Shell ou Local com SDK).

### 🛠️ Deploy e Atualização
Se você alterar o código `main.py`, use este comando para atualizar o robô na Europa:

```bash
gcloud run deploy processar-novo-pdf-rag ^
    --source . ^
    --region "europe-west4" ^
    --timeout=3600 ^
    --service-account "sa-rag-pipeline@rota-da-seda-478119.iam.gserviceaccount.com" ^
    --set-build-env-vars "GOOGLE_FUNCTION_TARGET=processar_evento_storage" ^
    --max-instances 4 ^
    --min-instances 1 ^
    --no-allow-unauthenticated
```

### 🔍 Verificação de Logs (Rastreio)
Para ver o que aconteceu com um arquivo específico (ex: `Contrato.pdf`):

```powershell
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.location="europe-west4" AND textPayload:"Contrato.pdf"' --limit=10 --format="value(textPayload)"
```

### 🧹 Limpeza de Buckets (Cuidado!)
Para apagar **tudo** e começar do zero:

```bash
gcloud storage rm gs://rota-da-seda-478119-pdf-inbox/** --quiet
gcloud storage rm gs://rota-da-seda-478119-pdf-processed/** --quiet
```

### 🧠 Teste de "Cérebro" (Python Script)
Para perguntar algo ao índice e ver se ele responde:
*Arquivo:* `teste_leitura.py`
*Comando:* `python teste_leitura.py`
*(Lembre-se de editar a variável `pergunta` dentro do arquivo para testar conteúdos específicos).*

---

## 6. Solução de Problemas (Troubleshooting)

### Erro: Apps Script "403 Insufficient Permission"
*   **Causa:** O script do Drive não tem permissão para escrever no Bucket.
*   **Solução 1 (Manifesto):** Verifique se o arquivo `appsscript.json` tem o escopo `https://www.googleapis.com/auth/devstorage.read_write`.
*   **Solução 2 (IAM):** Garanta que seu e-mail pessoal tenha permissão no bucket:
    ```bash
    gcloud storage buckets add-iam-policy-binding gs://rota-da-seda-478119-pdf-inbox --member="user:SEU_EMAIL" --role="roles/storage.objectAdmin"
    ```

### Erro: Cloud Run "The request was aborted / 429"
*   **Causa:** "Cold Start". O robô estava dormindo e demorou para acordar, ou muitas requisições chegaram ao mesmo tempo.
*   **Solução:** Já aplicada. Definimos `--min-instances 1` (mantém um robô acordado) e `--max-instances 4` (permite fila).

### Erro: Logs "The request was not authenticated"
*   **Causa:** O Gatilho (Eventarc) está tentando chamar o Cloud Run sem o crachá correto.
*   **Solução:** Recriar o gatilho forçando a Service Account:
    ```bash
    gcloud eventarc triggers create gatilho-rag-europe ... --service-account="sa-rag-pipeline@..."
    ```

### Erro: Python "Unknown field for ImportRagFilesResponse: result"
*   **Causa:** A biblioteca Python instalada é mais antiga que a API da Europa.
*   **Solução:** Já aplicada via código (Patch `try/except` no `main.py`). O erro é ignorado e o processo segue como sucesso.

---

## 7. Links de Acesso Rápido

| Ferramenta | Descrição | Link Direto |
| :--- | :--- | :--- |
| **Vertex AI (RAG)** | Onde ficam os dados indexados | [Acessar Corpus (Europa)](https://console.cloud.google.com/vertex-ai/rag-engines/corpora?project=rota-da-seda-478119&location=europe-west4) |
| **Cloud Run** | Onde roda o código Python | [Painel do Serviço](https://console.cloud.google.com/run/detail/europe-west4/processar-novo-pdf-rag/metrics?project=rota-da-seda-478119) |
| **Logs (Cloud Run)** | Histórico de erros e sucessos | [Logs Filtrados](https://console.cloud.google.com/logs/query;cursorTimestamp=2025-11-19T20:04:34.656387Z;duration=PT5M?project=rota-da-seda-478119) |
| **Apps Script** | Automação do Google Drive | [Editor de Código](https://script.google.com/home/projects/1EnTjMrtFKUUpLKrk4rJvdDeE95W9RLLKVSdPMrh9NQwjz1-EKONXOLd5/edit) |
| **Histórico Deploy** | Versões implantadas | [Cloud Build History](https://console.cloud.google.com/cloud-build/builds?project=rota-da-seda-478119) |

---

## 8. Higienização de Dados (Boas Práticas)

Para garantir que o robô não engasgue, siga estas regras ao nomear arquivos no Drive:

1.  **Evite Caracteres Especiais:** Evite `ç`, `ã`, emojis, ou símbolos como `&`, `%`, `$`.
    *   *Ruim:* `Relatório de Manutenção & Peças (Versão Final).pdf`
    *   *Bom:* `Relatorio_Manutencao_Pecas_V1.pdf`
2.  **Prefira PDF:** O sistema foi otimizado para PDFs.
3.  **Tamanho:** O Apps Script transfere bem arquivos até 50MB. Para arquivos gigantes (>100MB), o script precisaria de ajuste para "upload resumível" (chunked upload), mas para documentos de texto padrão, o atual sobra.
