import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador", layout="wide")

st.title("🏗️ Sistema de Orçamento v2")

# ESTE BLOCO CRIA OS DOIS CAMPOS LADO A LADO
st.subheader("📁 1. Upload de Arquivos Obrigatórios")
col1, col2 = st.columns(2)

with col1:
    arq_obra = st.file_uploader("Upload: Planilha da CONSTRUTORA", type=["xlsx", "csv"])

with col2:
    arq_lista = st.file_uploader("Upload: Seu LISTÃO (Aba MP)", type=["xlsx"])

st.divider()

if arq_obra and arq_lista:
    st.success("Os dois arquivos foram carregados! Iniciando processamento...")
    try:
        # Lendo a Obra (pulando 7 linhas conforme seu padrão)
        df_obra = pd.read_excel(arq_obra, skiprows=7) if arq_obra.name.endswith('.xlsx') else pd.read_csv(arq_obra, skiprows=7)
        # Lendo o Listão
        df_base = pd.read_excel(arq_lista, sheet_name='MP')
        
        st.write("### Itens da Obra Identificados")
        st.dataframe(df_obra.head())
    except Exception as e:
        st.error(f"Erro ao ler arquivos: {e}")
else:
    st.warning("⚠️ Atenção: Você precisa subir os DOIS arquivos acima para continuar.")
