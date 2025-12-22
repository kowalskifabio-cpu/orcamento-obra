import streamlit as st

# Configuração da página para o visual ficar limpo e largo
st.set_page_config(page_title="Sistema de Orçamento", layout="wide")

st.title("🏗️ Orçamentador de Obras")
st.markdown("---")

# Criando colunas para os dados não ficarem um em cima do outro (Visual Limpo)
col1, col2 = st.columns(2)

with col1:
    nome_obra = st.text_input("Nome da Obra / Cliente", placeholder="Ex: Itaú Lounge GRU")
    data_orcamento = st.date_input("Data do Orçamento")

with col2:
    bdi = st.number_input("Porcentagem de BDI (%)", min_value=0.0, value=20.0, step=0.1)
    tipo_obra = st.selectbox("Tipo de Serviço", ["Marcenaria", "Mármore e Granito", "Geral"])

st.markdown("---")
st.write(f"### Resumo: Obra {nome_obra}")
st.info(f"O sistema aplicará um BDI de {bdi}% sobre os custos unitários.")
