import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

# 1. Configuração inicial
st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- EXIBIÇÃO DA LOGO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    logo = Image.open(nome_logo)
    st.sidebar.image(logo, use_container_width=True)
else:
    st.sidebar.warning("Logo não encontrada no GitHub.")

st.title("🏗️ Sistema de Orçamento Profissional")
st.markdown("---")

# --- 2. ÁREA DE UPLOAD (Nomes atualizados) ---
st.subheader("📁 1. Carregar Ficheiros")
col_up1, col_up2 = st.columns(2)

with col_up1:
    arq_obra = st.file_uploader("Planilha da CONSTRUTORA", type=["xlsx", "csv"])

with col_up2:
    # Substituído conforme solicitado
    arq_lista = st.file_uploader("MP Valores", type=["xlsx", "csv"])

# --- 3. CONFIGURAÇÕES (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Parâmetros Financeiros")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)
    frete_fixo = st.number_input("Frete Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 4. PROCESSAMENTO ---
if arq_obra and arq_lista:
    try:
        # Lendo a Obra (pula 7 linhas)
        if arq_obra.name.endswith('.csv'):
            df_obra = pd.read_csv(arq_obra, skiprows=7)
        else:
            df_obra = pd.read_excel(arq_obra, skiprows=7)
        
        # Garante que a primeira coluna (ITEM) seja lida e mantida
        df_obra.columns = [c if not str(c).startswith('Unnamed') else f'C_{i}' for i, c in enumerate(df_obra.columns)]

        # Lendo o ficheiro MP Valores
        if arq_lista.name.endswith('.csv'):
            df_base = pd.read_csv(arq_lista)
        else:
            try:
                df_base = pd.read_excel(arq_lista, sheet_name='MP')
            except:
                df_base = pd.read_excel(arq_lista)
        
        # Adiciona colunas de trabalho
        if 'Custo Mat. Unit.' not in df_obra.columns:
            df_obra['Custo Mat. Unit.'] = 0.0
        if 'Mão de Obra Unit.' not in df_obra.columns:
            df_obra['Mão de Obra Unit.'] = 0.0

        st.success(f"✅ Arquivos carregados! Base 'MP Valores' com {len(df_base)} itens.")

        # --- 5. BUSCADOR MP VALORES ---
        with st.expander("🔍 CONSULTAR PREÇOS: MP Valores"):
            termo = st.text_input("Pesquise um material (Ex: MDF, Granito, Puxador):")
            if termo:
                mask = df_base.astype(str).apply(lambda x: x.str.contains(termo, case=False)).any(axis=1)
                st.dataframe(df_base[mask], use_container_width=True)

        # --- 6. TABELA DE ORÇAMENTO ---
        st.subheader("📝 Edição do Orçamento")
        
        df_editavel = st.data_editor(
            df_obra,
            num_rows="dynamic",
            column_config={
                "Custo Mat. Unit.": st.column_config.NumberColumn("Custo Mat. (R$)", format="R$ %.2f"),
                "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. (R$)", format="R$ %.2f"),
            },
            use_container_width=True,
            hide_index=True
        )

        # --- 7. CÁLCULOS ---
        col_qtd = next((c for c in df_editavel.columns if 'QDT' in str(c).upper() or 'QTD' in str(c).upper()), None)
        
        if col_qtd:
            qtd_num = pd.to_numeric(df_editavel[col_qtd], errors='coerce').fillna(0)
            mo_enc = df_editavel['Mão de Obra Unit.'] * (1 + perc_encargos/100)
            custo_direto = df_editavel['Custo Mat. Unit.'] + mo_enc
            venda_unit = custo_direto / divisor
            total_item = venda_unit * qtd_num
            total_obra = total_item.sum() + frete_fixo

            st.markdown("---")
            st.metric("VALOR TOTAL DA PROPOSTA", f"R$ {total_obra:,.2f}")

            # Exportação
            df_export = df_editavel.copy()
            df_export['Venda Unitário'] = venda_unit
            df_export['Total Item'] = total_item
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("💾 Baixar Orçamento (MP Valores)", data=output.getvalue(), file_name="Orcamento_MP_Final.xlsx")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.warning("⚠️ Aguardando a planilha da CONSTRUTORA e o ficheiro MP Valores.")
