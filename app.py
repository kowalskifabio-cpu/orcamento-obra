import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

# 1. Configuração inicial
st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- EXIBIÇÃO DA LOGO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    logo = Image.open(nome_logo)
    st.sidebar.image(logo, use_container_width=True)
else:
    st.sidebar.warning("Logo não encontrada no GitHub.")

st.title("🏗️ Sistema de Orçamento Profissional")
st.markdown("---")

# --- 2. ÁREA DE UPLOAD (Nomes atualizados) ---
st.subheader("📁 1. Carregar Ficheiros")
col_up1, col_up2 = st.columns(2)

with col_up1:
    arq_obra = st.file_uploader("Planilha da CONSTRUTORA", type=["xlsx", "csv"])

with col_up2:
    # Substituído conforme solicitado
    arq_lista = st.file_uploader("MP Valores", type=["xlsx", "csv"])

# --- 3. CONFIGURAÇÕES (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Parâmetros Financeiros")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)
    frete_fixo = st.number_input("Frete Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 4. PROCESSAMENTO ---
if arq_obra and arq_lista:
    try:
        # Lendo a Obra (pula 7 linhas)
        if arq_obra.name.endswith('.csv'):
            df_obra = pd.read_csv(arq_obra, skiprows=7)
        else:
            df_obra = pd.read_excel(arq_obra, skiprows=7)
        
        # Garante que a primeira coluna (ITEM) seja lida e mantida
        df_obra.columns = [c if not str(c).startswith('Unnamed') else f'C_{i}' for i, c in enumerate(df_obra.columns)]

        # Lendo o ficheiro MP Valores
        if arq_lista.name.endswith('.csv'):
            df_base = pd.read_csv(arq_lista)
        else:
            try:
                df_base = pd.read_excel(arq_lista, sheet_name='MP')
            except:
                df_base = pd.read_excel(arq_lista)
        
        # Adiciona colunas de trabalho
        if 'Custo Mat. Unit.' not in df_obra.columns:
            df_obra['Custo Mat. Unit.'] = 0.0
        if 'Mão de Obra Unit.' not in df_obra.columns:
            df_obra['Mão de Obra Unit.'] = 0.0

        st.success(f"✅ Arquivos carregados! Base 'MP Valores' com
