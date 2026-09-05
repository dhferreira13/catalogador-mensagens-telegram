---
name: data-engineer
description: >-
  Especialista em pipelines de engenharia de dados, limpeza, normalização,
  desduplicação e anonimização de mensagens e metadados para pesquisas em mídias sociais.
---

# Data Engineer — Pipeline de Dados Netnográficos

Esta skill define os processos de engenharia de dados para transformar mensagens brutas coletadas do Telegram em um conjunto de dados estruturado, higienizado e pronto para análise acadêmica.

## 1. Princípios do Pipeline de Dados

```
Dados Brutos (API / JSON) 
       │
       ▼
[ Ingestão & Validação de Schema ]
       │
       ▼
[ Filtro Temporal: 14 a 27 de Setembro de 2026 ]
       │
       ▼
[ Limpeza & Normalização de Texto ]
       │
       ▼
[ Extração de Features: Links, Mídias, Reações, Encaminhamentos ]
       │
       ▼
[ Anonimização & Proteção Ética ]
       │
       ▼
[ Carga no Banco SQLite & Exportação para Planilha ]
```

## 2. Regras de Limpeza e Tratamento

1. **Janela Temporal:**
   * Semana 1: `2026-09-14 00:00:00` a `2026-09-20 23:59:59` (BRT)
   * Semana 2: `2026-09-21 00:00:00` a `2026-09-27 23:59:59` (BRT)
   * Mensagens fora desta janela devem ser descartadas ou arquivadas separadamente.

2. **Anonimização (LGPD e Resolução CNS 510/2016):**
   * Nomes de usuários civis e números de telefone devem ser substituídos por identificadores alfanuméricos anônimos (ex: `User_A19`, `User_B04`).
   * Figuras públicas e canais institucionais podem ser mantidos conforme estabelecido no desenho metodológico do projeto.

3. **Extração de Entidades:**
   * Identificar e padronizar links encurtados ou redirecionamentos (`t.me/...`, `youtube.com/...`, portais de notícias).
   * Contabilizar engajamento total: `soma(reações) + visualizações + encaminhamentos`.
