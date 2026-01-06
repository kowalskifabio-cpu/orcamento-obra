import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. LOGO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    st.sidebar.image(Image.open(nome_logo), use_container_width=True)

# --- MEMÓRIA DE DADOS ---
if 'df_obra' not in st.session_state:
    st.session_state.df_obra = None
if 'cpus' not in st.session_state:
    st.session_state.cpus = {} 

# --- 2. MODAL DE COMPOSIÇÃO TÉCNICA ---
@st.dialog("Detalhamento da Composição (CPU)", width="large")
def abrir_cpu(idx, dados_linha):
    # Traz a Descrição e as Observações originais da planilha
    desc_original = str(dados_linha.iloc[1]) # Coluna B
    obs_original = str(dados_linha.get('OBSERVAÇÕES', ''))
    
    st.write(f"### 📋 Item: {desc_original}")
    st.markdown(f"**Observações da Construtora:** {obs_original}")
    
    # Inicializa CPU se vazio
    if idx not in st.session_state.cpus:
        st.session_state.cpus[idx] = pd.DataFrame(columns=[
            "Tipo", "Insumo/Material", "Unid", "Qtd", "Preço Unit. (MP)", "Observações Técnicas", "Subtotal"
        ])

    df_atual = st.session_state.cpus[idx]

    with st.container(border=True):
        st.write("#### 🛠️ Composição Técnica de Insumos")
        
        # TABELA EDITÁVEL COM OBSERVAÇÕES
        df_editado = st.data_editor(
            df_atual,
            num_rows="dynamic",
            column_config={
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Material", "Mão de Obra", "Terceirizado", "Ferragem"]),
                "Preço Unit. (MP)": st.column_config.NumberColumn("Custo Unit. (R$)", format="R$ %.2f"),
                "Observações Técnicas": st.column_config.TextColumn("Observações (Detalhes do Insumo)", width="large"),
                "Subtotal": st.column_config.NumberColumn("Subtotal", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"cpu_editor_{idx}"
        )

        # Cálculo de Totais
        if not df_editado.empty:
            df_editado["Subtotal"] = df_editado["Qtd"].fillna(0) * df_editado["Preço Unit. (MP)"].fillna(0)
            total_direto = df_editado["Subtotal"].sum()
        else:
            total_direto = 0.0

        st.divider()
        st.metric("Custo Direto Total", f"R$ {total_direto:,.2f}")
        
        if st.button("✅ Salvar Composição e Atualizar Planilha"):
            st.session_state.cpus[idx] = df_editado
            st.session_state.df_obra.at[idx, 'Custo Unitário Final'] = total_direto
            st.session_state.df_obra.at[idx, 'Status'] = "✅"
            st.rerun()

# --- 3. INTERFACE DE UPLOAD ---
st.title("🏗️ Orçamentador Marcenaria & Mármore")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_obra is None:
        # Lê a planilha e garante que traz todas as colunas (incluindo Observações)
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.insert(0, 'Status', '⭕')
        df['Custo Unitário Final'] = 0.0
        st.session_state.df_obra = df
    
    st.write("### Itens para Orçar")
    # Tabela principal com barra de rolagem
    selecao = st.dataframe(
        st.session_state.df_obra,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(selecao.selection.rows) > 0:
        idx_sel = selecao.selection.rows[0]
        row_sel = st.session_state.df_obra.iloc[idx_sel]
        
        # Botão para detalhar
        if st.button(f"🔎 Detalhar Composição: {row_sel.iloc[2]}", type="primary"):
            abrir_cpu(idx_sel, row_sel)
else:
    st.session_state.df_obra = None
    st.info("Aguardando os arquivos para gerar a composição...")
