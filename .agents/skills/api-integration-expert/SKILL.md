---
name: api-integration-expert
description: >-
  Especialista em integração com APIs do Telegram (Telethon, MTProto, Pyrogram) e
  parsers de arquivos exportados pelo Telegram Desktop. Use para configurar coleta
  de dados, autenticação de sessão, contorno de rate limits e extração de metadados.
---

# API Integration Expert — Telegram

Esta skill orienta a extração e coleta sistemática de mensagens, metadados e mídias de canais e grupos públicos do Telegram para pesquisas acadêmicas e netnográficas.

## 1. Métodos de Coleta Suportados

### A. Coleta Direta via Telethon (MTProto API)
Recomendado para coleta contínua, monitoramento em tempo real ou recuperação automatizada com filtros específicos.
* **Biblioteca padrão:** `telethon`
* **Credenciais necessárias:** `API_ID` e `API_HASH` obtidos em https://my.telegram.org.
* **Arquivo de sessão:** Armazenado como `session_name.session` (deve ser mantido fora do controle de versão via `.gitignore`).
* **Tratamento de Rate Limit:** O Telegram impõe `FloodWaitError`. Sempre capture esta exceção e aplique espera adaptativa (`asyncio.sleep(error.seconds + 1)`).

### B. Ingestão via Exportação JSON (Telegram Desktop)
Método seguro, sem necessidade de credenciais de desenvolvedor ou risco de banimento de conta:
1. No Telegram Desktop: Abra o canal ou grupo público.
2. Menu de três pontos `(...)` -> **Exportar histórico do chat**.
3. Selecione o formato **JSON** e o período desejado (ex: 14 a 27 de setembro de 2026).
4. Salve o arquivo `result.json` na pasta `data/raw/`.
5. Execute o parser via `python main.py import-json --file data/raw/result.json`.

## 2. Metadados Essenciais para Coleta Netnográfica

Ao processar mensagens do Telegram, extraia sempre os seguintes campos:
* `id`: Identificador único da mensagem no grupo.
* `date`: Timestamp UTC convertido para horário local (BRT / UTC-3).
* `sender_id` / `sender_name`: Identificador do autor (anonimizado para publicação).
* `text`: Texto integral da mensagem (incluindo quebras de linha e formatação).
* `views`: Quantidade de visualizações (em canais ou posts com contadores).
* `forwards`: Número de vezes que a mensagem foi reencaminhada.
* `forward_from`: Canal ou usuário de origem da mensagem (se for encaminhamento).
* `reactions`: Dicionário/lista de emojis de reação e contadores.
* `reply_to_msg_id`: ID da mensagem pai em threads de conversa.
* `media_type`: Tipo de mídia anexada (`photo`, `video`, `audio`, `document`, `web_page`).
* `urls`: Links externos presentes na mensagem ou no preview web.
