# =========================================================
#  Abastecimentos de Veículos - Controle com IA e Gmail
#  Autor: Paulo Varão (modificado por GitHub Copilot)
#  Versão: Painel - Requisições como fonte única / remoção de uploads e aba de cadastros
# =========================================================
import os
import io
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ===========================
# Configurações iniciais
# ===========================
DB_PATH = "abastecimentos.db"
LOGO_PATH = "LogoOriginal.png"  # Caminho do logo

# (Streamlit exige que set_page_config seja o primeiro comando da página)
st.set_page_config(page_title="Requisições de Abastecimento - Frango Americano", layout="wide", page_icon="⛽")

# ===========================
# Estilos (tema ajustado)
# ===========================
CUSTOM_CSS = """
<style>
/* Fundo geral escuro para contraste com identidade azul */
body { background: #07132a !important; color: #E6F0FF; }

/* Sidebar azul Frango Americano */
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg,#01263f,#003b63);
    color: #fff;
}

/* Logo/topo e cartões */
.app-card { background: linear-gradient(180deg, rgba(7,19,42,0.6), rgba(4,12,24,0.6)); border-radius: 8px; padding: 12px; margin-bottom:12px; }
.title-bar { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.top-actions > button { margin-left:8px; }
.stButton>button { background: linear-gradient(90deg,#1F77B4,#00A3FF); color: white; border: none; }
.table-actions button { margin-right:6px; }
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
        'KmUso': "INTEGER"
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
# Utilitários
# ===========================
def normalize_combustivel(val):
    try:
        if val is None:
            return val
        s = str(val).strip()
        s = ' '.join([w.capitalize() for w in s.split()])
        return s
    except Exception:
        return val

def to_excel_bytes(sheets: dict, engine_order=('xlsxwriter', 'openpyxl')):
    for engine in engine_order:
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine=engine) as writer:
                for name, df in sheets.items():
                    sheet_name = (name[:31]) if name else "Sheet1"
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
            buffer.seek(0)
            return buffer.getvalue(), engine
        except Exception:
            continue
    return None, None

def send_email_smtp(to_address, subject, body=None, html_body=None, attachment_bytes=None, attachment_name='relatorio.pdf', smtp_config=None):
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg['From'] = smtp_config.get('user') if smtp_config else ''
        msg['To'] = to_address
        msg['Subject'] = subject

        if html_body:
            msg.set_content(body if body else 'Este e-mail contém conteúdo em HTML.')
            msg.add_alternative(html_body, subtype='html')
        else:
            msg.set_content(body if body else '')

        if attachment_bytes is not None:
            subtype = 'octet-stream'
            maintype = 'application'
            if attachment_name.lower().endswith('.xlsx'):
                maintype, subtype = 'application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif attachment_name.lower().endswith('.pdf'):
                maintype, subtype = 'application', 'pdf'
            msg.add_attachment(attachment_bytes, maintype=maintype, subtype=subtype, filename=attachment_name)

        server = smtp_config.get('server', 'smtp.gmail.com') if smtp_config else 'smtp.gmail.com'
        port = smtp_config.get('port', 587) if smtp_config else 587
        user = smtp_config.get('user') if smtp_config else None
        password = smtp_config.get('password') if smtp_config else None
        use_tls = smtp_config.get('use_tls', True) if smtp_config else True

        s = smtplib.SMTP(server, port, timeout=30)
        if use_tls:
            s.starttls()
        if user and password:
            s.login(user, password)
        s.send_message(msg)
        s.quit()
        return True, ''
    except Exception as e:
        return False, str(e)

# ===========================
# Geração de PDF (mantida)
# ===========================
def generate_request_pdf(payload: dict) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception as e:
        raise RuntimeError("reportlab não disponível: instale com `pip install reportlab`") from e

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("Requisição de Abastecimento - Frango Americano", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    meta = [
        ["Data da Requisição:", payload.get("data", "")],
        ["Posto destino:", payload.get("posto", "")],
        ["Placa:", payload.get("placa", "")],
        ["Motorista:", payload.get("motorista", "")],
        ["Supervisor:", payload.get("supervisor", "")],
        ["Setor:", payload.get("setor", "")],
        ["Subsetor:", payload.get("subsetor", "")],
        ["Quilometragem atual (no momento):", str(payload.get("km_atual", ""))],
        ["Quantidade (L) / Tanque Cheio:", str(payload.get("litros", ""))],
        ["Combustível:", payload.get("combustivel", "")]
    ]
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
    justificativa = Paragraph(payload.get("justificativa", "").replace("\n","<br/>"), styles['Normal'])
    story.append(justificativa)
    story.append(Spacer(1, 24))

    story.append(Paragraph(f"Solicitado por: {payload.get('solicitante','')}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Assinatura: ____________________________", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ===========================
# Páginas (nova organização)
# ===========================
def pagina_requisicoes():
    st.markdown("<div class='app-card title-bar'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 3])
    with col1:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=140)
    with col2:
        st.markdown("<h2 style='margin:0'>Requisição de abastecimento</h2>", unsafe_allow_html=True)
        st.markdown("<div style='color:#cfeefe'>Área principal de requisições — pesquisa, ações rápidas e criação</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Topo: pesquisa e ações
    topo_col1, topo_col2 = st.columns([3,1])
    with topo_col1:
        q = st.text_input("Pesquisar (ID, Placa, Condutor, Posto, Observações)", value="", key="pesquisa_reqs")
    with topo_col2:
        st.markdown("<div class='top-actions'>", unsafe_allow_html=True)
        st.button("⚙️", key="top_icon_filter")
        st.button("⬇️", key="top_icon_export")
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
    df_columns = [c for c in df.columns]
    for c in ["combustivel", "Combustivel"]:
        if c in df_columns:
            df['Combustivel'] = df[c].apply(normalize_combustivel)
            break
    # Garante colunas que exibiremos
    display_cols = [
        "Sel", "Acoes", "id", "data", "Placa", "Condutor", "Setor", "Subsetor",
        "Quantidade", "Status", "Posto", "Observacoes", "DataUso", "KmUso"
    ]

    if df.empty:
        st.info("Nenhuma requisição registrada ainda.")
    else:
        # prepara colunas derivadas
        df_display = df.copy()
        # padroniza nomes
        if 'data' in df_display.columns:
            df_display['data'] = pd.to_datetime(df_display['data'], errors='coerce').dt.strftime("%Y-%m-%d")
        else:
            df_display['data'] = ""

        df_display['Placa'] = df_display.get('Placa', "")
        df_display['Condutor'] = df_display.get('Condutor', df_display.get('Condutor', ""))
        df_display['Setor'] = df_display.get('Setor', "")
        df_display['Subsetor'] = df_display.get('Subsetor', "")
        # Quantidade: se TanqueCheio==1 mostra "Tanque cheio" senão total_litros
        if 'TanqueCheio' in df_display.columns:
            df_display['Quantidade'] = df_display.apply(lambda r: "Tanque cheio" if int(r.get('TanqueCheio') or 0) == 1 else str(r.get('total_litros') or ""), axis=1)
        else:
            df_display['Quantidade'] = df_display.get('total_litros', "")

        df_display['Status'] = df_display.get('Status', "")
        df_display['Posto'] = df_display.get('Posto', "")
        # Observações / justificativa: usa Observacoes ou Referente
        df_display['Observacoes'] = df_display.apply(lambda r: r.get('Observacoes') or r.get('Referente') or "", axis=1)
        df_display['DataUso'] = df_display.get('DataUso', "")
        df_display['KmUso'] = df_display.get('KmUso', "")

        # Aplica pesquisa simples
        if q and q.strip():
            ql = q.strip().lower()
            mask = df_display.apply(lambda row: ql in str(row.to_dict()).lower(), axis=1)
            df_display = df_display.loc[mask]

        # Mostra tabela com linhas interativas (checkbox + ações)
        st.markdown("#### Requisições")
        # Cabeçalho da grade
        header_cols = st.columns([0.06, 0.12, 0.06, 0.1, 0.12, 0.12, 0.09, 0.09, 0.09, 0.09, 0.1, 0.12])
        headers = ["Sel", "Ações", "ID", "Data", "Placa", "Condutor", "Setor", "Subsetor", "Quantidade", "Status", "Posto", "Observações"]
        for hc, h in zip(header_cols, headers):
            hc.write(f"**{h}**")

        # renderiza linhas (limitado a 200 para perfomance)
        for idx, row in df_display.head(200).iterrows():
            cols = st.columns([0.06, 0.12, 0.06, 0.1, 0.12, 0.12, 0.09, 0.09, 0.09, 0.09, 0.1, 0.12])
            sel_key = f"sel_{row['id']}"
            with cols[0]:
                sel = st.checkbox("", key=sel_key)
            with cols[1]:
                # ações por linha
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

        # Exibe ação rápida se usuário clicou visualizar/editar
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

        if st.session_state.get("_edit_row"):
            rid = st.session_state.pop("_edit_row")
            conn = get_connection()
            r = pd.read_sql(f"SELECT * FROM abastecimentos WHERE id = {int(rid)}", conn)
            conn.close()
            if not r.empty:
                r0 = r.iloc[0].to_dict()
                st.sidebar.markdown("### Editar Requisição")
                with st.form("form_edit_row"):
                    posto = st.text_input("Posto", value=r0.get('Posto',''))
                    observ = st.text_area("Observações", value=r0.get('Observacoes') or r0.get('Referente',''))
                    status = st.selectbox("Status", ["", "Pendente", "Em andamento", "Concluído", "Cancelado"], index=0)
                    data_uso = st.date_input("Data de uso", value=datetime.today())
                    km_uso = st.number_input("Quilometragem atual", min_value=0, step=1, value=int(r0.get('KmUso') or r0.get('Odometro') or 0))
                    salvar = st.form_submit_button("Salvar Alterações")
                    if salvar:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("""
                            UPDATE abastecimentos
                            SET Posto = ?, Observacoes = ?, Status = ?, DataUso = ?, KmUso = ?
                            WHERE id = ?
                        """, (posto, observ, status, data_uso.strftime("%Y-%m-%d"), km_uso, int(rid)))
                        conn.commit()
                        conn.close()
                        st.success("Alterações salvas.")

    st.markdown("---")
    st.caption("Fonte: tabela 'abastecimentos' (todas as requisições) — cadastros automáticos são criados ao salvar uma nova requisição.")

    # Novo formulário de requisição (quando acionado)
    if st.session_state.get("_novo_requisicao_open"):
        st.session_state["_novo_requisicao_open"] = False
        st.markdown("### Nova Requisição")
        with st.form("form_nova_req"):
            colA, colB, colC = st.columns(3)
            with colA:
                placa = st.text_input("Placa")
                condutor = st.text_input("Condutor")
                setor = st.text_input("Setor")
                subsetor = st.text_input("Subsetor")
            with colB:
                litros = st.number_input("Quantidade (L)", min_value=0.0, step=0.1)
                tanque_cheio = st.checkbox("Tanque cheio")
                combustivel = st.selectbox("Combustível", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "GNV"])
                posto = st.text_input("Posto")
            with colC:
                data_req = st.date_input("Data da requisição", value=datetime.today())
                odometro = st.number_input("Odômetro atual", min_value=0, step=1)
                referente = st.text_area("Observações / Justificativa", height=80)

            submit = st.form_submit_button("Salvar Requisição")
            if submit:
                if not placa.strip():
                    st.error("Placa é obrigatória.")
                else:
                    # Insere na tabela abastecimentos
                    conn = get_connection()
                    c = conn.cursor()
                    combustivel_norm = normalize_combustivel(combustivel)
                    c.execute("""
                        INSERT INTO abastecimentos
                        (Placa, valor_total, total_litros, data, Referente, Odometro, Posto, Combustivel, Condutor, Unidade, Setor, TanqueCheio, Subsetor, Observacoes, Status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        placa.strip(), 0.0, litros if not tanque_cheio else None,
                        data_req.strftime("%Y-%m-%d"), referente.strip(), int(odometro),
                        posto.strip(), combustivel_norm, condutor.strip(), "", setor.strip(),
                        1 if tanque_cheio else 0, subsetor.strip(), referente.strip(), "Pendente"
                    ))
                    conn.commit()
                    conn.close()

                    # Garante cadastro automático na tabela cadastros
                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute("""
                            INSERT OR IGNORE INTO cadastros (Placa, Condutor, Unidade, Setor)
                            VALUES (?, ?, ?, ?)
                        """, (placa.strip(), condutor.strip(), "", setor.strip()))
                        conn.commit()
                    except Exception:
                        pass
                    conn.close()

                    st.success("✅ Requisição salva e cadastro (se necessário) criado automaticamente.")

def pagina_dashboard():
    st.header("📊 Dashboard de Abastecimentos")
    # reutiliza a lógica de visualização já implementada no arquivo original
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

    # breve conjunto de KPIs para Dashboard (reduzido)
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
    st.info("Narrativas automáticas sobre consumo, tendências e anomalias.")
    # exemplo simples usando últimas 30 requisições
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
    st.markdown("Opções disponíveis:")
    st.write("- Ajuda")
    st.write("- Contas")
    st.write("- Preferências")
    st.write("- Manuais")
    st.markdown("---")
    st.info("Configurações avançadas (SMTP, templates, integrações) podem ser adicionadas aqui.")

# ===========================
# Menu principal
# ===========================
def main():
    st.sidebar.title("Frango Americano")
    # Menu lateral com identidade azul (itens solicitados)
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
