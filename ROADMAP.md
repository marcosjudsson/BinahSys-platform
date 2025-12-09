# ROADMAP do BinahSys

## Visão Estratégica: Arquitetura de Dados IA OBJETIVA

Este roadmap baseia-se na estratégia de "Arquitetura de Dados IA OBJETIVA", focando em provas de conceito (PoC) para validar valor, ROI e manutenibilidade.

---

## Fase 1: Fundamentação e PoC (Atual)

### Pilotos Propostos (PoC)

| Piloto | Objetivo | Status |
| :--- | :--- | :--- |
| **1. Tutor da Academia (RAG Puro)** | Reduzir custo de SLA/Treinamento usando transcrições e manuais. | **EM ANDAMENTO / PRODUÇÃO** (Pipeline de Ingestão Ativo) |
| **2. Analista Causa-Raiz** | Análise de dados estruturados (SQL) para identificar bugs de performance. | **PLANEJADO** |
| **3. Assistente de Processo** | Orquestração híbrida entre Redmine, OTRS e Drive. | **FUTURO** |

### Status Detalhado - Piloto 1 (Tutor da Academia)
- [x] **Pipeline de Ingestão Automatizada:** Implementado e em produção (`rota-da-seda-478119`).
    - Integração Google Drive -> Cloud Storage -> Vertex AI RAG.
    - Região: `europe-west4` (Processamento/Dados), `southamerica-east1` (Gatilho).
- [ ] **Interface de Chat (Streamlit):** Em desenvolvimento.
    - Necessário integrar o frontend com o índice da Vertex AI criado pelo pipeline.

---

## Fase 2: Gestão de Conhecimento e Expansão

- [ ] **Refinamento do RAG:** Melhorar a precisão das respostas do Tutor.
- [ ] **Dashboard de Análise:** Métricas de uso do Tutor.
- [ ] **Integração com Google Drive:** Sincronização bidirecional (já iniciada com o pipeline de ingestão).

## Fase 3: Inteligência de Negócios (Piloto 2)

- [ ] **Conexão Segura com Banco de Dados:** VPN ou Gateway para acessar SQL Server/MySQL local.
- [ ] **Agente de Análise de Dados:** Implementar Text-to-SQL para responder perguntas sobre chamados e bugs.

## Fase 4: Orquestração e Agentes Autônomos (Piloto 3)

- [ ] **Integração de APIs:** Conectar com Redmine e OTRS.
- [ ] **Agente Orquestrador:** Coordenar ações entre diferentes sistemas.

---

## Histórico de Versões

- **v1.0 (11/11/2025):** Rascunho inicial da Arquitetura de Dados IA OBJETIVA.
