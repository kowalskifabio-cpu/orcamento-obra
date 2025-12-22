import streamlit as st
import pandas as pd

st.set_page_config(page_title="Orçamentador Técnico", layout="wide")

st.title("🏗️ Composição de Custos Detalhada")

# --- BARRA LATERAL: CONFIGURAÇÕES GERAIS ---
with st.sidebar:
    st.header("Configurações de Impostos e BDI")
    percentual_imposto = st.number_input("Impostos Totais (%)", value=15.0)
    percentual_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    percentual_lucro = st.number_input("Margem de Lucro/BDI (%)", value=20.0)
    frete_geral = st.number_input("Frete Global (R$)", value=0.0)

st.markdown("---")

arquivo_subido = st.file_uploader("Arraste a planilha da construtora", type=["xlsx", "csv"])

if arquivo_subido is not None:
    try:
        # Leitura padrão (pulando 7 linhas conforme seus arquivos)
        df = pd.read_csv(arquivo_subido, skiprows=7) if arquivo_subido.name.endswith('.csv') else pd.read_excel(arquivo_subido, skiprows=7)
        
        # Seleciona colunas base
        colunas_base = ['ITEM', 'DESCRIÇÃO', 'UND', 'QDT']
        df = df[[c for c in colunas_base if c in df.columns]].copy()
        df = df.dropna(subset=['DESCRIÇÃO'])

        # --- CRIAÇÃO DAS COLUNAS DE CÁLCULO ---
        # Iniciamos com valores zerados para você preencher
        if 'Custo Mat. Unit.' not in df.columns:
            df['Custo Mat. Unit.'] = 0.0
        if 'Mão de Obra Unit.' not in df.columns:
            df['Mão de Obra Unit.'] = 0.0

        st.subheader("🛠️ Composição por Item")
        st.caption("Ajuste os valores de Material e Mão de Obra abaixo:")

        # Tabela Editável de Engenharia
        df_editado = st.data_editor(
            df,
            column_config={
                "Custo Mat. Unit.": st.column_config.NumberColumn("Material (R$)", format="R$ %.2f"),
                "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. (R$)", format="R$ %.2f"),
            },
            disabled=['ITEM', 'DESCRIÇÃO', 'UND', 'QDT'],
            use_container_width=True,
            hide_index=True,
        )

        # --- LÓGICA DE CÁLCULO MATEMÁTICO ---
        # 1. M.O. com Encargos
        mo_com_encargos = df_editado['Mão de Obra Unit.'] * (1 + percentual_encargos/100)
        
        # 2. Custo Direto Total (Material + M.O. com Encargos)
        custo_direto_unitario = df_editado['Custo Mat. Unit.'] + mo_com_encargos
        
        # 3. Preço com Lucro e Imposto (Fórmula de Markup)
        # Preço = Custo Direto / (1 - (Imposto + Lucro)/100)
        divisor = 1 - ((percentual_imposto + percentual_lucro) / 100)
        df_editado['Preço Final Unit.'] = custo_direto_unitario / divisor
        
        # 4. Total por Linha
        df_editado['Total Item'] = df_editado['Preço Final Unit.'] * df_editado['QDT']

        st.markdown("---")
        
        # Exibição dos resultados
        st.subheader("📊 Resumo do Orçamento")
        total_proposta = df_editado['Total Item'].sum() + frete_geral
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total de Materiais", f"R$ {df_editado['Custo Mat. Unit.'].sum():,.2f}")
        c2.metric("Total M.O. (s/ encargos)", f"R$ {df_editado['Mão de Obra Unit.'].sum():,.2f}")
        c3.metric("VALOR TOTAL (c/ Frete)", f"R$ {total_proposta:,.2f}")

        st.write("### Detalhamento Final")
        st.dataframe(df_editado[['ITEM', 'DESCRIÇÃO', 'Preço Final Unit.', 'Total Item']], use_container_width=True)

    except Exception as e:
        st.error(f"Erro técnico: {e}")
