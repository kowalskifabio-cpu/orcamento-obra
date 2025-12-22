import streamlit as st
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Sistema de Orçamento", layout="wide")

st.title("🏗️ Orçamentador Profissional")
st.markdown("---")

# Dados Gerais
col1, col2, col3 = st.columns(3)
with col1:
    nome_obra = st.text_input("Nome da Obra / Cliente", placeholder="Ex: Itaú Lounge GRU")
with col2:
    data_orcamento = st.date_input("Data")
with col3:
    bdi_input = st.number_input("BDI (%)", min_value=0.0, value=20.0, step=0.1)

bdi_calculo = 1 + (bdi_input / 100)

st.markdown("---")

# ÁREA DE UPLOAD
st.subheader("1. Importar Planilha")
arquivo_subido = st.file_uploader("Arraste o arquivo da construtora (Ex: Marcenaria ou Mármore)", type=["xlsx", "csv"])

if arquivo_subido is not None:
    try:
        # Lê a planilha pulando as 7 linhas (ajustado para o seu padrão)
        df = pd.read_csv(arquivo_subido, skiprows=7) if arquivo_subido.name.endswith('.csv') else pd.read_excel(arquivo_subido, skiprows=7)
        
        # Agora incluímos OBSERVAÇÕES e IMAGEM na lista de colunas permitidas
        colunas_alvo = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT']
        
        # Filtra apenas as colunas que realmente existem no arquivo subido
        df = df[[c for c in colunas_alvo if c in df.columns]]
        df = df.dropna(subset=['DESCRIÇÃO']) # Remove linhas sem descrição

        st.subheader("2. Precificação Detalhada")
        
        # Criamos a coluna de Custo Unitário se não existir
        if 'Custo Unitário (R$)' not in df.columns:
            df['Custo Unitário (R$)'] = 0.0

        # Tabela editável com as novas colunas
        df_editavel = st.data_editor(
            df,
            column_config={
                "ITEM": st.column_config.TextColumn("Item", width="small"),
                "DESCRIÇÃO": st.column_config.TextColumn("Descrição", width="medium"),
                "OBSERVAÇÕES": st.column_config.TextColumn("Observações", width="large"),
                "IMAGEM": st.column_config.TextColumn("Link/Ref Imagem", width="small"),
                "UND": st.column_config.TextColumn("Unid.", width="small"),
                "QDT": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "Custo Unitário (R$)": st.column_config.NumberColumn("Custo Unitário", format="R$ %.2f"),
            },
            # Bloqueamos as colunas vindas da construtora, liberamos apenas o Custo
            disabled=['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT'], 
            use_container_width=True,
            hide_index=True,
        )

        # Cálculos de Totais
        total_custo = (df_editavel['Custo Unitário (R$)'] * df_editavel['QDT']).sum()
        total_com_bdi = total_custo * bdi_calculo

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Custo Total (Base)", f"R$ {total_custo:,.2f}")
        with c2:
            st.metric(f"PREÇO FINAL (BDI {bdi_input}%)", f"R$ {total_com_bdi:,.2f}")

    except Exception as e:
        st.error(f
