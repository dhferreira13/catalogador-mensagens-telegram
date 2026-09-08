import sys
import io
import argparse
import asyncio
from pathlib import Path

# Proteção contra erros de NoneType em stdout/stderr no modo --noconsole do PyInstaller
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from src.utils.logger import setup_logging

def main():
    log_file = setup_logging()

    from src.db.session import init_db
    try:
        init_db()
    except Exception:
        pass

    # Se nenhum argumento for passado, ou se for chamada direta de GUI / .exe
    if len(sys.argv) == 1:
        from src.gui.app import run_gui
        run_gui()
        return

    parser = argparse.ArgumentParser(
        description="Ferramenta de Coleta e Catalogação de Mensagens do Telegram para TCC"
    )
    parser.add_argument("--gui", action="store_true", help="Inicia a interface gráfica do aplicativo")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Comando: init-db
    subparsers.add_parser("init-db", help="Inicializa o banco de dados SQLite local")

    # Comando: import-json
    parser_json = subparsers.add_parser("import-json", help="Importa arquivo result.json exportado pelo Telegram Desktop")
    parser_json.add_argument("--file", required=True, type=str, help="Caminho para o arquivo result.json")

    # Comando: collect-api
    parser_api = subparsers.add_parser("collect-api", help="Coleta mensagens diretamente via API do Telegram (Telethon)")
    parser_api.add_argument("--chat", type=str, default=None, help="Canal ou grupo alvo (ex: @canal_exemplo)")
    parser_api.add_argument("--limit", type=int, default=None, help="Limite de mensagens a consultar")

    # Comando: export-excel
    parser_export = subparsers.add_parser("export-excel", help="Exporta mensagens catalogadas para planilha Excel formatada")
    parser_export.add_argument("--out", type=str, default=None, help="Caminho do arquivo Excel de saída")

    # Comando: stream
    parser_stream = subparsers.add_parser("stream", help="Inicia coleta contínua em tempo real (Live Stream)")
    parser_stream.add_argument("--chat", type=str, default=None, help="Canal ou grupo alvo (ex: @canal_exemplo)")
    parser_stream.add_argument("--no-media", action="store_true", help="Desabilitar download de mídias")

    args = parser.parse_args()

    if args.gui or args.command is None:
        from src.gui.app import run_gui
        run_gui()

    elif args.command == "init-db":
        from src.db.session import init_db
        init_db()
        print("Banco de dados SQLite inicializado com sucesso!")

    elif args.command == "import-json":
        from src.collectors.json_importer import parse_json_export
        path = Path(args.file)
        if not path.exists():
            print(f"Erro: Arquivo não encontrado: {path}")
            sys.exit(1)
        count = parse_json_export(path)
        print(f"Importação concluída! {count} novas mensagens inseridas no banco de dados.")

    elif args.command == "collect-api":
        from src.collectors.telegram_client import run_telethon_collector
        count = asyncio.run(run_telethon_collector(target_chat=args.chat, limit=args.limit))
        print(f"Coleta via API concluída! {count} novas mensagens inseridas.")

    elif args.command == "export-excel":
        from src.exporter.excel_exporter import export_to_tcc_spreadsheet
        out_path = Path(args.out) if args.out else None
        export_to_tcc_spreadsheet(output_file=out_path)

    elif args.command == "stream":
        from coletor_tempo_real import main as run_stream
        sys.argv = [sys.argv[0]]
        if args.chat:
            sys.argv.extend(["--target", args.chat])
        if args.no_media:
            sys.argv.append("--no-media")
        run_stream()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
