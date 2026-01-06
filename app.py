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

if 'respostas' not in st.session_state:
    st.session_state.respostas = {}

# --- 2. MODAL DE EDIÇÃO ---
@st.dialog("Detalhamento Técnica")
def modal_edicao(idx, row, df_mp):
    # Pega descrição (geralmente 2ª coluna)
    desc = str(row.iloc[1]) if len(row) > 1 else "Item"
    st.write(f"### 🛠️ {desc}")
    
    # Busca na MP Valores
    p_sugerido = 0.0
    if df_mp is not None:
        # Busca nas colunas solicitadas
        cols_mp = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "NOME PRODUTO", "PREÇO"]
        match = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(desc, case=False, na=False)).any(axis=1)]
        if not match.empty:
            for c in cols_mp:
                if c in match.columns:
                    p_sugerido = float(pd.to_numeric(match[c].iloc[0], errors='coerce') or 0.0)
                    if p_sugerido > 0: break

    with st.form("form_item"):
        c1, c2 = st.columns(2)
        v_mat = c1.number_input("Custo Material (R$)", value=p_sugerido)
        v_mo = c2.number_input("Custo Mão de Obra (R$)", value=0.0)
        
        st.write("---")
        st.caption("Fórmulas automáticas serão inseridas aqui no próximo passo.")
        
        if st.form_submit_button("Salvar e Fechar"):
            st.session_state.respostas[idx] = {"Status": "✅", "Valor": v_mat + v_mo}
            st.rerun()

# --- 3. UPLOAD ---
st.title("🏗️ Orçamentador Estável")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

# --- 4. EXIBIÇÃO ---
if arq_obra and arq_mp:
    try:
        # Lê a obra sem filtros para não perder dados
        df = pd.read_excel(arq_obra, skiprows=7) if arq_obra.name.endswith('.xlsx') else pd.read_csv(arq_obra, skiprows=7)
        
        # Lê MP
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        df_mp = pd.concat(dict_mp.values(), ignore_index=True)

        # PAGINAÇÃO
        linhas_por_pagina = 50
        total_paginas = (len(df) // linhas_por_pagina) + 1
        pag = st.sidebar.number_input("Página", min_value=1, max_value=total_paginas, step=1)
        inicio = (pag - 1) * linhas_por_pagina
        fim = inicio + linhas_por_pagina

        st.write(f"Mostrando linhas {inicio} a {fim} de {len(df)}")
        
        # Tabela de visualização rápida
        for i in range(inicio, min(fim, len(df))):
            row = df.iloc[i]
            status = st.session_state.respostas.get(i, {}).get("Status", "⭕")
            
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([0.5, 1, 6, 1])
                c1.write(status)
                c2.write(f"Linh. {i+8}") # Indica a linha real do Excel
                c3.write(str(row.iloc[1]) if pd.notnull(row.iloc[1]) else "---")
                if c4.button("Editar", key=f"btn_{i}"):
                    modal_edicao(i, row, df_mp)

    except Exception as e:
        st.error(f"Erro: {e}")
else:
    st.info("Aguardando arquivos...")
