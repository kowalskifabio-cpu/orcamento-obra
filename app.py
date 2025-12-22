import streamlit as st
import pandas as pd

# Configuração da página para visual limpo
st.set_page_config(page_title="Sistema de Orçamento", layout="wide")

st.title("🏗️ Orçamentador Profissional")
st.markdown("---")

# 1. DADOS GERAIS (Cabeçalho)
col1, col2, col3 = st.columns(3)
with col1:
    nome_obra = st.text_input("Nome da Obra / Cliente", placeholder="Ex: Itaú Lounge GRU")
with col2:
    data_orcamento = st.date_input("Data")
with col3:
    bdi_input = st.number_input("BDI (%)", min_value=0.0, value=20.0, step=0.1)

bdi_calculo = 1 + (bdi_input / 100)

st.markdown("---")

# 2. ÁREA DE UPLOAD
st.subheader("1. Importar Planilha da Construtora")
arquivo_subido = st.file_uploader("Arraste o arquivo Excel ou CSV", type=["xlsx", "csv"])

if arquivo_subido is not None:
    try:
        # Lê a planilha pulando as 7 linhas iniciais (padrão das construtoras que você enviou)
        if arquivo_subido.name.endswith('.csv'):
            df = pd.read_csv(arquivo_subido, skiprows=7)
        else:
            df = pd.read_excel(arquivo_subido, skiprows=7)
        
        # Define as colunas que queremos mostrar (baseado no seu pedido)
        # Usamos nomes que aparecem nos seus arquivos: ITEM, DESCRIÇÃO, OBSERVAÇÕES, IMAGEM, UND, QDT
        colunas_desejadas = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT']
        
        # Filtra apenas as colunas que existem de fato no arquivo
        colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
        df = df[colunas_existentes].copy()
        
        # Remove linhas totalmente vazias
        df = df.dropna(subset=['DESCRIÇÃO'])

        # Adiciona a coluna de Custo se ela não existir
        if 'Custo Unitário (R$)' not in df.columns:
            df['Custo Unitário (R$)'] = 0.0

        st.subheader("2. Tabela de Precificação")
        st.info("Dê um duplo clique na célula de 'Custo Unitário' para editar o valor.")

        # Tabela Interativa
        df_editavel = st.data_editor(
            df,
            column_config={
                "ITEM": st.column_config.TextColumn("Item", width="small"),
                "DESCRIÇÃO": st.column_config.TextColumn("Descrição", width="medium"),
                "OBSERVAÇÕES": st.column_config.TextColumn("Observações", width="large"),
                "IMAGEM": st.column_config.TextColumn("Imagem", width="small"),
                "UND": st.column_config.TextColumn("Unid.", width="small"),
                "QDT": st.column_config.NumberColumn("Qtd", format="%.2f"),
                "Custo Unitário (R$)": st.column_config.NumberColumn("Custo Unitário", format="R$ %.2f"),
            },
            disabled=['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT'],
            use_container_width=True,
            hide_index=True,
        )

        # 3. CÁLCULOS TOTAIS
        total_custo = (df_editavel['Custo Unitário (R$)'] * df_editavel['QDT']).sum()
        total_com_bdi = total_custo * bdi_calculo

        st.markdown("---")
        res1, res2 = st.columns(2)
        res1.metric("Custo Total Acumulado", f"R$ {total_custo:,.2f}")
        res2.metric(f"PREÇO FINAL (Com {bdi_input}% BDI)", f"R$ {total_com_bdi:,.2f}")

    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")

st.markdown("---")
