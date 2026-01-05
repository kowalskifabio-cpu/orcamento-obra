import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Inteligente", layout="wide")

# --- 1. CARREGAMENTO DA BASE DE DADOS (ABA MP) ---
@st.cache_data # Isso faz o site carregar a base apenas uma vez para ser rápido
def carregar_base_mp():
    try:
        # Tenta ler o arquivo modelo que você já tem
        caminho_modelo = "000-2025_MODELO.REV00.xlsm"
        df_mp = pd.read_excel(caminho_modelo, sheet_name='MP')
        # Limpa espaços em branco nos nomes das colunas
        df_mp.columns = df_mp.columns.str.strip()
        return df_mp
    except:
        return None

base_precos = carregar_base_mp()

st.title("🏗️ Orçamentador com Base de Dados MP")

# --- 2. CONFIGURAÇÕES FINANCEIRAS (SIDEBAR) ---
with st.sidebar:
    st.header("Configurações Globais")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro/BDI (%)", value=20.0)
    frete_fixo = st.number_input("Frete/Logística Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- 3. GESTÃO DE DADOS ---
if 'dados_orcamento' not in st.session_state:
    st.session_state.dados_orcamento = None

# --- 4. IMPORTAÇÃO DA PLANILHA DA CONSTRUTORA ---
st.subheader("1. Importar Planilha da Construtora")
arquivo_subido = st.file_uploader("Arraste o arquivo aqui", type=["xlsx", "csv"])

if arquivo_subido is not None and st.session_state.dados_orcamento is None:
    try:
        df_ini = pd.read_csv(arquivo_subido, skiprows=7) if arquivo_subido.name.endswith('.csv') else pd.read_excel(arquivo_subido, skiprows=7)
        colunas_alvo = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT']
        colunas_existentes = [c for c in colunas_alvo if c in df_ini.columns]
        df_ini = df_ini[colunas_existentes].copy()
        df_ini = df_ini.dropna(subset=['DESCRIÇÃO'])
        
        # Inicia colunas de custo zeradas
        df_ini['Custo Mat. Unit.'] = 0.0
        df_ini['Mão de Obra Unit.'] = 0.0
        st.session_state.dados_orcamento = df_ini
    except Exception as e:
        st.error(f"Erro na importação: {e}")

# --- 5. TABELA DE ORÇAMENTO ---
if st.session_state.dados_orcamento is not None:
    
    st.subheader("2. Planilha de Orçamento")
    
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("➕ Nova Linha"):
            nova_linha = pd.DataFrame([{'ITEM': '', 'DESCRIÇÃO': 'Novo Item', 'UND': 'und', 'QDT': 1.0, 'Custo Mat. Unit.': 0.0, 'Mão de Obra Unit.': 0.0}])
            st.session_state.dados_orcamento = pd.concat([st.session_state.dados_orcamento, nova_linha], ignore_index=True)
            st.rerun()

    # Mostra um aviso se a base MP foi carregada
    if base_precos is not None:
        st.success(f"Base de Dados MP carregada com sucesso! ({len(base_precos)} materiais encontrados)")
    else:
        st.warning("Aba 'MP' não encontrada no arquivo modelo. Preencha os custos manualmente.")

    # TABELA EDITÁVEL TOTAL
    df_editado = st.data_editor(
        st.session_state.dados_orcamento,
        num_rows="dynamic",
        column_config={
            "Custo Mat. Unit.": st.column_config.NumberColumn("Material (R$)", format="R$ %.2f"),
            "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. (R$)", format="R$ %.2f"),
            "QDT": st.column_config.NumberColumn("Qtd", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True,
    )
    st.session_state.dados_orcamento = df_editado

    # --- 6. LÓGICA DE CÁLCULO FINAL ---
    mo_com_enc = df_editado['Mão de Obra Unit.'] * (1 + perc_encargos/100)
    custo_direto_unit = df_editado['Custo Mat. Unit.'] + mo_com_enc
    
    # Preço Unitário com Impostos e Lucro
    df_editado['Preço Final Unit.'] = custo_direto_unit / divisor
    df_editado['Total Item'] = df_editado['Preço Final Unit.'] * df_editado['QDT']

    total_proposta = df_editado['Total Item'].sum() + frete_fixo

    st.markdown("---")
    st.metric("VALOR TOTAL DA PROPOSTA", f"R$ {total_proposta:,.2f}")

    # Exportação
    def para_excel(df):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return out.getvalue()

    st.download_button("📥 Baixar Orçamento Finalizado", data=para_excel(df_editado), file_name="Orcamento_Final.xlsx"))
