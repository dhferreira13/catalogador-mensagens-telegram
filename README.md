# 📱 Catalogador de Mensagens do Telegram

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Interface](https://img.shields.io/badge/UI-CustomTkinter-blueviolet.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![API](https://img.shields.io/badge/Telegram-Telethon%20MTProto-blue.svg)](https://github.com/LonamiWebs/Telethon)
[![Vibe Coding](https://img.shields.io/badge/Metodologia-Vibe%20Coding-ff69b4.svg)]()
[![AI Assistant](https://img.shields.io/badge/AI%20Assistant-Google%20Antigravity%20v2.12.2-4285F4.svg)]()

> 💡 **Nota de Desenvolvimento:** Este software foi integralmente desenvolvido através de **Vibe Coding**, com assistência e co-autoria técnica da ferramenta de Inteligência Artificial **Google Antigravity (versão 2.12.2)**, integrando princípios de engenharia de software, conformidade ética com a LGPD e design de experiência do usuário.

Um aplicativo desktop moderno, robusto e amigável para **coleta, extração e catalogação ética de mensagens, reações e mídias** de grupos e canais do Telegram.

Projetado especialmente para **pesquisadores acadêmicos** (Comunicação, Ciência Política, Sociologia, Jornalismo, Humanidades Digitais) e **profissionais de dados**, o aplicativo entrega uma planilha Excel (`.xlsx`) estruturada e higienizada com conformidade ética estrita (**LGPD** e **Resolução CNS 510/2016**).

---

## ✨ Principais Recursos

* 🎨 **Interface Gráfica Moderna (Dark Theme):** Desenvolvida em CustomTkinter, intuitiva, responsiva e de fácil navegação.
* 🔒 **Anonimização Ética Estrita:** Protege a privacidade de usuários civis (substitui nomes reais e telefones por identificadores determinísticos como `User_A8F2`).
* ⏱️ **Filtros Temporais com Precisão de Minutos:** Defina a data de início e término com seletores independentes de horas e minutos (`DD/MM/AAAA HH:MM`).
* 📊 **Monitoramento em Tempo Real:** Cronômetro dinâmico em tempo real (`00:00:00`), contadores de mensagens varridas/salvas e console humanizado.
* 👑 **Identificação de Administradores e Bots:** Detecta se quem enviou ou encaminhou a mensagem possui privilégios de administrador ou se é um robô.
* 🖼️ **Download Padronizado de Mídias:** Salva fotos, vídeos e GIFs automaticamente com nomenclatura acadêmica `{ID}_{Data}_{Horário}.{ext}`.
* 📑 **Planilha Excel (.xlsx) Profissional:** 15 colunas objetivas estilizadas em Azul Navy com larguras automáticas, quebra de linha de texto, congelamento de painéis e filtros automáticos.
* 📝 **Sistema Contínuo de Auditoria (`Log.txt`):** Registro detalhado de sucessos, contadores parciais e diagnóstico de exceções em UTF-8.

---

## 🚀 Como Usar

### Opção 1: Baixar o Executável Pronto para Windows (Sem instalar Python!)
1. Acesse a aba [**Releases**](https://github.com/dhferreira13/catalogador-mensagens-telegram/releases) deste repositório.
2. Baixe o arquivo **`Catalogador de Mensagens do Telegram.exe`**.
3. Dê dois cliques para abrir e usar diretamente em qualquer computador com Windows!

> 💡 **Nota:** O `.exe` é completamente *standalone* (autossuficiente). Quando executado, ele cria automaticamente na mesma pasta onde está salvo os diretórios `output/` (para mídias e planilhas) e `Log.txt`.

---

### Opção 2: Executar em Modo de Desenvolvimento (Código Fonte)

Se você deseja rodar via Python ou contribuir com o projeto:

```bash
# 1. Clonar este repositório
git clone https://github.com/dhferreira13/catalogador-mensagens-telegram.git
cd catalogador-mensagens-telegram

# 2. Criar e ativar o ambiente virtual (Windows PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# No Linux / macOS:
# python3 -m venv venv && source venv/bin/activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Iniciar o aplicativo gráfico
python main.py
```

---

## 🔑 Como Obter suas Credenciais do Telegram (`API ID` e `API Hash`)

Para que o aplicativo possa se conectar à API oficial do Telegram com segurança:

1. Acesse o portal oficial de desenvolvedores do Telegram: [**https://my.telegram.org**](https://my.telegram.org).
2. Digite o número do seu celular (com código do país `+55` e DDD).
3. Insira o código de confirmação recebido no seu aplicativo do Telegram.
4. No menu principal, clique em **API development tools**.
5. Preencha os campos `App title` e `Short name` (ex: *MeuCatalogador*) e selecione a plataforma *Desktop*.
6. Clique em **Create application**.
7. Copie o **`api_id`** (número) e o **`api_hash`** (código alfanumérico) gerados e cole na tela inicial do aplicativo!

> 🔐 **Privacidade e Segurança:** Suas credenciais são salvas apenas localmente no seu próprio computador e são utilizadas exclusivamente para autenticar sua sessão com o Telegram.

---

## 📊 Estrutura da Planilha Exportada (.xlsx)

As planilhas são geradas na pasta `output/Planilhas de Catalogação/` contendo **15 colunas objetivas**, padronizadas para qualquer pesquisa científica:

| # | Coluna | Descrição |
|---|---|---|
| 1 | **ID da Mensagem** | Identificador numérico único da mensagem no Telegram |
| 2 | **Data e Horário (BRT)** | Data e hora convertidas para o fuso de Brasília (`DD/MM/AAAA HH:MM:SS`) |
| 3 | **Publicada por Bot?** | `Sim` / `Não` |
| 4 | **Publicada por Administrador?** | `Sim` / `Não` (identifica donos, moderadores e administradores anônimos) |
| 5 | **Fruto de Encaminhamento?** | `Sim` / `Não` |
| 6 | **Origem do Encaminhamento** | Nome do canal/grupo institucional de origem (ou `-`) |
| 7 | **Possui Mídia?** | `Sim` / `Não` |
| 8 | **Tipo de Mídia** | `Foto`, `Vídeo`, `GIF`, `Imagem` ou `Nenhuma` |
| 9 | **Arquivo de Mídia Salvo** | Nome exato do arquivo salvo na pasta `output/Mídias/` |
| 10 | **Visualizações** | Quantidade de views no momento da coleta |
| 11 | **Total de Reações** | Soma total de todas as reações registradas |
| 12 | **Tipos de Reações** | Emojis e quantidades (ex: `👍 (15), ❤️ (4), 🔥 (2)`) |
| 13 | **Texto da Mensagem** | Conteúdo textual na íntegra com quebras de linha preservadas |
| 14 | **Código do Autor (Anônimo)** | Identificador ético pseudonimizado (ex: `User_A8F2`) |
| 15 | **Links Extraídos** | Lista de URLs e links externos identificados na postagem |

---

## 📁 Organização de Pastas de Saída (`output/`)

```
output/
├── Mídias/
│   ├── 1042_2026-09-03_14-30-22.jpg
│   ├── 1043_2026-09-03_14-35-10.mp4
│   └── 1045_2026-09-03_15-00-00.gif
│
└── Planilhas de Catalogação/
    └── Catalogacao_NomeDoGrupo_20260905_120000.xlsx
```

---

## 🛠️ Como Gerar um Novo Executável (.exe)

O projeto inclui um script automatizado de compilação com PyInstaller:

```powershell
python build_exe.py
```

O executável standalone com ícone multi-resolução será gerado em `dist/Catalogador de Mensagens do Telegram.exe`.

---

## 🧪 Testes Automatizados (QA)

Para rodar a suíte de testes de integridade, anonimização e formatação:

```powershell
python -m unittest tests/test_tcc_catalog.py
```

---

## 🤖 Metodologia de Desenvolvimento: Vibe Coding com IA

Este projeto foi concebido e construído utilizando a metodologia de **Vibe Coding** em colaboração contínua com a ferramenta de Inteligência Artificial **Google Antigravity (versão 2.12.2)**.

O processo combinou a supervisão humana e requisitos do pesquisador com assistência de agentes de IA:
- **Engenharia Orientada a Skills:** Utilização de personas e habilidades especializadas em integração com APIs (`Telethon`/MTProto), arquitetura de banco de dados (SQLite WAL e mitigação de concorrência), design de interfaces gráficas modernas (`CustomTkinter`), testes contínuos de qualidade (`unittest`) e estilização de planilhas (`openpyxl`).
- **Rigor Ético e Científico:** Desenvolvimento direcionado à pesquisa acadêmica, com garantia de conformidade com a LGPD e resoluções éticas de pesquisa em mídias sociais (CNS 510/2016).
- **Ciclo Iterativo Ágil:** Todo o fluxo — desde a definição dos requisitos até o empacotamento do executável Windows com ícone multi-resolução e publicação — foi orquestrado com o **Google Antigravity v2.12.2**.

---

## 📄 Licença

Este projeto está licenciado sob a **Licença MIT** — consulte o arquivo [LICENSE](LICENSE) para obter mais detalhes.

Sinta-se à vontade para utilizar, modificar e citar este software em suas pesquisas e publicações acadêmicas!

