# Registro de Decisões de Arquitetura (ADR)

Este documento registra as decisões de arquitetura importantes tomadas durante o desenvolvimento do projeto.

---

## ADR-001: Criação de Documentação Estruturada

*   **Data:** 30 de outubro de 2025
*   **Status:** Decidido

### Contexto

Durante a fase inicial de desenvolvimento e implantação, percebemos a necessidade de uma estrutura de documentação mais robusta para garantir a consistência, o alinhamento e a capacidade de evolução do projeto a longo prazo. A natureza volátil da memória da IA entre as sessões de trabalho exige um "cérebro persistente" para o projeto.

### Decisão

Decidimos criar e manter os seguintes documentos como a "única fonte da verdade" do projeto:
*   **`ARCHITECTURE.md`:** Para documentar a arquitetura do sistema de forma visual e descritiva.
*   **`DECISION_LOG.md` (Incorporado neste ADR):** Para registrar o "porquê" por trás das nossas decisões técnicas.
*   **`CHANGELOG.md`:** Para manter um diário de bordo detalhado das atividades.
*   **`ROADMAP.md`:** Para o planejamento estratégico de alto nível.

Também foi decidido adotar um fluxo de trabalho baseado em sessões (início e fim) para garantir que esses documentos sejam sempre consultados e atualizados, e integrar o Obsidian como a ferramenta principal para visualização e gerenciamento dessa base de conhecimento.

### Consequências

*   **Positivas:**
    *   Maior clareza e alinhamento sobre o estado e a direção do projeto.
    *   Cria uma base de conhecimento persistente que acelera a retomada do trabalho entre sessões.
    *   Facilita a manutenção e a evolução do sistema a longo prazo.
    *   Atende à preferência do usuário por uma abordagem visual e estruturada.
*   **Negativas:**
    *   Exige uma disciplina maior para manter os documentos atualizados ao final de cada sessão de trabalho.

---

## ADR-002: Expansão da Visão do Projeto para Inteligência de Negócios Proativa

*   **Data:** 30 de outubro de 2025
*   **Status:** Decidido

### Contexto

Após a implementação inicial e a definição da arquitetura base, identificamos o potencial do BinahSys de ir além de um sistema de gerenciamento de conhecimento e Q&A. A conversa revelou uma necessidade estratégica de não apenas acessar informação, mas de usar a IA para analisar dados de negócio e gerar insights que possam levar a otimizações de processo, redução de custos e aumento de competitividade.

### Decisão

Decidimos expandir oficialmente a visão de longo prazo do BinahSys. O projeto agora tem como missão evoluir para um **sistema de inteligência de negócios proativo**. Isso inclui:
1.  Integrar a plataforma com fontes de dados quantitativos (ERPs, bancos de dados, planilhas).
2.  Desenvolver "Personas Analíticas" capazes de interpretar esses dados e gerar hipóteses.
3.  Implementar funcionalidades de relatórios autônomos e alertas inteligentes.

Esta decisão foi registrada na **Fase 5** do `ROADMAP.md` e incorporada à "Missão Principal" do projeto no `PROJECT_OVERVIEW.md` e na `APRESENTACAO_PROJETO.md`.

### Consequências

*   **Positivas:**
    *   Aumenta drasticamente o valor estratégico e o potencial de ROI (Retorno sobre o Investimento) do projeto.
    *   Alinha o desenvolvimento tecnológico com os objetivos de negócio da empresa (lucratividade, competitividade).
    *   Cria uma visão mais ambiciosa e inspiradora para o futuro da IA na empresa.
*   **Negativas:**
    *   Aumenta a complexidade do projeto a longo prazo.


---

## ADR-003: Adoção de Metodologia de Gestão Multi-Projeto e Segundo Cérebro

*   **Data:** 3 de novembro de 2025
*   **Status:** Decidido

### Contexto

Com o sucesso da gestão do projeto inicial, surgiu a necessidade de expandir a metodologia para gerenciar múltiplos projetos e, de forma mais ampla, construir um sistema de gestão de conhecimento pessoal e profissional (um "Segundo Cérebro"). A limitação da IA, que opera apenas dentro do diretório em que é iniciada, exigiu a definição de um fluxo de trabalho robusto e explícito.

### Decisão

Decidimos adotar uma estrutura e metodologia abrangentes, baseadas nos seguintes pilares:
1.  **Estrutura de "Hub de Projetos":** Todos os projetos serão organizados em subdiretórios dentro de uma pasta principal `Projetos/`.
2.  **Regra do "Workspace Raiz":** A IA deverá ser sempre iniciada no diretório raiz (`C:\MeusProjetos\GEMINI\`), que funcionará como o "Vault" principal do Obsidian. Isso garante que a IA tenha visibilidade de todos os projetos e documentos.
3.  **Modelo Híbrido (P.A.R.A. + Zettelkasten):** Adotaremos o método P.A.R.A. (Projetos, Áreas, Recursos, Arquivo) para a organização estrutural e o método Zettelkasten para a criação de uma rede de notas atômicas e conectadas, fomentando a geração de insights.
4.  **Especialista em Obsidian:** A IA assume o papel de especialista em Obsidian, responsável por implementar e manter as práticas avançadas (Dataview, Templater, etc.) para o usuário.

### Consequências

*   **Positivas:**
    *   Cria um sistema escalável e organizado para gerenciar múltiplos projetos.
    *   Resolve a limitação de contexto da IA, estabelecendo um fluxo de trabalho claro.
    *   Estabelece as bases para um verdadeiro "Segundo Cérebro", indo além da simples gestão de projetos.
    *   Maximiza o potencial da colaboração Humano-IA, com papéis bem definidos.
*   **Negativas:**
    *   Exige que o usuário siga rigorosamente a regra de iniciar a IA no diretório raiz para que o sistema funcione como esperado.

---

## ADR-004: Princípio da Validação de Riscos de Workspace

*   **Data:** 3 de novembro de 2025
*   **Status:** Adotado

### Contexto

A tentativa de unificar o workspace do projeto `diamondone-v4-app` com o cofre do Obsidian causou um conflito crítico, travando a aplicação. A causa raiz foi a interação imprevista entre a estrutura de arquivos do projeto (a pasta `venv`) e o mecanismo de indexação do Obsidian. Isso demonstra que mudanças estruturais no nosso ambiente de trabalho (o "workspace") carregam riscos que precisam ser explicitamente analisados.

### Decisão (Meu Novo Processo)

Antes de executar qualquer operação que reestruture significativamente nossos arquivos ou pastas (como mover projetos, alterar a arquitetura de pastas, etc.), sou agora obrigado a realizar e comunicar uma **"Validação de Riscos de Workspace"**. Esta validação responderá a 4 perguntas:
1.  **O Objetivo:** Qual o benefício esperado com a mudança?
2.  **O Impacto:** Quais ferramentas e processos podem ser afetados (Obsidian, Git, o próprio aplicativo, etc.)?
3.  **O Risco Principal:** Qual é o pior cenário provável (ex: travamento de uma ferramenta, quebra de links, corrupção de dados)?
4.  **A Mitigação:** Como vamos prevenir o risco? E qual é o plano para reverter a mudança se o risco se concretizar?

### Consequências

*   **Positivas:**
    *   Força uma abordagem de "medir duas vezes, cortar uma", reduzindo a probabilidade de erros disruptivos.
    *   Aumenta a transparência e a confiança do usuário no meu processo de tomada de decisão.
    *   Cria um registro de análise de risco que pode ser consultado no futuro.
*   **Negativas:**
    *   Adiciona um pequeno passo de planejamento antes de ações estruturais, um custo que é justificado pela estabilidade ganha.
