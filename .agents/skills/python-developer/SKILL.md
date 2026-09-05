---
name: python-developer
description: >-
  Especialista em desenvolvimento de software Python, automação, estruturação de pacotes,
  scripts de linha de comando (CLI) e boas práticas de código limpo e manutenível.
---

# Python Developer — Boas Práticas do Projeto

Esta skill estabelece os padrões de desenvolvimento, organização de código e ferramentas Python utilizadas no projeto de catalogação.

## 1. Padrões de Projeto
* **Python 3.12+ / 3.14:** Utilizar digitação estática (`typing`), *type hints*, e bibliotecas modernas.
* **ORM e Dados:** Utilizar `SQLAlchemy` para comunicação com o SQLite e `pandas` / `openpyxl` para manipulação de planilhas.
* **Assincronismo:** Utilizar `asyncio` para operações de rede com o Telegram via `telethon`.
* **Configuração Centralizada:** Todas as variáveis de ambiente e caminhos devem ser acessados via `src.config.settings`.
* **Separação de Responsabilidades:**
  * `src/collectors`: apenas comunicação externa e ingestão bruta.
  * `src/pipeline`: transformação de dados puros (sem dependência de banco de dados).
  * `src/db`: persistência e consultas SQL.
  * `src/exporter`: formatação e geração de relatórios e planilhas.
