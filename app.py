import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Sistema de Orçamento", layout="wide")

st.title("🏗️ Orçamentador de Obras")
st.markdown("---")

# Dados Gerais
col1, col2 = st.columns(2)
with col1:
    nome_obra = st.text_input("Nome da Obra / Cliente", placeholder="Ex: Itaú Lounge GRU")
    data_orcamento = st.date_input("Data do Orçamento")
with col2:
    bdi = st.number_input("Porcentagem de BDI (%)", min_value=0.0, value=20.0, step=0.1)

st.markdown("---")

# ÁREA DE UPLOAD (Importação)
st.subheader("1. Importar Planilha da Construtora")
arquivo_subido = st.file_uploader("Arraste aqui o arquivo Excel ou CSV da construtora", type=["xlsx", "csv"])

if arquivo_subido is not None:
    try:
        # Aqui o código pula as 7 linhas vazias que vimos nos seus arquivos
        df = pd.read_csv(arquivo_subido, skiprows=7) if arquivo_subido.name.endswith('.csv') else pd.read_excel(arquivo_subido, skiprows=7)
        
        # Limpa colunas vazias
        df = df.dropna(how='all', axis=1)
        
        st.success("Planilha importada com sucesso!")
        st.write("### Itens Identificados:")
        
        # Mostra a tabela de forma limpa
        st.dataframe(df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}. Verifique se a planilha segue o padrão de 7 linhas de cabeçalho.")

st.markdown("---")
