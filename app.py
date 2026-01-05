import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Inteligente", layout="wide")

# --- 1. CARREGAMENTO DA BASE MP (LISTÃO) ---
@st.cache_data
def carregar_base_mp():
    try:
        # Tenta carregar o arquivo modelo que você subiu no GitHub
        df_mp = pd.read_excel("000-2025_MODELO.REV00.xlsm", sheet_name='MP')
        return df_mp
    except:
        return None

base_mp = carregar_base_mp()

st.title("🏗️ Orçamentador: Cruzamento de Dados (Construtora x Listão)")

# --- 2. SIDEBAR FINANCEIRO ---
with st.sidebar:
    st.header("Configurações de Impostos/BDI")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)
    frete_total = st.number_input("Frete (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 3. IMPORTAÇÃO DO ARQUIVO DA CONSTRUTORA ---
if 'dados' not in st.session_state:
    st.session_state.dados = None

st.subheader("1. Importar Arquivo da Construtora")
arq = st.file_uploader("Suba a planilha da obra", type=["xlsx", "csv"])

if arq and st.session_state.dados is None:
    df_ini = pd.read_csv(arq, skiprows=7) if arq.name.endswith('.csv') else pd.read_excel(arq, skiprows=7)
    cols = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'UND', 'QDT']
    df_ini = df_ini[[c for c in cols if c in df_ini.columns]].copy()
    df_ini['Custo Material Unit.'] = 0.0
    df_ini['Mão de Obra Unit.'] = 0.0
    st.session_state.dados = df_ini

# --- 4. CRUZAMENTO E TABELA ---
if st.session_state.dados is not None:
    st.subheader("2. Cruzamento de Itens e Precificação")
    
    # Se a base MP existir, mostra um buscador para te ajudar
    if base_mp is not None:
        with st.expander("🔍 Consultar Preços no Listão (Aba MP)"):
            busca = st.text_input("Digite o nome do material para ver o preço no listão:")
            if busca:
                # Procura no listão (ajuste o nome da coluna se for diferente de 'DESCRIÇÃO' ou 'MATERIAL')
                resultado = base_mp[base_mp.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)]
                st.dataframe(resultado)

    # Tabela principal editável
    df_editado = st.data_editor(
        st.session_state.dados,
        num_rows="dynamic",
        column_config={
            "Custo Material Unit.": st.column_config.NumberColumn("Material (R$)", format="R$ %.2f"),
            "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. (R$)", format="R$ %.2f"),
        },
        use_container_width=True,
        hide_index=True
    )
    st.session_state.dados = df_editado

    # --- 5. CÁLCULOS FINAIS ---
    mo_enc = df_editado['Mão de Obra Unit.'] * (1 + perc_encargos/100)
    custo_direto = df_editado['Custo Material Unit.'] + mo_enc
    precos_venda = custo_direto / divisor
    totais = precos_venda * df_editado['QDT']

    st.markdown("---")
    res1, res2 = st.columns(2)
    res1.metric("Custo de Execução", f"R$ {(df_editado['Custo Material Unit.'].sum() + mo_enc.sum()):,.2f}")
    res2.metric("VALOR DA PROPOSTA", f"R$ {(totais.sum() + frete_total):,.2f}")

    # Exportar
    df_final = df_editado.copy()
    df_final['PREÇO VENDA UNIT.'] = precos_venda
    df_final['TOTAL ITEM'] = totais
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    
    st.download_button("💾 Baixar Orçamento Cruzado", data=output.getvalue(), file_name="Orcamento_Final.xlsx")
