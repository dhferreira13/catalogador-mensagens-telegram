---
name: qa-engineer
description: >-
  Engenheiro de qualidade de dados (QA) e testes. Focado em validação de integridade,
  testes de regressão, consistência das amostras e conferência de abas e métricas do TCC.
---

# QA Engineer — Garantia de Qualidade de Dados e Testes

Esta skill estabelece a suíte de testes e validação contínua para assegurar que nenhum dado chegue corrompido, duplicado ou fora do escopo metodológico na planilha final.

## 1. Checklist de Validação da Amostra Netnográfica

* **Teste de Janela Temporal:** Nenhuma mensagem com timestamp anterior a `2026-09-14 00:00:00` ou posterior a `2026-09-27 23:59:59` pode estar no conjunto principal.
* **Teste de Unicidade:** O campo `telegram_msg_id` deve ser estritamente único no banco de dados (zero duplicatas).
* **Teste de Anonimização:** Nenhum número de telefone ou nome completo de cidadão comum deve constar nas colunas públicas da planilha exportada.
* **Teste de Abas da Planilha:** A planilha gerada deve conter obrigatoriamente as abas `Semana 1 (14 a 20 set)` e `Semana 2 (21 a 27 set)` devidamente povoadas e com cabeçalhos consistentes.
* **Automação de Testes:** Suíte baseada em `pytest` em `tests/` para verificar sanitização de texto, cálculo de reações e filtros de datas.
