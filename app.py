import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Dinâmico", layout="wide")

st.title("🏗️ Orçamentador: Cruzamento em Tempo Real")
st.info("Para começar, faça o upload de ambos os arquivos abaixo.")

# --- 1. ÁREA DE UPLOAD DUPLO ---
col_up1, col_up2 = st.columns(2)

with col_up1:
    st.subheader("📋 1. Planilha da Construtora")
    arq_obra = st.file_uploader("Arraste o arquivo da OBRA", type=["xlsx", "csv"], key="obra")

with col_up2:
    st.subheader("💰 2. Listão de Preços (MP)")
    arq_lista = st.file_uploader("Arraste o seu LISTÃO ATUALIZADO", type=["xlsx"], key="lista")

# --- 2. CONFIGURAÇÕES NA BARRA LATERAL ---
with st.sidebar:
    st.header("Parâmetros Financeiros")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro/BDI (%)", value=20.0)
    frete_fixo = st.number_input("Frete Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 3. PROCESSAMENTO DOS DADOS ---
if arq_obra and arq_lista:
    try:
        # Lendo a Obra (pulando as 7 linhas padrão)
        df_obra = pd.read_csv(arq_obra, skiprows=7) if arq_obra.name.endswith('.csv') else pd.read_excel(arq_obra, skiprows=7)
        
        # Lendo o Listão (procurando a aba MP)
        df_base = pd.read_excel(arq_lista, sheet_name='MP')
        st.success(f"✅ Conectado: {len(df_base)} itens de preço carregados.")

        # Limpeza básica da planilha da obra
        cols_obra = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'UND', 'QDT']
        df_final = df_obra[[c for c in cols_obra if c in df_obra.columns]].copy()
        df_final = df_final.dropna(subset=['DESCRIÇÃO'])

        # Criando as colunas que você vai preencher ou o sistema vai sugerir
        if 'Custo Mat. Unit.' not in df_final.columns:
            df_final['Custo Mat. Unit.'] = 0.0
        if 'Mão de Obra Unit.' not in df_final.columns:
            df_final['Mão de Obra Unit.'] = 0.0

        # --- 4. BUSCADOR DE PREÇOS (O "CRUZAMENTO") ---
        st.markdown("---")
        with st.expander("🔍 BUSCADOR DE PREÇOS NO LISTÃO"):
            termo = st.text_input("Digite o nome do material para buscar no Listão:")
            if termo:
                # Busca em todas as colunas do listão
                mask = df_base.astype(str).apply(lambda x: x.str.contains(termo, case=False)).any(axis=1)
                st.dataframe(df_base[mask], use_container_width=True)

        # --- 5. TABELA DE ORÇAMENTO EDITÁVEL ---
        st.subheader("📝 Edição do Orçamento")
        
        # Botão para linha manual
        if st.button("➕ Adicionar Item Manual"):
            nova = pd.DataFrame([{'ITEM': '', 'DESCRIÇÃO': 'Novo Item', 'UND': 'und', 'QDT': 1.0, 'Custo Mat. Unit.': 0.0, 'Mão de Obra Unit.': 0.0}])
            df_final = pd.concat([df_final, nova], ignore_index=True)

        df_editavel = st.data_editor(
            df_final,
            num_rows="dynamic",
            column_config={
                "Custo Mat. Unit.": st.column_config.NumberColumn("Mat. Unit. (R$)", format="R$ %.2f"),
                "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. Unit. (R$)", format="R$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # --- 6. CÁLCULOS E EXPORTAÇÃO ---
        mo_com_enc = df_editavel['Mão de Obra Unit.'] * (1 + perc_encargos/100)
        custo_direto = df_editavel['Custo Mat. Unit.'] + mo_com_enc
        venda_unit = custo_direto / divisor
        total_item = venda_unit * df_editavel['QDT']

        st.markdown("---")
        st.metric("VALOR TOTAL DA PROPOSTA", f"R$ {(total_item.sum() + frete_fixo):,.2f}")

        # Botão para baixar
        df_export = df_editavel.copy()
        df_export['Venda Unitário'] = venda_unit
        df_export['Total Item'] = total_item
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False)
        
        st.download_button("💾 Baixar Orçamento Final", data=output.getvalue(), file_name="Proposta_Final.xlsx")

    except Exception as e:
        st.error(f"Erro ao cruzar arquivos: {e}. Certifique-se de que o listão tem a aba 'MP'.")
else:
    st.warning("Aguardando o upload de ambos os arquivos para liberar o orçamento.")
