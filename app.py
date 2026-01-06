import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- LOGO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    st.sidebar.image(Image.open(nome_logo), use_container_width=True)

# --- MEMÓRIA DE DADOS ---
if 'df_obra' not in st.session_state:
    st.session_state.df_obra = None
if 'cpus' not in st.session_state:
    st.session_state.cpus = {} # Guarda a composição de cada linha

# --- FUNÇÃO DE CÁLCULO DA CPU (Baseado nas linhas 240-294) ---
@st.dialog("Detalhamento da Composição (CPU)", width="large")
def abrir_cpu(idx, descricao_item):
    st.write(f"### 🛠️ Composição Técnica: {descricao_item}")
    
    # Se não existe composição para esta linha, cria uma vazia com a estrutura da aba "Base"
    if idx not in st.session_state.cpus:
        st.session_state.cpus[idx] = pd.DataFrame(columns=[
            "Tipo", "Descrição Insumo", "Unid", "Consumo/Qtd", "Preço Unit. (MP)", "Subtotal"
        ])

    df_atual = st.session_state.cpus[idx]

    # Interface de edição da CPU
    with st.container(border=True):
        st.write("**Insumos e Serviços para este item:**")
        
        # Editor de tabela para os insumos
        df_editado = st.data_editor(
            df_atual,
            num_rows="dynamic", # PERMITE INCLUIR E EXCLUIR LINHAS MANUALMENTE
            column_config={
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Material", "Mão de Obra", "Terceirizado", "Ferragem"]),
                "Preço Unit. (MP)": st.column_config.NumberColumn("Custo Unit. (R$)", format="R$ %.2f"),
                "Subtotal": st.column_config.NumberColumn("Subtotal", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"cpu_editor_{idx}"
        )

        # Cálculo automático do Subtotal por linha e Total Geral
        if not df_editado.empty:
            df_editado["Subtotal"] = df_editado["Consumo/Qtd"].fillna(0) * df_editado["Preço Unit. (MP)"].fillna(0)
            total_custo_direto = df_editado["Subtotal"].sum()
        else:
            total_custo_direto = 0.0

        st.divider()
        col_res1, col_res2 = st.columns(2)
        col_res1.metric("Custo Direto Total", f"R$ {total_custo_direto:,.2f}")
        
        if st.button("💾 Salvar Composição e Fechar"):
            st.session_state.cpus[idx] = df_editado
            # Atualiza a planilha principal com o custo calculado
            st.session_state.df_obra.at[idx, 'Custo Unitário Final'] = total_custo_direto
            st.session_state.df_obra.at[idx, 'Status'] = "✅"
            st.rerun()

# --- INTERFACE PRINCIPAL ---
st.title("🏗️ Sistema de Orçamento - Marcenaria & Mármore")

u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_obra is None:
        # Lê a planilha da construtora
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.insert(0, 'Status', '⭕')
        df['Custo Unitário Final'] = 0.0
        st.session_state.df_obra = df
    
    st.write("### Itens da Obra")
    st.caption("Clique em uma linha para detalhar a composição de materiais e serviços.")

    # Exibição da planilha para seleção
    tabela_obra = st.dataframe(
        st.session_state.df_obra,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=False
    )

    # Lógica para abrir o detalhamento se houver seleção
    if len(tabela_obra.selection.rows) > 0:
        idx_selecionado = tabela_obra.selection.rows[0]
        row_data = st.session_state.df_obra.iloc[idx_selecionado]
        
        # Botão flutuante para abrir o detalhamento
        if st.button(f"🔎 Detalhar: {row_data.iloc[2]}", type="primary"):
            abrir_cpu(idx_selecionado, row_data.iloc[2])

else:
    st.session_state.df_obra = None
    st.info("Por favor, carregue os arquivos para iniciar a orçamentação.")
