# =========================================================
#  Abastecimentos de Veículos - Controle
#  Autor: Paulo Varão
#  Atualizado: adiciona sidebar branca, logo, requisição teste, config real
# =========================================================
import os
import io
import json
import sqlite3
import pandas as pd
from datetime import datetime
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

# ===========================
# Configurações iniciais / settings
# ===========================
DB_PATH = "abastecimentos.db"
PROJECT_DIR = r"C:\Users\paulo\Desktop\Projetos\Abastecimento de frota"
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
        target = SETTINGS_PATH
        with open(target, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

_settings = load_settings()
LOGO_PATH = _settings.get("logo_path") if _settings.get("logo_path") else DEFAULT_LOGO_PATH
if LOGO_PATH and not os.path.isabs(LOGO_PATH):
    LOGO_PATH = os.path.join(PROJECT_DIR, LOGO_PATH)

st.set_page_config(page_title="Requisições de Abastecimento - Frango Americano", layout="wide", page_icon="⛽")

# ===========================
# Estilos (tema ajustado)
# ===========================
CUSTOM_CSS = f"""
<style>
body {{ background: #f5f7fa !important; color: #050505; }}
[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(180deg,#01263f,#003b63);
    color: #fff !important;
    padding-top: 12px;
}}
[data-testid="stSidebar"] * {{
    color: #fff !important;
}}
.sidebar-logo-wrapper {{
    display:flex;
    align-items:center;
    justify-content:center;
    padding: 8px 0 12px 0;
}}
.app-card {{ background: linear-gradient(180deg, rgba(7,19,42,0.6), rgba(4,12,24,0.6)); border-radius: 8px; padding: 12px; margin-bottom:12px; }}
.title-bar {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }}
.top-actions > button {{ margin-left:8px; }}
.stButton>button {{ background: linear-gradient(90deg,#1F77B4,#00A3FF); color: white; border: none; }}
.table-actions button {{ margin-right:6px; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ===========================
# Funções utilitárias
# ===========================
def normalize_combustivel(c: str) -> str:
    if not isinstance(c, str):
        return ""
    if "etanol" in c.lower():
        return "Etanol"
    if "gasolina" in c.lower():
        return "Gasolina"
    if "diesel s10" in c.lower():
        return "Diesel S10"
    if "diesel s500" in c.lower():
        return "Diesel S500"
    if "arla" in c.lower():
        return "Arla"
    return c.strip()

# ===========================
# Banco de dados
# ===========================
def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
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
            Status TEXT,
            Subsetor TEXT,
            Observacoes TEXT,
            TanqueCheio INTEGER,
            DataUso TEXT,
            KmUso INTEGER,
            EmailPosto TEXT,
            TipoPosto TEXT
        )
    """)
    conn.commit()
    existing = [r[1] for r in c.execute("PRAGMA table_info(abastecimentos)").fetchall()]
    extras = {
        'Status': "TEXT", 'Subsetor': "TEXT", 'Observacoes': "TEXT",
        'TanqueCheio': "INTEGER", 'DataUso': "TEXT", 'KmUso': "INTEGER",
        'EmailPosto': "TEXT", 'TipoPosto': "TEXT"
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
# Geração de PDF
# ===========================
def generate_request_pdf(payload: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    if payload.get("logo_path") and os.path.exists(payload["logo_path"]):
        try:
            img = Image(payload["logo_path"], width=100, height=40)
            story.append(img)
            story.append(Spacer(1, 8))
        except Exception:
            pass

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
        ["Referente do veículo:", payload.get("referente_veiculo", "")],
        ["Placa:", payload.get("placa", "")],
        ["Motorista:", payload.get("motorista", "")],
        ["Supervisor:", payload.get("supervisor", "")],
        ["Setor:", payload.get("setor", "")],
        ["Subsetor:", payload.get("subsetor", "")],
    ]

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
    story.append(Spacer(1, 32))

    story.append(Paragraph(f"Requisição solicitada por: {payload.get('solicitante','')}", styles['Normal']))
    story.append(Spacer(1, 19))
    story.append(Paragraph("Assinatura do Supervisor: ____________________________", styles['Normal']))
    story.append(Spacer(1, 19))
    story.append(Paragraph("Quilometragem atual: _________________________"))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ===========================
# Páginas
# ===========================
def _show_new_request_form():
    """Função que exibe e gerencia o formulário de nova requisição."""
    
    st.markdown("### Nova Requisição")
    
    # Limpa dados da sessão para evitar botões de download de requisições anteriores
    if "pdf_data" in st.session_state:
        del st.session_state["pdf_data"]
    if "pdf_filename" in st.session_state:
        del st.session_state["pdf_filename"]

    with st.form("form_nova_req"):
        requisicao_teste = st.checkbox("Requisição teste - gerar PDF sem salvar", value=False)
        colA, colB, colC = st.columns(3)
        with colA:
            placa = st.text_input("Placa")
            condutor = st.text_input("Condutor")
            setor = st.text_input("Setor")
            subsetor = st.text_input("Subsetor")
            if not requisicao_teste:
                email_posto = st.text_input("E-mail do Posto")
            else:
                email_posto = ""
        with colB:
            tipo_posto = st.selectbox("Tipo de Posto", ["Próprio", "Terceiro"])
            litros = st.number_input("Quantidade (L)", min_value=0.0, step=0.1, value=0.0)
            tanque_cheio = st.checkbox("Tanque cheio")
            combustivel = st.selectbox("Combustível", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "Arla"])
            posto = st.text_input("Posto")
        with colC:
            data_req = st.date_input("Data da requisição", value=datetime.today())
            referente = st.text_area("Observações / Justificativa", height=80)

        enviar = st.form_submit_button("Emitir requisição")
        
        if enviar:
            if not placa.strip():
                st.error("Placa é obrigatória.")
            else:
                combustivel_norm = normalize_combustivel(combustivel)
                payload = {
                    "empresa": "Frango Americano", "logo_path": LOGO_PATH if LOGO_PATH else None,
                    "data": data_req.strftime("%Y-%m-%d"), "posto": posto.strip(),
                    "email_posto": email_posto.strip(), "tipo_posto": tipo_posto,
                    "placa": placa.strip(), "motorista": condutor.strip(), "supervisor": "",
                    "setor": setor.strip(), "subsetor": subsetor.strip(),
                    "litros": litros if not tanque_cheio else None, "valor_total": None, "km_atual": None,
                    "combustivel": combustivel_norm, "justificativa": referente.strip(),
                    "solicitante": condutor.strip()
                }
                
                try:
                    pdf_bytes = generate_request_pdf(payload)
                    # Armazena os dados do PDF e o nome do arquivo na sessão
                    st.session_state["pdf_data"] = pdf_bytes
                    st.session_state["pdf_filename"] = f"requisicao_{placa.strip()}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                    st.success("✅ Requisição gerada com sucesso.")
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")
                    st.info("Verifique a instalação do reportlab: pip install reportlab")
                    st.session_state["pdf_data"] = None

                if not requisicao_teste and st.session_state.get("pdf_data"):
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
                            posto.strip(), normalize_combustivel(combustivel), condutor.strip(), "", setor.strip(),
                            1 if tanque_cheio else 0, subsetor.strip(), referente.strip(), "Enviada",
                            email_posto.strip(), tipo_posto
                        ))
                        conn.commit()
                        st.success("✅ Requisição salva no banco de dados.")
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco de dados: {e}")
                    finally:
                        conn.close()


def pagina_requisicoes():
    st.markdown("<div class='app-card title-bar'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 3])
    with col1:
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=140)
    with col2:
        st.markdown("<h2 style='margin:0'>Requisição de abastecimento</h2>", unsafe_allow_html=True)
        st.markdown("<div style='color:#0f0f0f'>Área principal de requisições — pesquisa, ações rápidas e criação</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "table"

    topo_col1, topo_col2 = st.columns([3,1])
    with topo_col1:
        q = st.text_input("Pesquisar (ID, Placa, Condutor, Posto, Observações)", value="", key="pesquisa_reqs")
    with topo_col2:
        st.markdown("<div class='top-actions'>", unsafe_allow_html=True)
        st.button("⚙️", key="top_icon_filter")
        st.button("🔁", key="top_icon_refresh", on_click=lambda: st.session_state.update(view_mode="table"))
        st.markdown("</div>", unsafe_allow_html=True)

    ar1, ar2, ar3, ar4 = st.columns([1,1,1,1])
    with ar1:
        st.button("Cancelar", key="btn_cancelar", help="Marca seleção como Cancelado")
    with ar2:
        st.button("Em andamento", key="btn_andamento", help="Marca seleção como Em andamento")
    with ar3:
        if st.button("➕ Novo", key="btn_novo_requisicao", on_click=lambda: st.session_state.update(view_mode="form")):
            pass
    with ar4:
        st.button("📤 Enviar selecionados", key="btn_enviar_selecionados")

    st.markdown("---")

    if st.session_state.view_mode == "form":
        _show_new_request_form()
        
        # EXIBE O BOTÃO DE DOWNLOAD AQUI, FORA DO FORMULÁRIO
        if "pdf_data" in st.session_state and st.session_state["pdf_data"]:
            st.markdown("---")
            st.download_button(
                label="Download PDF da requisição",
                data=st.session_state["pdf_data"],
                file_name=st.session_state["pdf_filename"],
                mime="application/pdf"
            )

    elif st.session_state.view_mode == "table":
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM abastecimentos ORDER BY id DESC", conn)
        conn.close()
        
        if not df.empty:
            df_columns = [c for c in df.columns]
            for c in ["combustivel", "Combustivel"]:
                if c in df_columns:
                    df['Combustivel'] = df[c].apply(normalize_combustivel)
                    break
        
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
                        st.session_state.view_mode = "view"
                        st.session_state._view_row = int(row['id'])
                    if st.button("📎", key=f"anx_{row['id']}"):
                        st.info("Abrir anexos (não implementado).")
                    if st.button("✏️", key=f"edit_{row['id']}"):
                        st.session_state.view_mode = "edit"
                        st.session_state._edit_row = int(row['id'])
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

    if st.session_state.get("view_mode") == "view" and "_view_row" in st.session_state:
        rid = st.session_state.pop("_view_row")
        conn = get_connection()
        r = pd.read_sql(f"SELECT * FROM abastecimentos WHERE id = {int(rid)}", conn)
        conn.close()
        if not r.empty:
            r0 = r.iloc[0].to_dict()
            st.sidebar.markdown("### Visualizar Requisição")
            for k, v in r0.items():
                st.sidebar.write(f"**{k}**: {v}")
            st.sidebar.button("Voltar", on_click=lambda: st.session_state.update(view_mode="table"))

    if st.session_state.get("view_mode") == "edit" and "_edit_row" in st.session_state:
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
            st.sidebar.button("Voltar", on_click=lambda: st.session_state.update(view_mode="table"))

    st.markdown("---")
    st.caption("Fonte: tabela 'abastecimentos' (todas as requisições).")

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
        st.write(f"  - {p}: {c} requisições")

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
    if os.path.exists(LOGO_PATH):
        try:
            st.sidebar.image(LOGO_PATH, width=220)
        except Exception:
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
