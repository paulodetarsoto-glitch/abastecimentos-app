# =========================================================
#  Abastecimentos de Veículos - Controle com IA e Gmail
#  Autor: Paulo Varão (modificado por GitHub Copilot)
#  Versão: Painel - Requisições como fonte única / remoção de uploads e aba de cadastros
#  Atualizado: adiciona sidebar branca, logo, requisição teste, config real
# =========================================================
import os
import io
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ===========================
# Configurações iniciais / settings
# ===========================
DB_PATH = "abastecimentos.db"

# Pasta raiz do projeto (conforme sua observação)
PROJECT_DIR = r"C:\Users\paulo\Desktop\Projetos\Abastecimento de frota"
# Caminho default do logo dentro do projeto
DEFAULT_LOGO_PATH = os.path.join(PROJECT_DIR, "LogoOriginal.png")
SETTINGS_PATH = os.path.join(PROJECT_DIR, "settings.json") if os.path.isdir(PROJECT_DIR) else "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_settings(s):
    try:
        # garante que settings.json seja salvo na pasta do projeto
        target = SETTINGS_PATH
        with open(target, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

_settings = load_settings()
# usa o path do settings se definido, senão usa o default (absoluto)
LOGO_PATH = _settings.get("logo_path") if _settings.get("logo_path") else DEFAULT_LOGO_PATH
# se for relativo, torna absoluto em relação à pasta do projeto
if LOGO_PATH and not os.path.isabs(LOGO_PATH):
    LOGO_PATH = os.path.join(PROJECT_DIR, LOGO_PATH)

# (Streamlit exige que set_page_config seja o primeiro comando da página)
st.set_page_config(page_title="Requisições de Abastecimento - Frango Americano", layout="wide", page_icon="⛽")

# ===========================
# Estilos (tema ajustado)
# ===========================
CUSTOM_CSS = f"""
<style>
/* Fundo geral claro para contraste com identidade azul */
body {{ background: #f5f7fa !important; color: #050505; }}

/* Sidebar azul Frango Americano */
[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(180deg,#01263f,#003b63);
    color: #fff !important;
    padding-top: 12px;
}}

/* Força todos os textos dentro da sidebar para branco */
[data-testid="stSidebar"] * {{
    color: #fff !important;
}}

/* Centraliza a logo grande na sidebar */
.sidebar-logo-wrapper {{
    display:flex;
    align-items:center;
    justify-content:center;
    padding: 8px 0 12px 0;
}}

/* Logo pequena nos cards */
.app-card {{ background: linear-gradient(180deg, rgba(7,19,42,0.6), rgba(4,12,24,0.6)); border-radius: 8px; padding: 12px; margin-bottom:12px; }}
.title-bar {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }}
.top-actions > button {{ margin-left:8px; }}
.stButton>button {{ background: linear-gradient(90deg,#1F77B4,#00A3FF); color: white; border: none; }}
.table-actions button {{ margin-right:6px; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ===========================
# Banco de dados
# ===========================
def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Tabela de cadastros (mantida, mas sem aba de cadastro manual)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cadastros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Placa TEXT UNIQUE,
            Condutor TEXT,
            Unidade TEXT,
            Setor TEXT,
            Categoria TEXT,
            Marca TEXT,
            Modelo TEXT
        )
    """)

    # Tabela de abastecimentos / requisições (fonte única)
    c.execute("""
        CREATE TABLE IF NOT EXISTS abastecimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Placa TEXT,
            valor_total REAL,
            total_litros REAL,
            data TEXT,
            Referente TEXT,
            Odometro INTEGER,
            Posto TEXT,
            Combustivel TEXT,
            Condutor TEXT,
            Unidade TEXT,
            Setor TEXT,
            -- campos extras que podem não existir em bases antigas (serão garantidos abaixo)
            Status TEXT,
            Subsetor TEXT,
            Observacoes TEXT,
            TanqueCheio INTEGER,
            DataUso TEXT,
            KmUso INTEGER
        )
    """)
    conn.commit()

    # Garante colunas adicionais caso a tabela exista sem elas (compatibilidade)
    existing = [r[1] for r in c.execute("PRAGMA table_info(abastecimentos)").fetchall()]
    extras = {
        'Status': "TEXT",
        'Subsetor': "TEXT",
        'Observacoes': "TEXT",
        'TanqueCheio': "INTEGER",
        'DataUso': "TEXT",
        'KmUso': "INTEGER",
        'EmailPosto': "TEXT",
        'TipoPosto': "TEXT"
    }
    for col, typ in extras.items():
        if col not in existing:
            try:
                c.execute(f"ALTER TABLE abastecimentos ADD COLUMN {col} {typ}")
            except Exception:
                pass

    conn.commit()
    conn.close()

init_db()

# ===========================
# Geração de PDF (mantida, agora inclui cabeçalho com data)
# ===========================
def generate_request_pdf(payload: dict) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    except Exception as e:
        raise RuntimeError("reportlab não disponível: instale com `pip install reportlab`") from e

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    # Se existir logo local, tenta adicionar pequena imagem ao cabeçalho (não obrigatória)
    if payload.get("logo_path") and os.path.exists(payload["logo_path"]):
        try:
            img = Image(payload["logo_path"], width=100, height=40)
            story.append(img)
            story.append(Spacer(1, 8))
        except Exception:
            pass

    # Cabeçalho com nome da empresa e data automática (momento da geração)
    empresa = payload.get("empresa", "Frango Americano")
    data_envio = datetime.now().strftime("%d/%m/%Y %H:%M")
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Title'], alignment=0, fontSize=14)
    header = Paragraph(f"<b>{empresa}</b> — {data_envio}", header_style)
    story.append(header)
    story.append(Spacer(1, 12))

    title = Paragraph("Requisição de Abastecimento", styles['Heading2'])
    story.append(title)
    story.append(Spacer(1, 12))

    meta = [
        ["Data da Requisição:", payload.get("data", "")],
        ["Posto destino:", payload.get("posto", "")],
        ["E-mail do Posto:", payload.get("email_posto", "")],
        ["Tipo de Posto:", payload.get("tipo_posto", "")],
        ["Placa:", payload.get("placa", "")],
        ["Motorista:", payload.get("motorista", "")],
        ["Supervisor:", payload.get("supervisor", "")],
        ["Setor:", payload.get("setor", "")],
        ["Subsetor:", payload.get("subsetor", "")],
    ]

    # Campos complementares aparecem apenas se houver valor preenchido
    if payload.get("km_atual") not in (None, "", 0):
        meta.append(["Quilometragem atual (no momento):", str(payload.get("km_atual", ""))])
    if payload.get("litros") not in (None, ""):
        meta.append(["Quantidade abastecida (L):", str(payload.get("litros", ""))])
    if payload.get("valor_total") not in (None, "", 0):
        meta.append(["Valor total:", f"R$ {float(payload.get('valor_total')):,.2f}"])
    if payload.get("combustivel"):
        meta.append(["Combustível:", payload.get("combustivel", "")])

    tbl = Table(meta, colWidths=[160, 330])
    tbl.setStyle(TableStyle([
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica')
    ]))
    story.append(tbl)
    story.append(Spacer(1, 16))

    story.append(Paragraph("<b>Justificativa / Observações</b>", styles['Heading3']))
    justificativa = Paragraph((payload.get("justificativa") or "").replace("\n","<br/>"), styles['Normal'])
    story.append(justificativa)
    story.append(Spacer(1, 24))

    story.append(Paragraph(f"Solicitado por: {payload.get('solicitante','')}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Assinatura: ____________________________", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ===========================
# Páginas
# ===========================
def pagina_requisicoes():
    st.markdown("<div class='app-card title-bar'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 3])
    with col1:
        # pequena logo dentro do header do card (usa LOGO_PATH absoluto)
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=140)
    with col2:
        st.markdown("<h2 style='margin:0'>Requisição de abastecimento</h2>", unsafe_allow_html=True)
        st.markdown("<div style='color:#0f0f0f'>Área principal de requisições — pesquisa, ações rápidas e criação</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Topo: pesquisa e ações (REMOVIDO botão de export para Excel)
    topo_col1, topo_col2 = st.columns([3,1])
    with topo_col1:
        q = st.text_input("Pesquisar (ID, Placa, Condutor, Posto, Observações)", value="", key="pesquisa_reqs")
    with topo_col2:
        st.markdown("<div class='top-actions'>", unsafe_allow_html=True)
        st.button("⚙️", key="top_icon_filter")
        st.button("🔁", key="top_icon_refresh")
        st.markdown("</div>", unsafe_allow_html=True)

    # Ações de estado no topo direito
    ar1, ar2, ar3, ar4 = st.columns([1,1,1,1])
    with ar1:
        st.button("Cancelar", key="btn_cancelar", help="Marca seleção como Cancelado")
    with ar2:
        st.button("Em andamento", key="btn_andamento", help="Marca seleção como Em andamento")
    with ar3:
        if st.button("➕ Novo", key="btn_novo_requisicao"):
            st.session_state["_novo_requisicao_open"] = True
    with ar4:
        st.button("📤 Enviar selecionados", key="btn_enviar_selecionados")

    st.markdown("---")

    # Carrega dados (fonte única: tabela abastecimentos)
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM abastecimentos ORDER BY id DESC", conn)
    conn.close()

    # Normalizações de colunas possíveis (compatibilidade com esquemas antigos)
    if not df.empty:
        df_columns = [c for c in df.columns]
        for c in ["combustivel", "Combustivel"]:
            if c in df_columns:
                df['Combustivel'] = df[c].apply(normalize_combustivel)
                break

    # Exibição
    if df.empty:
        st.info("Nenhuma requisição registrada ainda.")
    else:
        df_display = df.copy()
        if 'data' in df_display.columns:
            df_display['data'] = pd.to_datetime(df_display['data'], errors='coerce').dt.strftime("%Y-%m-%d")
        else:
            df_display['data'] = ""
        df_display['Placa'] = df_display.get('Placa', "")
        df_display['Condutor'] = df_display.get('Condutor', df_display.get('Condutor', ""))
        df_display['Setor'] = df_display.get('Setor', "")
        df_display['Subsetor'] = df_display.get('Subsetor', "")
        if 'TanqueCheio' in df_display.columns:
            df_display['Quantidade'] = df_display.apply(lambda r: "Tanque cheio" if int(r.get('TanqueCheio') or 0) == 1 else str(r.get('total_litros') or ""), axis=1)
        else:
            df_display['Quantidade'] = df_display.get('total_litros', "")
        df_display['Status'] = df_display.get('Status', "")
        df_display['Posto'] = df_display.get('Posto', "")
        df_display['Observacoes'] = df_display.apply(lambda r: r.get('Observacoes') or r.get('Referente') or "", axis=1)
        df_display['DataUso'] = df_display.get('DataUso', "")
        df_display['KmUso'] = df_display.get('KmUso', "")

        if q and q.strip():
            ql = q.strip().lower()
            mask = df_display.apply(lambda row: ql in str(row.to_dict()).lower(), axis=1)
            df_display = df_display.loc[mask]

        st.markdown("#### Requisições")
        header_cols = st.columns([0.06, 0.12, 0.06, 0.1, 0.12, 0.12, 0.09, 0.09, 0.09, 0.09, 0.1, 0.12])
        headers = ["Sel", "Ações", "ID", "Data", "Placa", "Condutor", "Setor", "Subsetor", "Quantidade", "Status", "Posto", "Observações"]
        for hc, h in zip(header_cols, headers):
            hc.write(f"**{h}**")

        for idx, row in df_display.head(200).iterrows():
            cols = st.columns([0.06, 0.12, 0.06, 0.1, 0.12, 0.12, 0.09, 0.09, 0.09, 0.09, 0.1, 0.12])
            sel_key = f"sel_{row['id']}"
            with cols[0]:
                sel = st.checkbox("", key=sel_key)
            with cols[1]:
                if st.button("👁️", key=f"view_{row['id']}"):
                    st.session_state["_view_row"] = int(row['id'])
                if st.button("📎", key=f"anx_{row['id']}"):
                    st.info("Abrir anexos (não implementado).")
                if st.button("✏️", key=f"edit_{row['id']}"):
                    st.session_state["_edit_row"] = int(row['id'])
            cols[2].write(str(row.get('id', '')))
            cols[3].write(str(row.get('data', '')))
            cols[4].write(str(row.get('Placa', '')))
            cols[5].write(str(row.get('Condutor', '')))
            cols[6].write(str(row.get('Setor', '')))
            cols[7].write(str(row.get('Subsetor', '')))
            cols[8].write(str(row.get('Quantidade', '')))
            cols[9].write(str(row.get('Status', '')))
            cols[10].write(str(row.get('Posto', '')))
            cols[11].write(str(row.get('Observacoes', '')[:60]))

        # Visualizar no sidebar
        if st.session_state.get("_view_row"):
            rid = st.session_state.pop("_view_row")
            conn = get_connection()
            r = pd.read_sql(f"SELECT * FROM abastecimentos WHERE id = {int(rid)}", conn)
            conn.close()
            if not r.empty:
                r0 = r.iloc[0].to_dict()
                st.sidebar.markdown("### Visualizar Requisição")
                for k, v in r0.items():
                    st.sidebar.write(f"**{k}**: {v}")

    st.markdown("---")
    st.caption("Fonte: tabela 'abastecimentos' (todas as requisições).")

    # Novo formulário de requisição (quando acionado)
    if st.session_state.get("_novo_requisicao_open"):
        st.session_state["_novo_requisicao_open"] = False
        st.markdown("### Nova Requisição")
        with st.form("form_nova_req"):
            # Requisição teste no topo (impacta quais campos aparecem e o label do botão)
            requisicao_teste = st.checkbox("Requisição teste - gerar PDF sem salvar", value=False)

            colA, colB, colC = st.columns(3)
            with colA:
                placa = st.text_input("Placa")
                condutor = st.text_input("Condutor")
                setor = st.text_input("Setor")
                subsetor = st.text_input("Subsetor")
                # O campo de e-mail só aparece quando NÃO é requisição de teste
                if not requisicao_teste:
                    email_posto = st.text_input("E-mail do Posto")
                else:
                    email_posto = ""
            with colB:
                tipo_posto = st.selectbox("Tipo de Posto", ["Próprio", "Terceiro"])
                litros = st.number_input("Quantidade (L)", min_value=0.0, step=0.1, value=0.0)
                tanque_cheio = st.checkbox("Tanque cheio")
                combustivel = st.selectbox("Combustível", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "GNV", "Arla"])
                posto = st.text_input("Posto")
            with colC:
                data_req = st.date_input("Data da requisição", value=datetime.today())
                referente = st.text_area("Observações / Justificativa", height=80)

            # Label do botão muda conforme modo teste
            button_label = "Emitir teste de requisição" if requisicao_teste else "Enviar requisição agora"
            enviar = st.form_submit_button(button_label)
            if enviar:
                if not placa.strip():
                    st.error("Placa é obrigatória.")
                else:
                    combustivel_norm = normalize_combustivel(combustivel)
                    # Monta payload para PDF
                    payload = {
                        "empresa": "Frango Americano",
                        "logo_path": LOGO_PATH if LOGO_PATH else None,
                        "data": data_req.strftime("%Y-%m-%d"),
                        "posto": posto.strip(),
                        "email_posto": email_posto.strip(),
                        "tipo_posto": tipo_posto,
                        "placa": placa.strip(),
                        "motorista": condutor.strip(),
                        "supervisor": "",
                        "setor": setor.strip(),
                        "subsetor": subsetor.strip(),
                        "litros": liters if False else (litros if not tanque_cheio else None),
                        "valor_total": None,
                        "km_atual": None,
                        "combustivel": combustivel_norm,
                        "justificativa": referente.strip(),
                        "solicitante": condutor.strip()
                    }

                    # tenta gerar o PDF e captura erro claro se reportlab não estiver instalado
                    try:
                        pdf_bytes = generate_request_pdf(payload)
                    except RuntimeError as e:
                        st.error(f"Erro ao gerar PDF: {e}")
                        st.info("Instale o reportlab localmente e reinicie a aplicação: pip install reportlab")
                        pdf_bytes = None
                    except Exception as e:
                        st.error(f"Erro inesperado ao gerar PDF: {e}")
                        pdf_bytes = None

                    # Se a geração do PDF falhou, não prosseguir para download ou gravação
                    if pdf_bytes is None:
                        st.warning("PDF não gerado. Verifique a mensagem acima e tente novamente.")
                    else:
                        if requisicao_teste:
                            # Modo teste: NÃO salva no DB; apenas gera PDF para verificação
                            st.success("✅ PDF de teste gerado (não salvo).")
                            st.download_button(
                                label="Download PDF (teste)",
                                data=pdf_bytes,
                                file_name=f"requisicao_teste_{placa.strip()}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf",
                                mime="application/pdf"
                            )
                        else:
                            # Modo normal: salva na base marcando status como Enviada
                            conn = get_connection()
                            c = conn.cursor()
                            try:
                                c.execute("""
                                    INSERT INTO abastecimentos
                                    (Placa, valor_total, total_litros, data, Referente, Odometro, Posto, Combustivel, Condutor, Unidade, Setor, TanqueCheio, Subsetor, Observacoes, Status, EmailPosto, TipoPosto)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    placa.strip(), 0.0, litros if not tanque_cheio else None,
                                    data_req.strftime("%Y-%m-%d"), referente.strip(), None,
                                    posto.strip(), combustivel_norm, condutor.strip(), "", setor.strip(),
                                    1 if tanque_cheio else 0, subsetor.strip(), referente.strip(), "Enviada",
                                    email_posto.strip(), tipo_posto
                                ))
                                conn.commit()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                            finally:
                                conn.close()

                            st.success("✅ Requisição enviada e salva. Agora você pode complementar os dados do abastecimento.")
                            st.download_button(
                                label="Download PDF (enviada)",
                                data=pdf_bytes,
                                file_name=f"requisicao_{placa.strip()}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf",
                                mime="application/pdf"
                            )

    # ...edição dos campos complementares após envio...
    if st.session_state.get("_edit_row"):
        rid = st.session_state.pop("_edit_row")
        conn = get_connection()
        r = pd.read_sql(f"SELECT * FROM abastecimentos WHERE id = {int(rid)}", conn)
        conn.close()
        if not r.empty:
            r0 = r.iloc[0].to_dict()
            st.sidebar.markdown("### Completar Abastecimento")
            with st.form("form_edit_row"):
                km_uso = st.number_input("Quilometragem atual", min_value=0, step=1, value=int(r0.get('KmUso') or r0.get('Odometro') or 0))
                valor_total = st.number_input("Valor total (R$)", min_value=0.0, step=0.01, value=float(r0.get('valor_total') or 0.0))
                quantidade_abastecida = st.number_input("Quantidade abastecida (L)", min_value=0.0, step=0.01, value=float(r0.get('total_litros') or 0.0))
                salvar = st.form_submit_button("Salvar informações")
                if salvar:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE abastecimentos
                        SET KmUso = ?, valor_total = ?, total_litros = ?
                        WHERE id = ?
                    """, (km_uso, valor_total, quantidade_abastecida, int(rid)))
                    conn.commit()
                    conn.close()
                    st.success("Informações do abastecimento salvas.")

def pagina_dashboard():
    st.header("📊 Dashboard de Abastecimentos")
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM abastecimentos", conn)
    conn.close()
    if df.empty:
        st.info("Nenhum dado registrado ainda.")
        return
    df.columns = [c.strip() for c in df.columns]
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df = df.dropna(subset=['data'])
    if 'Combustivel' in df.columns:
        df['combustivel'] = df['Combustivel'].apply(normalize_combustivel)
    elif 'combustivel' in df.columns:
        df['combustivel'] = df['combustivel'].apply(normalize_combustivel)
    total_litros = float(df['total_litros'].sum()) if 'total_litros' in df.columns else 0.0
    total_valor = float(df['valor_total'].sum()) if 'valor_total' in df.columns else 0.0
    n_veiculos = int(df["Placa"].nunique()) if 'Placa' in df.columns else 0
    k1, k2, k3 = st.columns(3)
    with k1: st.metric("🚗 Veículos distintos", n_veiculos)
    with k2: st.metric("🛢 Total de litros", f"{total_litros:,.2f}")
    with k3: st.metric("💰 Valor total gasto", f"R$ {total_valor:,.2f}")
    st.markdown("Gráficos e análises completos mantidos na versão anterior (Dashboard estendido).")

def pagina_narrativas():
    st.header("🧠 Narrativas")
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    st.info("Narrativas automáticas sobre consumo, tendências e anomalias.")
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM abastecimentos ORDER BY data DESC LIMIT 200", conn)
    conn.close()
    if df.empty:
        st.info("Sem dados para gerar narrativas.")
        return
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    total_litros = df['total_litros'].sum() if 'total_litros' in df.columns else 0
    st.markdown(f"- Total de litros (últimos registros): **{total_litros:,.2f} L**")
    placas = df['Placa'].value_counts().head(5).to_dict()
    st.markdown("- Top 5 placas por número de requisições:")
    for p, c in placas.items():
        st.write(f"  - {p}: {c} requisições")

def pagina_configuracoes():
    st.header("⚙️ Configurações")
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    st.markdown("Preencha as configurações abaixo para SMTP, remetente e logo.")
    settings = load_settings()
    with st.form("form_settings"):
        smtp_server = st.text_input("SMTP Server", value=settings.get("smtp_server", "smtp.gmail.com"))
        smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=int(settings.get("smtp_port", 587)))
        smtp_user = st.text_input("SMTP User (e-mail remetente)", value=settings.get("smtp_user", ""))
        smtp_password = st.text_input("SMTP Password (opcional)", value=settings.get("smtp_password", ""), type="password")
        smtp_use_tls = st.checkbox("Usar TLS", value=settings.get("smtp_use_tls", True))
        salvar = st.form_submit_button("Salvar configurações")
        if salvar:
            new = {
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "smtp_user": smtp_user,
                "smtp_password": smtp_password,
                "smtp_use_tls": smtp_use_tls,
            }
            ok = save_settings(new)
# ===========================
# Menu principal
# ===========================
def main():
    # Sidebar: logo grande e título (garante fonte branca)
    if os.path.exists(LOGO_PATH):
        try:
            # método preferencial (gera menos problemas que file:// em muitas instalações)
            st.sidebar.image(LOGO_PATH, width=220)
        except Exception:
            # fallback: tentar injetar html se image falhar
            st.sidebar.markdown(f"<div class='sidebar-logo-wrapper'><img src='file://{os.path.abspath(LOGO_PATH)}' width='220' /></div>", unsafe_allow_html=True)
    st.sidebar.title("Frango Americano")
    menu = st.sidebar.radio(
        "Menu",
        ["Requisições", "Dashboard", "Narrativas", "Configurações"],
        index=0
    )

    if menu == "Requisições":
        pagina_requisicoes()
    elif menu == "Dashboard":
        pagina_dashboard()
    elif menu == "Narrativas":
        pagina_narrativas()
    elif menu == "Configurações":
        pagina_configuracoes()

if __name__ == "__main__":
    main()
