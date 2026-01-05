import streamlit as st
import pandas as pd
from io import BytesIO

# 1. Configuração inicial
st.set_page_config(page_title="Orçamentador Inteligente", layout="wide")

# Força o reset se os arquivos forem removidos
if 'dados_obra' not in st.session_state:
    st.session_state.dados_obra = None

st.title("🏗️ Orçamentador: Cruzamento Construtora x Listão")
st.markdown("---")

# 2. ÁREA DE UPLOAD DUPLO (Obrigatório)
st.subheader("📁 Upload de Documentos")
col_up1, col_up2 = st.columns(2)

with col_up1:
    arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])

with col_up2:
    arq_lista = st.file_uploader("2. Seu LISTÃO DE PREÇOS (Aba MP)", type=["xlsx"])

# 3. PARÂMETROS FINANCEIROS (Sidebar)
with st.sidebar:
    st.header("⚙️ Configurações")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)
    frete_fixo = st.number_input("Frete Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# 4. LÓGICA DE PROCESSAMENTO
if arq_obra and arq_lista:
    try:
        # Lendo a Obra (pula 7 linhas)
        if arq_obra.name.endswith('.csv'):
            df_obra = pd.read_csv(arq_obra, skiprows=7)
        else:
            df_obra = pd.read_excel(arq_obra, skiprows=7)
        
        # Lendo o Listão (procura aba MP)
        df_base = pd.read_excel(arq_lista, sheet_name='MP')
        
        st.success(f"✅ Sucesso! Obra carregada e Listão com {len(df_base)} itens pronto.")

        # Limpeza da planilha da obra
        cols_obra = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'UND', 'QDT']
        df_processado = df_obra[[c for c in cols_obra if c in df_obra.columns]].copy()
        df_processado = df_processado.dropna(subset=['DESCRIÇÃO'])
        
        # Adiciona colunas de custo zeradas para preenchimento
        df_processado['Custo Mat. Unit.'] = 0.0
        df_processado['Mão de Obra Unit.'] = 0.0

        # 5. BUSCADOR DE PREÇOS
        st.markdown("---")
        with st.expander("🔍 CONSULTAR PREÇOS NO LISTÃO (MP)"):
            termo = st.text_input("Procure por um material (ex: Mármore, MDF, Puxador):")
            if termo:
                resultado = df_base[df_base.astype(str).apply(lambda x: x.str.contains(termo, case=False)).any(axis=1)]
                st.dataframe(resultado, use_container_width=True)

        # 6. TABELA DE ORÇAMENTO
        st.subheader("📝 Tabela de Orçamento")
        
        if st.button("➕ Adicionar Linha Manual"):
            nova = pd.DataFrame([{'ITEM': '', 'DESCRIÇÃO': 'Novo Item', 'UND': 'und', 'QDT': 1.0, 'Custo Mat. Unit.': 0.0, 'Mão de Obra Unit.': 0.0}])
            df_processado = pd.concat([df_processado, nova], ignore_index=True)

        df_editavel = st.data_editor(
            df_processado,
            num_rows="dynamic",
            column_config={
                "Custo Mat. Unit.": st.column_config.NumberColumn("Mat. Unit. (R$)", format="R$ %.2f"),
                "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. Unit. (R$)", format="R$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # 7. CÁLCULOS
        mo_com_enc = df_editavel['Mão de Obra Unit.'] * (1 + perc_encargos/100)
        custo_direto = df_editavel['Custo Mat. Unit.'] + mo_com_enc
        venda_unit = custo_direto / divisor
        total_item = venda_unit * df_editavel['QDT']
        total_geral = total_item.sum() + frete_fixo

        st.markdown("---")
        st.metric("VALOR TOTAL DA PROPOSTA", f"R$ {total_geral:,.2f}")

        # 8. EXPORTAÇÃO
        df_export = df_editavel.copy()
        df_export['Venda Unitário'] = venda_unit
        df_export['Total Item'] = total_item
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False)
        
        st.download_button("💾 Baixar Orçamento em Excel", data=output.getvalue(), file_name="Orcamento_Finalizado.xlsx")

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}. Verifique se a aba 'MP' existe no Listão.")

else:
    st.warning("⚠️ Por favor, suba os DOIS arquivos acima para liberar o orçamento.")
