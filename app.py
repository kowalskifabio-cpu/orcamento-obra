import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

st.set_page_config(page_title="Orçamentador Flexível", layout="wide")

# --- 1. LOGO E ESTILO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    st.sidebar.image(Image.open(nome_logo), use_container_width=True)

# Memória para os itens já orçados
if 'respostas' not in st.session_state:
    st.session_state.respostas = {}

# --- 2. JANELA DE EDIÇÃO (MODAL) ---
@st.dialog("Composição de Preço do Item")
def abrir_modal_edicao(index, dados_linha, df_mp):
    st.write(f"### Detalhando Item")
    
    # Identifica a descrição para busca (Geralmente na Coluna B ou similar)
    # Como não há padrão, pegamos o valor da segunda coluna preenchida
    desc_busca = str(dados_linha.iloc[1]) if len(dados_linha) > 1 else ""
    
    st.info(f"**Descrição original:** {desc_busca}")
    
    # BUSCA NAS COLUNAS ESPECÍFICAS DA MP VALORES
    preco_base = 0.0
    if df_mp is not None:
        # Busca o termo no listão
        match = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(desc_busca, case=False, na=False)).any(axis=1)]
        if not match.empty:
            cols_alvo = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "PREÇO", "NOME PRODUTO"]
            for c in cols_alvo:
                if c in match.columns:
                    preco_base = float(pd.to_numeric(match[c].iloc[0], errors='coerce') or 0.0)
                    if preco_base > 0:
                        st.success(f"Valor sugerido (MP): R$ {preco_base:.2f}")
                        break

    # FORMULÁRIO 100% EDITÁVEL
    with st.form("form_calculo"):
        st.write("#### Dados de Entrada")
        c1, c2, c3 = st.columns([3, 1, 1])
        nova_desc = c1.text_input("Descrição Proposta", value=desc_busca)
        unid = c2.text_input("Unidade", value="un")
        # Tenta achar quantidade na linha
        qtd_ini = float(pd.to_numeric(dados_linha.get('QDT', 1), errors='coerce') or 1.0)
        qtd = c3.number_input("Quantidade", value=qtd_ini)

        st.divider()
        st.write("#### Fórmulas e Custos")
        f1, f2 = st.columns(2)
        val_mat = f1.number_input("Valor Unitário Material (R$)", value=preco_base, format="%.2f")
        val_mo = f2.number_input("Valor Unitário Mão de Obra (R$)", value=0.0, format="%.2f")
        
        # Próximas regras entrarão aqui
        st.caption("Próximas fórmulas
