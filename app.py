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

# Memória de cálculos
if 'df_trabalho' not in st.session_state:
    st.session_state.df_trabalho = None
if 'df_mp' not in st.session_state:
    st.session_state.df_mp = None

# --- 2. JANELA DE DETALHAMENTO (MODAL) ---
@st.dialog("Composição de Preço")
def abrir_detalhe(index):
    df = st.session_state.df_trabalho
    linha = df.loc[index]
    desc = str(linha.iloc[1])
    
    st.write(f"### 🛠️ Item: {desc}")
    
    # Busca automática no MP Valores
    p_sugerido = 0.0
    if st.session_state.df_mp is not None:
        base = st.session_state.df_mp
        # Busca nas 3 colunas específicas que você pediu
        match = base[base.astype(str).apply(lambda x: x.str.contains(desc, case=False, na=False)).any(axis=1)]
        if not match.empty:
            for c in ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "PREÇO"]:
                if c in match.columns:
                    p_sugerido = float(pd.to_numeric(match[c].iloc[0], errors='coerce') or 0.0)
                    if p_sugerido > 0: break
    
    with st.form("f_detalhe"):
        c1, c2 = st.columns(2)
        v_mat = c1.number_input("Custo Material (R$)", value=p_sugerido, format="%.2f")
        v_mo = c2.number_input("Custo Mão de Obra (R$)", value=0.0, format="%.2f")
        
        st.divider()
        st.info("As fórmulas enviadas serão aplicadas aqui.")
        
        if st.form_submit_button("Salvar e Atualizar Planilha"):
            # Atualiza a planilha principal com os dados do modal
            st.session_state.df_trabalho.at[index, 'Custo Mat.'] = v_mat
            st.session_state.df_trabalho.at[index, 'Custo M.O.'] = v_mo
            st.session_state.df_trabalho.at[index, 'STATUS'] = "✅"
            st.rerun()

# --- 3. UPLOAD ---
st.title("🏗️ Orçamentador Universal")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

# --- 4. PROCESSAMENTO ---
if arq_obra and arq_mp:
    # Carrega dados se ainda não estiverem na memória
    if st.session_state.df_trabalho is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all')
        df.insert(0, 'STATUS', '⭕')
        df['Custo Mat.'] = 0.0
        df['Custo M.O.'] = 0.0
        st.session_state.df_trabalho = df
        
        # Carrega MP
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        st.session_state.df_mp = pd.concat(dict_mp.values(), ignore_index=True)

    # Exibição
    st.write("### Planilha de Orçamento")
    st.caption("Selecione uma linha na bolinha à esquerda e clique em 'Detalhar Item' para abrir a caixa.")
    
    # Tabela principal (Como no início)
    selecao = st.dataframe(
        st.session_state.df_trabalho,
        use_container_width=True,
        hide_index=False,
        on_select="rerun",
        selection_mode="single-row"
    )

    # Verifica se algo foi selecionado para abrir o botão de Detalhar
    if len(selecao.selection.rows) > 0:
        idx_sel = selecao.selection.rows[0]
        if st.button(f"🔎 Detalhar Item Selecionado (Linha {idx_sel + 8})", type="primary"):
            abrir_detalhe(idx_sel)

    # Exportação
    st.divider()
    if st.button("💾 Gerar Arquivo Excel Final"):
        out = BytesIO()
        st.session_state.df_trabalho.to_excel(out, index=False)
        st.download_button("Clique aqui para baixar", data=out.getvalue(), file_name="Orcamento_Final.xlsx")

else:
    st.info("Aguardando os dois arquivos...")
    st.session_state.df_trabalho = None
