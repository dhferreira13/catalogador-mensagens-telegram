---
name: database-architect
description: >-
  Especialista em arquitetura de dados relacionais e modelagem conceitual/física
  (SQLite, PostgreSQL, DuckDB) para catalogação de mensagens, categorias de análise de conteúdo e métricas.
---

# Database Architect — Modelagem Relacional para Pesquisa de Mídia

Esta skill orienta o design, criação, otimização e manutenção do banco de dados relacional para armazenamento de mensagens e catalogação da pesquisa de TCC.

## 1. Esquema Relacional

### Tabela `messages`
* `id` (INTEGER, PK): ID interno sequencial.
* `telegram_msg_id` (INTEGER, UNIQUE): ID original da mensagem no chat/canal.
* `chat_id` (TEXT): Identificador do canal/grupo monitorado.
* `chat_title` (TEXT): Nome do canal/grupo no momento da coleta.
* `date_utc` (DATETIME): Data e hora em UTC.
* `date_brt` (DATETIME, INDEX): Data e hora no fuso horário de Brasília (UTC-3).
* `week_label` (TEXT, INDEX): Rótulo da semana (`Semana 1 (14 a 20 set)` ou `Semana 2 (21 a 27 set)`).
* `sender_id_anon` (TEXT): Identificador anonimizado do remetente.
* `sender_type` (TEXT): `user`, `channel`, `bot`, `admin`.
* `text_raw` (TEXT): Texto original completo da mensagem.
* `text_clean` (TEXT): Texto limpo (sem tags, URLs ou emojis para processamento NLP).
* `media_type` (TEXT): `none`, `photo`, `video`, `audio`, `document`, `web_page`.
* `has_media` (BOOLEAN): Indicador binário de presença de mídia.
* `is_forward` (BOOLEAN): Indicador binário se a mensagem é encaminhada.
* `forward_from_name` (TEXT): Nome do canal/autor de origem do encaminhamento.
* `views_count` (INTEGER, DEFAULT 0): Número de visualizações.
* `forwards_count` (INTEGER, DEFAULT 0): Número de encaminhamentos.
* `reactions_count` (INTEGER, DEFAULT 0): Contagem total de reações.
* `reactions_json` (TEXT): JSON serializado detalhando reações por emoji (ex: `{"👍": 15, "❤️": 3}`).
* `urls_list` (TEXT): JSON array ou texto com links extraídos da mensagem.
* `created_at` (DATETIME): Timestamp de inserção no banco de dados.

### Tabela `content_analysis` (Catalogação Qualitativa / Codebook)
* `id` (INTEGER, PK): Identificador do registro de análise.
* `message_id` (INTEGER, FK -> messages.id, UNIQUE): Vínculo 1:1 com a mensagem.
* `tema_predominante` (TEXT): Categoria temática conforme o livro de códigos.
* `enquadramento_noticioso` (TEXT): Enquadramento jornalístico / refratado.
* `valencia_politica` (TEXT): Polaridade ou tom em relação a atores políticos.
* `apelo_credibilidade` (TEXT): Tipo de dispositivo de validação (print de matéria, link oficial, etc.).
* `status_validacao` (TEXT): `Pendente`, `Catalogado`, `Duvida`.
* `observacoes_netnograficas` (TEXT): Notas de campo do pesquisador sobre o contexto da postagem.
* `updated_at` (DATETIME): Data da última atualização da análise.

## 2. Índices e Consultas Críticas
* Índice composto em `(week_label, date_brt)` para segmentação rápida dos relatórios semanais.
* Consultas agregadas para estatística descritiva (frequência de postagens por dia/hora, tipos de mídia mais compartilhados, ranking de canais de origem).
