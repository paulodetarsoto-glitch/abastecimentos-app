# =========================================================
#  Abastecimentos de Veículos - Controle com IA e Gmail
#  Autor: Paulo Varão
#  Versão: Painel rico (tema branco, filtros Select All, KPIs e gráficos extras)
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
st.set_page_config(page_title="Gestão de Abastecimentos", layout="wide", page_icon="⛽")

# ===========================
# Estilos (tema branco + cartões)
# ===========================
CUSTOM_CSS = """
<style>
body { background: #07132a !important; color: #E6F0FF; }

/* Neon accents and cards */
.neon { text-shadow: 0 0 8px rgba(0,150,255,0.6); color: #E6F0FF; }
.app-card { background: linear-gradient(180deg, rgba(7,19,42,0.6), rgba(4,12,24,0.6)); border: 1px solid rgba(0,150,255,0.08); border-radius: 12px; padding: 12px; }

[data-testid="stMetricValue"] { font-size: 18px !important; font-weight: 700; color: #E6F0FF; }
.kpi-card { background: linear-gradient(90deg, rgba(4,12,24,0.6), rgba(7,19,42,0.6)); border-radius:10px; padding:12px; border:1px solid rgba(0,150,255,0.12); }
.neon-title { color: #AEE7FF; text-shadow: 0 0 10px rgba(0,160,255,0.6); }
.stButton>button { background: linear-gradient(90deg,#1F77B4,#00A3FF); color: white; border: none; }
th { background: linear-gradient(90deg,#12324A,#1F77B4); color: white; }
hr { border: none; height:1px; background: rgba(0,150,255,0.06); margin: 1rem 0; }
</style>

"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ===========================
# Banco de dados
# ===========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabela de cadastros (com UNIQUE em Placa para consistência)
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

    # Tabela de abastecimentos
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
            Setor TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# Tabela para armazenar e-mails dos postos
def init_postos_emails():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS postos_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            posto TEXT UNIQUE,
            email TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_postos_emails()

def get_connection():
    return sqlite3.connect(DB_PATH)


def normalize_combustivel(val):
    """Normaliza o nome do combustível: remove espaços extras e capitaliza de forma consistente."""
    try:
        if val is None:
            return val
        s = str(val).strip()
        # capitaliza cada palavra (Gasolina -> Gasolina, gasolina -> Gasolina)
        s = ' '.join([w.capitalize() for w in s.split()])
        return s
    except Exception:
        return val

# === nova função utilitária para gerar bytes de Excel com fallback ===
def to_excel_bytes(sheets: dict, engine_order=('xlsxwriter', 'openpyxl')):
    """    # ...existing code...
                        if df_ab.empty:
                            st.warning('Não foram encontrados abastecimentos para o posto selecionado.')
                        else:
    -                        # Gera Excel em memória
    -                        buffer = io.BytesIO()
    -                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    -                            df_ab.to_excel(writer, index=False, sheet_name='Abastecimentos')
    -                        excel_bytes = buffer.getvalue()
    -                        smtp_conf = {
    -                            'server': smtp_server,
    -                            'port': int(smtp_port),
    -                            'user': smtp_user.strip(),
    -                            'password': smtp_password.strip(),
    -                            'use_tls': use_tls
    -                        }
    +                        # Oferece downloads (CSV + Excel se possível) e prepara anexo para envio.
    +                        csv_bytes = df_ab.to_csv(index=False).encode('utf-8')
    +                        st.download_button("⬇️ Baixar CSV", data=csv_bytes, file_name=f"abastecimentos_{posto_sel}.csv", mime="text/csv")
    +
    +                        sheets = {"Abastecimentos": df_ab}
    +                        excel_bytes, engine_used = to_excel_bytes(sheets)
    +                        if excel_bytes is not None:
    +                            st.download_button("⬇️ Baixar Excel", data=excel_bytes, file_name=f"abastecimentos_{posto_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    +                            attachment_bytes = excel_bytes
    +                            attachment_name = f"abastecimentos_{posto_sel}.xlsx"
    +                        else:
    +                            st.info("Gerar .xlsx requer 'xlsxwriter' ou 'openpyxl' instalados. Será usado CSV como anexo.")
    +                            attachment_bytes = csv_bytes
    +                            attachment_name = f"abastecimentos_{posto_sel}.csv"
    +
    +                        smtp_conf = {
    +                            'server': smtp_server,
    +                            'port': int(smtp_port),
    +                            'user': smtp_user.strip(),
    +                            'password': smtp_password.strip(),
    +                            'use_tls': use_tls
    +                        }
     
                             # monta corpo HTML se solicitado
                             html_body = None
                             if enviar_html:
                                                            try:
                                                                    df_temp = df_ab.copy()
    # ...existing code...
                            with st.spinner('Enviando e-mail com anexo Excel...'):
    -                            ok, err = send_email_smtp(to_address=to_email.strip(), subject=assunto, body=(mensagem if not enviar_html else ''), html_body=html_body, attachment_bytes=excel_bytes, attachment_name=f'abastecimentos_{posto_sel}.xlsx', smtp_config=smtp_conf)
    +                            ok, err = send_email_smtp(to_address=to_email.strip(), subject=assunto, body=(mensagem if not enviar_html else ''), html_body=html_body, attachment_bytes=attachment_bytes, attachment_name=attachment_name, smtp_config=smtp_conf)
                            if ok:
                                st.success('✅ E-mail enviado com sucesso!')
                                # guarda credenciais mínimas na sessão para facilitar (não persiste em disco)
                                st.session_state['smtp_user'] = smtp_user
                                st.session_state['smtp_server'] = smtp_server
                                st.session_state['smtp_port'] = int(smtp_port)
                            else:
                                st.error(f'Falha ao enviar e-mail: {err}')
    # ...existing
    Gera bytes de um arquivo .xlsx a partir de um dict {sheet_name: DataFrame}.
    Tenta engines na ordem informada; retorna (bytes, engine_usado) ou (None, None).
    """
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


# CRUD simples para emails dos postos
def get_postos_emails():
    conn = get_connection()
    df = pd.read_sql('SELECT * FROM postos_emails', conn)
    conn.close()
    return df

def save_posto_email(posto, email):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO postos_emails(posto, email) VALUES (?, ?)', (posto, email))
    conn.commit()
    conn.close()

def send_email_smtp(to_address, subject, body=None, html_body=None, attachment_bytes=None, attachment_name='relatorio.csv', smtp_config=None):
    """
    Envia e-mail via SMTP. Pode enviar texto (body) ou HTML (html_body).
    smtp_config: dict com keys 'server','port','user','password','use_tls'
    Retorna (True, '') ou (False, 'erro')
    """
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg['From'] = smtp_config.get('user') if smtp_config else ''
        msg['To'] = to_address
        msg['Subject'] = subject

        if html_body:
            # Texto alternativo simples
            msg.set_content(body if body else 'Este e-mail contém conteúdo em HTML.')
            msg.add_alternative(html_body, subtype='html')
        else:
            msg.set_content(body if body else '')

        if attachment_bytes is not None:
            # tenta inferir tipo por extensão
            subtype = 'octet-stream'
            maintype = 'application'
            if attachment_name.lower().endswith('.xlsx'):
                maintype, subtype = 'application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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
# Uploads Excel
# ===========================
def upload_cadastros(file):
    try:
        df = pd.read_excel(file)
        expected_cols = ["Placa", "Categoria", "Marca", "Modelo", "Condutor", "Unidade", "Setor"]
        if not all(col in df.columns for col in expected_cols):
            st.error(f"❌ Planilha inválida! Deve conter as colunas: {expected_cols}")
            return
        if not df["Placa"].notna().all():
            st.error("❌ Existem registros sem Placa. Corrija a planilha antes do upload.")
            return

        conn = get_connection()
        cur = conn.cursor()
        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT OR REPLACE INTO cadastros
                    (Placa, Categoria, Marca, Modelo, Condutor, Unidade, Setor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row["Placa"], row["Categoria"], row["Marca"], row["Modelo"],
                      row["Condutor"], row["Unidade"], row["Setor"]))
            except Exception as e:
                st.warning(f"Não foi possível inserir Placa {row.get('Placa')}: {e}")
        conn.commit()
        conn.close()
        st.success("✅ Cadastros importados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao fazer upload de cadastros: {e}")

def upload_abastecimentos(file):
    try:
        df = pd.read_excel(file)
        expected_cols = ["Placa", "Valor Total", "Total de litros", "Data", "Referente",
                         "Odometro", "Posto", "Combustivel", "Condutor", "Unidade", "Setor"]
        if not all(col in df.columns for col in expected_cols):
            st.error(f"❌ Planilha inválida! Deve conter as colunas: {expected_cols}")
            return
        if not df["Placa"].notna().all():
            st.error("❌ Existem registros sem Placa. Corrija a planilha antes do upload.")
            return

        df = df.copy()
        df.rename(columns={
            "Valor Total": "valor_total",
            "Total de litros": "total_litros",
            "Data": "data"
        }, inplace=True)
        # Normaliza coluna de Combustível para evitar duplicatas como 'Gasolina '
        if 'Combustivel' in df.columns:
            df['Combustivel'] = df['Combustivel'].apply(normalize_combustivel)

        conn = get_connection()
        df.to_sql("abastecimentos", conn, if_exists="append", index=False)
        conn.close()
        st.success("✅ Abastecimentos importados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao fazer upload de abastecimentos: {e}")

# ===========================
# Páginas
# ===========================
def pagina_inicio():
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=220)
    st.title("Sistema de Gestão de Abastecimentos")
    st.markdown("""
Bem-vindo ao painel completo de controle de abastecimentos!

O programa foi desenvolvido para centralizar e otimizar o controle da frota, oferecendo visão completa e estratégica:

- Registro detalhado por veículo, motorista, data, combustível, litros e custo.
- Análises macro e micro para identificar padrões e oportunidades de economia.
- Dashboards interativos com KPIs, gráficos e evolução histórica.
- Narrativas analíticas automáticas para apoiar decisões e planejamento.
""")

def pagina_cadastros():
    st.subheader("📂 Upload de planilha Excel (Cadastros)")
    file = st.file_uploader("Selecione o arquivo Cadastros.xlsx", type=["xlsx"], key="cadastros")
    if file:
        upload_cadastros(file)

    st.subheader("Cadastro Manual")
    with st.form("form_cadastro"):
        placa = st.text_input("Placa")
        categoria = st.text_input("Categoria")
        marca = st.text_input("Marca")
        modelo = st.text_input("Modelo")
        condutor = st.text_input("Condutor")
        unidade = st.text_input("Unidade")
        setor = st.text_input("Setor")
        submitted = st.form_submit_button("Salvar Cadastro")
        if submitted:
            if not placa.strip():
                st.error("❌ O campo Placa é obrigatório!")
            else:
                conn = get_connection()
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO cadastros (Placa, Categoria, Marca, Modelo, Condutor, Unidade, Setor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (placa.strip(), categoria.strip(), marca.strip(), modelo.strip(),
                      condutor.strip(), unidade.strip(), setor.strip()))
                conn.commit()
                conn.close()
                st.success("✅ Cadastro salvo com sucesso!")

    st.markdown("---")
    if st.button("🗑️ Apagar último cadastro"):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM cadastros ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        if row:
            c.execute("DELETE FROM cadastros WHERE id = ?", (row[0],))
            conn.commit()
            st.success("Último cadastro apagado com sucesso!")
        else:
            st.info("Nenhum cadastro para apagar.")
        conn.close()

def pagina_abastecimentos():

    # Carrega cadastros para listas suspensas
    conn = get_connection()
    cadastros_df = pd.read_sql("SELECT * FROM cadastros", conn)
    conn.close()

    st.subheader("📂 Upload de planilha Excel (Abastecimentos)")
    file = st.file_uploader("Selecione o arquivo Abastecimentos.xlsx", type=["xlsx"], key="abastecimentos")
    if file:
        upload_abastecimentos(file)

    st.subheader("Registro Manual")
    with st.form("form_abastecimento"):
        # Opções seguras (vazias se não houver cadastro)
        placas_opt = sorted(cadastros_df["Placa"].dropna().unique().tolist()) if not cadastros_df.empty else []
        condutores_opt = sorted(cadastros_df["Condutor"].dropna().unique().tolist()) if not cadastros_df.empty else []
        unidades_opt = sorted(cadastros_df["Unidade"].dropna().unique().tolist()) if not cadastros_df.empty else []
        setores_opt = sorted(cadastros_df["Setor"].dropna().unique().tolist()) if not cadastros_df.empty else []

        colA, colB, colC = st.columns(3)
        with colA:
            placa = st.selectbox("Placa", placas_opt, index=0 if placas_opt else None)
        with colB:
            # Preenchimento automático por placa (se existir)
            condutor_default = None
            unidade_default = None
            setor_default = None
            if placa and not cadastros_df.empty:
                row = cadastros_df.loc[cadastros_df["Placa"] == placa]
                if not row.empty:
                    condutor_default = row["Condutor"].iloc[0] if pd.notna(row["Condutor"].iloc[0]) else None
                    unidade_default = row["Unidade"].iloc[0] if pd.notna(row["Unidade"].iloc[0]) else None
                    setor_default = row["Setor"].iloc[0] if pd.notna(row["Setor"].iloc[0]) else None

            condutor = st.selectbox("Condutor", condutores_opt, index=condutores_opt.index(condutor_default) if condutor_default in condutores_opt else 0 if condutores_opt else None)
        with colC:
            unidade = st.selectbox("Unidade", unidades_opt, index=unidades_opt.index(unidade_default) if unidade_default in unidades_opt else 0 if unidades_opt else None)

        # Linha seguinte: Setor e Posto
        colD, colE = st.columns(2)
        with colD:
            # CORREÇÃO: garantir que "setor" venha da lista de setores (não da unidade)
            setor = st.selectbox("Setor", setores_opt, index=setores_opt.index(setor_default) if setor_default in setores_opt else 0 if setores_opt else None)
        with colE:
            posto = st.text_input("Posto")

        combustivel = st.selectbox("Combustível", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "GNV"])
        col1, col2, col3 = st.columns(3)
        with col1:
            valor_total = st.number_input("Valor Total (R$)", min_value=0.0, step=0.01)
        with col2:
            total_litros = st.number_input("Total de litros", min_value=0.0, step=0.01)
        with col3:
            odometro = st.number_input("Odômetro", min_value=0, step=1)

        col4, col5 = st.columns(2)
        with col4:
            data = st.date_input("Data", datetime.today())
        with col5:
            referente = st.text_input("Referente")

        submitted = st.form_submit_button("Salvar Abastecimento")

        if submitted:
            if not placa:
                st.error("❌ O campo Placa é obrigatório!")
            else:
                conn = get_connection()
                c = conn.cursor()
                # garante combustivel normalizado
                combustivel_norm = normalize_combustivel(combustivel)
                c.execute("""
                    INSERT INTO abastecimentos 
                    (Placa, valor_total, total_litros, data, Referente, Odometro, Posto, Combustivel, Condutor, Unidade, Setor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (placa, valor_total, total_litros, data.strftime("%Y-%m-%d"), referente,
                      odometro, posto, combustivel_norm, condutor, unidade, setor))
                conn.commit()
                conn.close()
                st.success("✅ Abastecimento registrado com sucesso!")

def multiselect_select_all(label, options, key=None):
    """
    Multiselect com opção "Selecionar tudo".
    - Se "Selecionar tudo" estiver selecionado OU se o usuário não selecionar nada, retorna todas as opções reais.
    """
    if not options:
        return []
    sentinel = "Selecionar tudo"
    opts = [sentinel] + list(options)
    selected = st.multiselect(label, opts, default=opts, key=key)
    if (sentinel in selected) or (len(selected) == 0):
        return list(options)
    else:
        # Garante que não passe o sentinel adiante
        return [x for x in selected if x != sentinel]

def pagina_dashboard():
    st.header("📊 Dashboard de Abastecimentos")

    # Leitura
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM abastecimentos", conn)
    conn.close()

    if df.empty:
        st.info("Nenhum dado registrado ainda.")
        return

    # Padronização
    df.columns = [c.strip().lower() for c in df.columns]
    df['data'] = pd.to_datetime(df['data'], errors='coerce')
    df = df.dropna(subset=['data'])
    # Normaliza combustivel para evitar duplicatas com espaços/maiúsculas
    if 'combustivel' in df.columns:
        df['combustivel'] = df['combustivel'].apply(normalize_combustivel)

    # ======================
    # Filtros (listas suspensas com 'Todos')
    # ======================
    with st.expander("🔎 Filtros", expanded=True):
        colf1, colf2, colf3, colf4, colf5 = st.columns(5)
        with colf1:
            placas_opts = ['Todos'] + sorted(df["placa"].dropna().unique().tolist())
            placa_sel = st.selectbox("Placa", placas_opts, index=0)
        with colf2:
            condutores_opts = ['Todos'] + sorted(df["condutor"].dropna().unique().tolist())
            condutor_sel = st.selectbox("Condutor", condutores_opts, index=0)
        with colf3:
            unidades_opts = ['Todos'] + sorted(df["unidade"].dropna().unique().tolist())
            unidade_sel = st.selectbox("Unidade", unidades_opts, index=0)
        with colf4:
            setores_opts = ['Todos'] + sorted(df["setor"].dropna().unique().tolist())
            setor_sel = st.selectbox("Setor", setores_opts, index=0)
        with colf5:
            combust_opts = ['Todos'] + sorted(df["combustivel"].dropna().unique().tolist())
            combust_sel = st.selectbox("Combustível", combust_opts, index=0)

        # Período (opcional)
        colp1, colp2 = st.columns(2)
        with colp1:
            dt_min = df["data"].min()
            dt_max = df["data"].max()
            start = st.date_input("Data inicial", dt_min.date() if pd.notna(dt_min) else datetime.today().date())
        with colp2:
            end = st.date_input("Data final", dt_max.date() if pd.notna(dt_max) else datetime.today().date())

    # Aplica filtros (quando não 'Todos')
    mask = pd.Series(True, index=df.index)
    if placa_sel != 'Todos':
        mask &= df['placa'] == placa_sel
    if condutor_sel != 'Todos':
        mask &= df['condutor'] == condutor_sel
    if unidade_sel != 'Todos':
        mask &= df['unidade'] == unidade_sel
    if setor_sel != 'Todos':
        mask &= df['setor'] == setor_sel
    if combust_sel != 'Todos':
        mask &= df['combustivel'] == combust_sel
    mask &= (df['data'].dt.date >= start) & (df['data'].dt.date <= end)
    dff = df.loc[mask].copy()

    if dff.empty:
        st.warning("Não há dados com os filtros selecionados.")
        return

    # ======================
    # KPIs (originais + extras)
    # ======================
    total_litros = float(dff['total_litros'].sum())
    total_valor = float(dff['valor_total'].sum())
    n_veiculos = int(dff["placa"].nunique())
    n_postos = int(dff["posto"].nunique())
    custo_medio_litro = (total_valor / total_litros) if total_litros > 0 else 0.0
    ticket_medio = float(dff["valor_total"].mean()) if not dff.empty else 0.0
    abastecimentos_qtd = int(len(dff))

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: st.metric("🚗 Veículos distintos", n_veiculos)
    with k2: st.metric("⛽ Postos distintos", n_postos)
    with k3: st.metric("🛢 Total de litros", f"{total_litros:,.2f}")
    with k4: st.metric("💰 Valor total gasto", f"R$ {total_valor:,.2f}")
    with k5: st.metric("💸 Custo médio/L", f"R$ {custo_medio_litro:.2f}")
    with k6: st.metric("🧾 Ticket médio", f"R$ {ticket_medio:,.2f}")


    # Custo médio por litro por combustível
    df_custo_comb = dff.groupby('combustivel', as_index=False).apply(
        lambda g: pd.Series({
            'custo_medio_litro': g['valor_total'].sum() / g['total_litros'].sum() if g['total_litros'].sum() > 0 else 0.0
        })
    ).reset_index(drop=True)
    # Gráfico de colunas verticais
    fig_custo_comb = px.bar(
        df_custo_comb,
        x='combustivel',
        y='custo_medio_litro',
        text='custo_medio_litro',
        title='Custo médio por litro por Combustível',
        color='combustivel',
        color_discrete_sequence=px.colors.qualitative.Set1
    )
    fig_custo_comb.update_traces(texttemplate='R$ %{y:.2f}', textposition='outside')
    fig_custo_comb.update_layout(yaxis_title='R$ por litro', xaxis_title='Combustível')
    st.plotly_chart(fig_custo_comb, use_container_width=True)
    st.markdown("---")

    # ======================
    # Gráficos reorganizados e novos
    # ======================
    # calcula preco medio por registro para alguns gráficos
    dff["preco_medio"] = np.where(dff["total_litros"] > 0, dff["valor_total"] / dff["total_litros"], np.nan)

    # Row 1: distribuição por Unidade, Combustível e Valor por Posto
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        fig_unidade = px.pie(dff, names="unidade", values="total_litros", title="Litros por Unidade", color_discrete_sequence=px.colors.qualitative.Bold)
        fig_unidade.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_unidade, use_container_width=True)
    with r1c2:
        fig_comb = px.pie(dff, names="combustivel", values="total_litros", title="Litros por Combustível", color_discrete_sequence=px.colors.qualitative.Set3)
        fig_comb.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_comb, use_container_width=True)
    with r1c3:
        # mostra todos os postos ordenados por valor (sem limite Top-N)
        df_posto = dff.groupby("posto", as_index=False)["valor_total"].sum().sort_values("valor_total", ascending=True)
        # barra horizontal: valor no eixo x, posto no y
        fig_posto = px.bar(df_posto, x="valor_total", y="posto", orientation='h', text="valor_total", title="Postos por Valor", color="valor_total", color_continuous_scale="Plasma")
        # garante que maior valor apareça no topo
        fig_posto.update_layout(yaxis={'categoryorder':'total ascending'})
        fig_posto.update_traces(textposition='auto')
        st.plotly_chart(fig_posto, use_container_width=True)

    # Row 2: Placa ranking, Boxplot preço por combustível, Histograma de tickets
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        # calcula total por placa (mostra todas as placas, sem limitar)
        df_placa = dff.groupby("placa", as_index=False)["total_litros"].sum().sort_values("total_litros", ascending=True)
        # barras horizontais em formato ranking (maior no topo)
        fig_placa = px.bar(df_placa, x="total_litros", y="placa", orientation='h', text="total_litros", title="Placas por Litros (ranking)", color="total_litros", color_continuous_scale="Viridis")
        # força ordenação por total para garantir ranking visual (maior no topo)
        fig_placa.update_layout(yaxis={'categoryorder':'total ascending'})
        fig_placa.update_traces(textposition='auto')
        st.plotly_chart(fig_placa, use_container_width=True)
    # Ranking por Setor (horizontal) - mostra todos os setores
    try:
        df_setor = dff.groupby('setor', as_index=False)['total_litros'].sum().sort_values('total_litros', ascending=True)
        fig_setor = px.bar(df_setor, x='total_litros', y='setor', orientation='h', text='total_litros', title='Setores por Total de Litros', color='total_litros', color_continuous_scale='Blues')
        fig_setor.update_layout(yaxis={'categoryorder':'total ascending'})
        fig_setor.update_traces(textposition='auto')
        st.plotly_chart(fig_setor, use_container_width=True)
    except Exception:
        pass
    with r2c2:
        fig_box = px.box(dff, x='combustivel', y='preco_medio', title='Boxplot Preço médio por Combustível', points='all', color='combustivel')
        st.plotly_chart(fig_box, use_container_width=True)
    with r2c3:
        fig_hist = px.histogram(dff, x='valor_total', nbins=25, title='Distribuição de Ticket (Valor Total)', color_discrete_sequence=['#636EFA'])
        st.plotly_chart(fig_hist, use_container_width=True)

    # Row 3: Séries temporais
    t1, t2 = st.columns(2)
    with t1:
        df_mes_litros = dff.groupby(dff['data'].dt.to_period('M'))['total_litros'].sum().reset_index()
        df_mes_litros['data'] = df_mes_litros['data'].dt.strftime('%b/%y')
        fig_linhas = px.line(df_mes_litros, x="data", y="total_litros", markers=True, title="Evolução de Litros por Mês", labels={'data': 'Mês', 'total_litros': 'Total de Litros'}, color_discrete_sequence=["#00CC96"])
        st.plotly_chart(fig_linhas, use_container_width=True)
    with t2:
        df_mes_valor = dff.groupby(dff['data'].dt.to_period('M'))['valor_total'].sum().reset_index()
        df_mes_valor['data'] = df_mes_valor['data'].dt.strftime('%b/%y')
        fig_valor = px.line(df_mes_valor, x="data", y="valor_total", markers=True, title="Evolução de Valor por Mês", color_discrete_sequence=["#1F77B4"])
        st.plotly_chart(fig_valor, use_container_width=True)
    # calcula preco medio por mes (necessário para narrativas e export)
    preco_mes = dff.groupby(dff['data'].dt.to_period('M'))['preco_medio'].mean().reset_index()
    preco_mes['data'] = preco_mes['data'].dt.strftime('%b/%y')

    # Heatmap e dispersão
    h1, h2 = st.columns(2)
    with h1:
        heat = dff.copy()
        heat["mes"] = heat["data"].dt.strftime("%b/%y")
        heat_pv = pd.pivot_table(heat, values="total_litros", index="combustivel", columns="mes", aggfunc="sum", fill_value=0)
        fig_heat = px.imshow(heat_pv, aspect="auto", title="Heatmap - Litros por Combustível e Mês", labels=dict(color="Litros"))
        st.plotly_chart(fig_heat, use_container_width=True)
    with h2:
        fig_scatter = px.scatter(dff, x="total_litros", y="valor_total", color="combustivel", size="valor_total", hover_data=["placa", "posto", "unidade", "setor"], title="Custo x Litros por Abastecimento")
        st.plotly_chart(fig_scatter, use_container_width=True)

    # ======================
    # Narrativas inteligentes (mantidas + extras)
    # ======================
    st.markdown("### 🧠 Insights Automáticos")
    try:
        litros_por_placa = dff.groupby("placa")["total_litros"].sum()
        maior_consumo = litros_por_placa.idxmax()
        menor_consumo = litros_por_placa.idxmin()
        st.markdown(f"- Veículo com **maior consumo**: **{maior_consumo}** ({litros_por_placa.max():,.2f} L).")
        st.markdown(f"- Veículo com **menor consumo**: **{menor_consumo}** ({litros_por_placa.min():,.2f} L).")
    except ValueError:
        pass

    st.markdown(f"- Total consumido: **{total_litros:,.2f} litros**.")
    st.markdown(f"- Total gasto: **R$ {total_valor:,.2f}**.")
    st.markdown(f"- Custo médio: **R$ {custo_medio_litro:.2f}/L**.")
    if not preco_mes.empty:
        ult = preco_mes["preco_medio"].iloc[-1]
        st.markdown(f"- Preço médio do último mês analisado: **R$ {ult:.2f}/L**.")

    # Projeção simples (próximo mês = média dos últimos 3 meses)
    proj = None
    if len(df_mes_valor) >= 1:
        ultimos_3 = df_mes_valor.tail(3)["valor_total"]
        if not ultimos_3.empty:
            proj = float(ultimos_3.mean())
            st.info(f"📈 Projeção de gasto para o próximo mês (média dos últimos 3): **R$ {proj:,.2f}**")

    # ======================
    # Exportações
    # ======================
    st.markdown("### 📤 Exportar dados filtrados")
    colx1, colx2 = st.columns(2)
    with colx1:
        csv = dff.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV", data=csv, file_name="abastecimentos_filtrado.csv", mime="text/csv")
    with colx2:
        # Excel em memória com fallback para engines disponíveis (to_excel_bytes)
        sheets = {"Dados": dff, "Litros_Mensal": df_mes_litros, "Valor_Mensal": df_mes_valor}
        if preco_mes is not None:
            sheets["Preco_Medio"] = preco_mes

        excel_bytes, engine_used = to_excel_bytes(sheets)
        if excel_bytes is not None:
            st.download_button("⬇️ Baixar Excel", data=excel_bytes,
                               file_name="abastecimentos_filtrado.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("Não foi possível gerar .xlsx (xlsxwriter/openpyxl não disponíveis). Use o CSV ou instale 'xlsxwriter' ou 'openpyxl'.")

    st.markdown("### 📋 Tabela (dados filtrados)")
    display_df = dff.copy()
    # remove coluna Odometro se existir (normalização de nomes já feita para minusculas acima)
    if 'odometro' in [c.lower() for c in display_df.columns]:
        # busca a coluna original e remove
        cols = display_df.columns.tolist()
        cols = [c for c in cols if c.lower() != 'odometro']
        display_df = display_df[cols]
    st.dataframe(display_df.sort_values("data", ascending=False), use_container_width=True)

def generate_request_pdf(payload: dict) -> bytes:
    """
    Gera PDF da requisição a partir do dict payload e retorna bytes.
    Campos esperados: placa, justificativa, supervisor, setor, litros, combustivel, posto, solicitante, data
    """
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

    title = Paragraph("Requisição de Abastecimento", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))

    meta = [
        ["Data:", payload.get("data", "")],
        ["Posto destino:", payload.get("posto", "")],
        ["Placa:", payload.get("placa", "")],
        ["Motorista:", payload.get("motorista", "")],  # NOVO
        ["Supervisor:", payload.get("supervisor", "")],
        ["Setor:", payload.get("setor", "")],
        ["Quilometragem atual:", str(payload.get("km_atual", ""))],  # NOVO
        ["Quantidade (L):", str(payload.get("litros", ""))],
        ["Combustível:", payload.get("combustivel", "")]
    ]
    tbl = Table(meta, colWidths=[110, 380])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('BOX', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica')
    ]))
    story.append(tbl)
    story.append(Spacer(1, 16))

    story.append(Paragraph("<b>Justificativa</b>", styles['Heading3']))
    justificativa = Paragraph(payload.get("justificativa", "").replace("\n","<br/>"), styles['Normal'])
    story.append(justificativa)
    story.append(Spacer(1, 24))

    story.append(Paragraph(f"Solicitado por: {payload.get('solicitante','')}", styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Assinatura: ____________________________", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def pagina_email():
    st.header("✉️ Enviar Requisição de Abastecimento em PDF ao Posto")
    st.info("Preencha os dados abaixo para gerar e enviar a ficha de requisição em PDF diretamente ao e-mail do posto selecionado.")

    # Campos principais da requisição
    with st.form("form_requisicao_pdf"):
        st.subheader("Dados da Requisição")

        col1, col2 = st.columns(2)
        with col1:
            placa = st.text_input("Placa do veículo")
            supervisor = st.text_input("Supervisor responsável")
            setor = st.text_input("Setor")
            motorista = st.text_input("Nome do motorista")  # NOVO
            data_abastecimento = st.date_input("Data do abastecimento", value=datetime.today())  # NOVO
            km_atual = st.number_input("Quilometragem atual", min_value=0, step=1)  # NOVO
        with col2:
            litros = st.number_input("Quantidade de litros", min_value=0.0, step=0.1)
            combustivel = st.selectbox("Tipo de combustível", ["Gasolina", "Etanol", "Diesel S10", "Diesel S500", "GNV"])
        
        justificativa = st.text_area("Justificativa", height=100)

        st.markdown("---")
        st.subheader("Informações de E-mail")

        # Dados do remetente pré-preenchidos
        nosso_email = st.text_input("Nosso Email (remetente)", value="paulodetarso.to@frangoamericano.com", disabled=True)
        smtp_password = st.text_input("Senha do Email", value="", type="password", disabled=True)
        smtp_server = st.text_input("Servidor SMTP", value="smtp-mail.outlook.com", disabled=True)
        smtp_port = st.text_input("Porta SMTP", value="587", disabled=True)
        st.markdown("Criptografia: **STARTTLS** (já configurado)")

        # E-mail do posto (destinatário)
        email_posto = st.text_input("E-mail do posto (destino)", value="", help="Digite o e-mail do posto que receberá a requisição.")

        enviar = st.form_submit_button("Enviar Requisição em PDF")

        if enviar:
            # Validações
            if not placa.strip():
                st.error("Informe a placa do veículo.")
            elif not supervisor.strip():
                st.error("Informe o supervisor responsável.")
            elif not setor.strip():
                st.error("Informe o setor.")
            elif litros <= 0:
                st.error("Informe a quantidade de litros (maior que zero).")
            elif not email_posto.strip():
                st.error("Informe o e-mail do posto.")
            else:
                payload = {
                    "data": data_abastecimento.strftime("%Y-%m-%d"),
                    "posto": "",  # opcional
                    "placa": placa.strip(),
                    "supervisor": supervisor.strip(),
                    "setor": setor.strip(),
                    "motorista": motorista.strip(),  # NOVO
                    "litros": litros,
                    "combustivel": combustivel,
                    "justificativa": justificativa.strip(),
                    "solicitante": nosso_email,
                    "km_atual": km_atual  # NOVO
                }
                try:
                    pdf_bytes = generate_request_pdf(payload)
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")
                    pdf_bytes = None

                if pdf_bytes:
                    fname = f"requisicao_{placa.strip()}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                    smtp_conf = {
                        'server': smtp_server,
                        'port': int(smtp_port),
                        'user': nosso_email.strip(),
                        'password': smtp_password.strip(),
                        'use_tls': True
                    }
                    subject = f"Requisição de Abastecimento - Placa {placa.strip()}"
                    body = f"Prezados,\n\nSegue em anexo a requisição de abastecimento do veículo {placa.strip()}.\n\nAtenciosamente."

                    with st.spinner("Enviando e-mail com PDF..."):
                        ok, err = send_email_smtp(
                            to_address=email_posto.strip(),
                            subject=subject,
                            body=body,
                            html_body=None,
                            attachment_bytes=pdf_bytes,
                            attachment_name=fname,
                            smtp_config=smtp_conf
                        )
                    if ok:
                        st.success("✅ Requisição enviada com sucesso ao posto!")
                    else:
                        st.error(f"Falha ao enviar: {err}")

# Menu
# ===========================
def main():
    menu = st.sidebar.radio(
        "Menu",
        ["Início", "Cadastros", "Abastecimentos", "Dashboard", "Relatórios & E-mail"]
    )

    if menu == "Início":
        pagina_inicio()
    elif menu == "Cadastros":
        pagina_cadastros()
    elif menu == "Abastecimentos":
        pagina_abastecimentos()
    elif menu == "Dashboard":
        pagina_dashboard()
    elif menu == "Relatórios & E-mail":
        pagina_email()

if __name__ == "__main__":
    main()
