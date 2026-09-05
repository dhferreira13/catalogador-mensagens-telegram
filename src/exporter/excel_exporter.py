import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.utils.paths import get_sheets_dir
from src.db.session import SessionLocal, init_db
from src.db.models import Message, ContentAnalysis

def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no Windows."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def export_to_tcc_spreadsheet(
    chat_id: Optional[str] = None,
    chat_title: Optional[str] = None,
    output_file: Optional[Path] = None,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None
) -> Path:
    """
    Exporta mensagens catalogadas para uma planilha Excel (.xlsx) profissionalmente estruturada
    na pasta 'output/Planilhas de Catalogação'.

    Regra Ética Crítica:
    Nenhum nome de usuário real, telefone ou @arroba pessoal é incluído na planilha.
    Apenas códigos anônimos criptografados (ex: Participante_A8F2) são utilizados.
    """
    sheets_dir = get_sheets_dir()
    try:
        init_db()
    except Exception:
        pass
    db = SessionLocal()

    if output_file is None:
        clean_title = sanitize_filename(chat_title or "Grupo_Telegram")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = sheets_dir / f"Catalogacao_{clean_title}_{timestamp}.xlsx"

    try:
        query = db.query(Message)
        if chat_id:
            query = query.filter(Message.chat_id == str(chat_id))
        if start_dt:
            query = query.filter(Message.date_brt >= start_dt)
        if end_dt:
            query = query.filter(Message.date_brt <= end_dt)

        messages = query.order_by(Message.date_brt.asc()).all()

        rows = []
        for m in messages:
            analysis = m.analysis
            
            # Formata reações para visualização amigável
            reactions_display = "-"
            if m.reactions_json:
                try:
                    r_dict = json.loads(m.reactions_json)
                    if r_dict:
                        reactions_display = ", ".join([f"{k} ({v})" for k, v in r_dict.items()])
                except Exception:
                    pass

            row = {
                "ID da Mensagem": m.telegram_msg_id,
                "Data e Horário (BRT)": m.date_brt.strftime("%d/%m/%Y %H:%M:%S"),
                "Publicada por Bot?": "Sim" if m.is_bot or m.sender_type == "bot" else "Não",
                "Publicada por Administrador?": "Sim" if getattr(m, 'is_admin', False) else "Não",
                "Fruto de Encaminhamento?": "Sim" if m.is_forward else "Não",
                "Origem do Encaminhamento": m.forward_from_name or "-",
                "Possui Mídia?": "Sim" if m.has_media else "Não",
                "Tipo de Mídia": m.media_type if m.has_media else "Nenhuma",
                "Arquivo de Mídia Salvo": m.media_filename or "-",
                "Visualizações": m.views_count,
                "Total de Reações": m.reactions_count,
                "Tipos de Reações": reactions_display,
                "Texto da Mensagem": m.text_raw or "",
                "Código do Autor (Anônimo)": m.sender_id_anon or "Participante_Anon",
                "Links Extraídos": m.urls_list or "-",
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        # Se não houver dados, gera DataFrame com colunas vazias
        if df.empty:
            columns = [
                "ID da Mensagem", "Data e Horário (BRT)", "Publicada por Bot?",
                "Publicada por Administrador?",
                "Fruto de Encaminhamento?", "Origem do Encaminhamento", "Possui Mídia?",
                "Tipo de Mídia", "Arquivo de Mídia Salvo", "Visualizações",
                "Total de Reações", "Tipos de Reações", "Texto da Mensagem",
                "Código do Autor (Anônimo)", "Links Extraídos"
            ]
            df = pd.DataFrame(columns=columns)

        # Salva o arquivo inicial com pandas
        df.to_excel(output_file, sheet_name="Mensagens Catalogadas", index=False)

        # Aplica estilização de alta qualidade com openpyxl (UX/UI Designer)
        wb = openpyxl.load_workbook(output_file)
        ws = wb.active

        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Azul Petróleo / Navy Elegante
        cell_font = Font(name="Segoe UI", size=10)
        
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        # Estilização do cabeçalho
        for col_idx, col in enumerate(ws.iter_cols(min_row=1, max_row=1), start=1):
            for cell in col:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        ws.row_dimensions[1].height = 28

        # Estilização das linhas de dados
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
            for cell in row:
                cell.font = cell_font
                cell.border = thin_border
                # Se for a coluna de texto da mensagem (coluna 13), habilita wrap_text
                if cell.column == 13:
                    cell.alignment = Alignment(vertical="top", horizontal="left", wrap_text=True)
                else:
                    cell.alignment = Alignment(vertical="center", horizontal="left" if cell.column in [6, 9, 15] else "center")

        # Ajuste inteligente de largura das colunas
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            header_val = str(col[0].value or "")
            
            # Colunas largas com texto
            if header_val == "Texto da Mensagem":
                ws.column_dimensions[col_letter].width = 50
            elif header_val in ["Arquivo de Mídia Salvo", "Origem do Encaminhamento"]:
                ws.column_dimensions[col_letter].width = 30
            elif header_val in ["Data e Horário (BRT)", "Tipos de Reações", "Links Extraídos", "Publicada por Administrador?"]:
                ws.column_dimensions[col_letter].width = 24
            elif header_val in ["Código do Autor (Anônimo)"]:
                ws.column_dimensions[col_letter].width = 22
            else:
                max_len = max(len(str(cell.value or '')) for cell in col)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

        # Congela a primeira linha (cabeçalho) e a primeira coluna (ID)
        ws.freeze_panes = "B2"

        # Habilita filtros automáticos
        ws.auto_filter.ref = ws.dimensions

        wb.save(output_file)
        return output_file
    finally:
        db.close()
