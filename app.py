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
arquivo_subido = st.file_uploader("Arraste o arquivo da construtora", type=["xlsx", "csv"])

if arquivo_subido is not None:
    try:
        # Lê a planilha pulando as 7 linhas de cabeçalho (padrão que você enviou)
        df = pd.read_csv(arquivo_subido, skiprows=7) if arquivo_subido.name.endswith('.csv') else pd.read_excel(arquivo_subido, skiprows=7)
        
        # Seleciona apenas as colunas que interessam para não poluir o visual
        colunas_necessarias = ['ITEM', 'DESCRIÇÃO', 'UND', 'QDT']
        # Filtra apenas as colunas que existem no arquivo para evitar erro
        df = df[[c for c in colunas_necessarias if c in df.columns]]
        df = df.dropna(subset=['DESCRIÇÃO']) # Remove linhas vazias

        st.subheader("2. Precificação")
        st.info("💡 Clique duas vezes na célula de 'Custo Unitário' para digitar o preço.")

        # Criamos a coluna de Custo preenchida com 0.0
        df['Custo Unitário (R$)'] = 0.0

        # Esta é a parte mágica: transforma a tabela em algo editável
        df_editavel = st.data_editor(
            df,
            column_config={
                "Custo Unitário (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "QDT": st.column_config.NumberColumn("Qtd", help="Quantidade vinda da planilha"),
            },
            disabled=["ITEM", "DESCRIÇÃO", "UND", "QDT"], # Bloqueia o que você não deve mexer
            use_container_width=True,
            hide_index=True,
        )

        # Cálculos Finais
        total_custo = (df_editavel['Custo Unitário (R$)'] * df_editavel['QDT']).sum()
        total_com_bdi = total_custo * bdi_calculo

        st.markdown("---")
        c1, c2 = st.columns(2)
        c1.metric("Custo Total (Materiais/Mão de Obra)", f"R$ {total_custo:,.2f}")
        c2.metric(f"PREÇO FINAL (Com {bdi_input}% BDI)", f"R$ {total_com_bdi:,.2f}")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")

st.markdown("---")
