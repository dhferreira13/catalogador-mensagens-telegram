---
name: debugging-expert
description: >-
  Especialista em diagnóstico rápido de falhas, análise de erros de conexão Telegram,
  codificação de texto (UTF-8 / Emojis), bloqueios de banco SQLite e resolução ágil de bugs.
---

# Debugging Expert — Diagnóstico Ágil e Resolução de Erros

Esta skill atua na identificação rápida da causa-raiz de falhas durante a coleta, processamento e exportação de dados, minimizando o tempo de inatividade e o consumo de contexto.

## 1. Guia Rápido de Falhas Conhecidas e Resoluções

1. **Encoding / Caracteres Especiais / Emojis:**
   * **Sintoma:** `UnicodeEncodeError` ou caracteres quebrados no terminal do Windows.
   * **Correção:** Sempre abrir arquivos com `encoding="utf-8"` explícito e sanitizar strings antes da escrita.

2. **Telegram API Rate Limit (`FloodWaitError`):**
   * **Sintoma:** O Telegram bloqueia novas requisições por X segundos.
   * **Correção:** Capturar `telethon.errors.FloodWaitError`, recuperar `error.seconds` e aplicar espera assíncrona automática (`await asyncio.sleep(e.seconds + 2)`).

3. **Concorrência e Locks no SQLite (`database is locked`):**
   * **Sintoma:** SQLite travado quando múltiplos processos tentam escrever simultaneamente.
   * **Correção:** Utilizar `timeout=30.0` no driver do SQLite e manter transações curtas com commit imediato.

4. **Caminhos no Windows com Espaços e Aspas:**
   * **Sintoma:** PowerShell entra em modo `>>` ou falha ao localizar executáveis.
   * **Correção:** Usar `pathlib.Path` em Python e sempre envelopar caminhos entre aspas duplas `"..."` no shell.
