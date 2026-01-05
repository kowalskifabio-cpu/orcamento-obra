import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Total", layout="wide")

st.title("🏗️ Orçamentador: Espelhamento Completo")

# --- 1. ÁREA DE UPLOAD ---
st.subheader("📁 1. Carregar Ficheiros")
col_up1, col_up2 = st.columns(2)

with col_up1:
    arq_obra = st.file_uploader("Planilha da CONSTRUTORA", type=["xlsx", "csv"], key="obra")

with col_up2:
    arq_lista = st.file_uploader("Seu LISTÃO (Listão.xlsx)", type=["xlsx", "csv"], key="lista")

# --- 2. CONFIGURAÇÕES (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Financeiro")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)
    frete_fixo = st.number_input("Frete Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 3. PROCESSAMENTO ---
if arq_obra and arq_lista:
    try:
        # Lendo a Obra sem filtros rígidos (pula as 7 de cabeçalho)
        if arq_obra.name.endswith('.csv'):
            df_obra = pd.read_csv(arq_obra, skiprows=7)
        else:
            df_obra = pd.read_excel(arq_obra, skiprows=7)
        
        # Lendo o Listão
        if arq_lista.name.endswith('.csv'):
            df_base = pd.read_csv(arq_lista)
        else:
            try:
                df_base = pd.read_excel(arq_lista, sheet_name='MP')
            except:
                df_base = pd.read_excel(arq_lista)
        
        # Remove colunas totalmente sem nome (comuns em Excel sujo)
        df_obra = df_obra.loc[:, ~df_obra.columns.str.contains('^Unnamed')]

        # ADICIONA COLUNAS DE TRABALHO (Se não existirem)
        for col in ['Custo Material Unit.', 'Mão de Obra Unit.']:
            if col not in df_obra.columns:
                df_obra[col] = 0.0

        st.success(f"✅ Planilha da construtora carregada com {len(df_obra)} linhas.")

        # --- 4. BUSCADOR ---
        with st.expander("🔍 CONSULTAR PREÇOS NO LISTÃO"):
            termo = st.text_input("Pesquise no seu Listão (Ex: MDF, Inox, Cuba):")
            if termo:
                mask = df_base.astype(str).apply(lambda x: x.str.contains(termo, case=False)).any(axis=1)
                st.dataframe(df_base[mask], use_container_width=True)

        # --- 5. TABELA DE ORÇAMENTO ---
        st.subheader("📝 Edição do Orçamento")
        
        # O data_editor agora mostra TUDO o que veio no Excel
        df_editavel = st.data_editor(
            df_obra,
            num_rows="dynamic",
            column_config={
                "Custo Material Unit.": st.column_config.NumberColumn("Custo Mat. (R$)", format="R$ %.2f"),
                "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. (R$)", format="R$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # --- 6. CÁLCULOS ---
        # Tenta achar a coluna de quantidade (pode ser QDT, Qtd, Quantidade...)
        col_qtd = next((c for c in df_editavel.columns if 'QDT' in c.upper() or 'QTD' in c.upper()), None)
        
        if col_qtd:
            qtd_num = pd.to_numeric(df_editavel[col_qtd], errors='coerce').fillna(0)
            mo_enc = df_editavel['Mão de Obra Unit.'] * (1 + perc_encargos/100)
            custo_direto = df_editavel['Custo Material Unit.'] + mo_enc
            venda_unit = custo_direto / divisor
            total_item = venda_unit * qtd_num
            total_obra = total_item.sum() + frete_fixo

            st.markdown("---")
            st.metric("VALOR TOTAL DA PROPOSTA", f"R$ {total_obra:,.2f}")

            # Exportação
            df_export = df_editavel.copy()
            df_export['VENDA UNITÁRIO'] = venda_unit
            df_export['TOTAL DO ITEM'] = total_item
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("💾 Baixar Orçamento Completo", data=output.getvalue(), file_name="Orcamento_Final.xlsx")
        else:
            st.warning("⚠️ Não encontrei uma coluna de quantidade (QDT). Os cálculos totais não podem ser feitos, mas você pode editar os preços.")

    except Exception as e:
        st.error(f"Erro técnico ao processar: {e}")
else:
    st.warning("Aguardando os ficheiros da CONSTRUTORA e o seu LISTÃO...")
