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

# --- 2. JANELA DE EDIÇÃO (MODAL) ---
@st.dialog("Composição de Preço")
def abrir_modal(index, linha, df_mp):
    # Identifica a descrição (geralmente coluna 1 ou 2)
    desc_original = str(linha.iloc[1]) if len(linha) > 1 else "Item sem descrição"
    
    st.write(f"### 🛠️ Item: {desc_original}")
    
    # BUSCA NAS COLUNAS DA MP VALORES
    preco_base = 0.0
    if df_mp is not None:
        # Busca por nome
        match = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(desc_original, case=False, na=False)).any(axis=1)]
        if not match.empty:
            cols_alvo = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "PREÇO", "NOME PRODUTO"]
            for c in cols_alvo:
                if c in match.columns:
                    preco_base = float(pd.to_numeric(match[c].iloc[0], errors='coerce') or 0.0)
                    if preco_base > 0:
                        st.success(f"Valor sugerido na MP: R$ {preco_base:.2f}")
                        break

    with st.form("calculo_item"):
        c1, c2 = st.columns([3, 1])
        nova_desc = c1.text_input("Descrição Proposta", value=desc_original)
        qtd = c2.number_input("Quantidade", value=1.0)
        
        st.divider()
        st.write("#### Custos Unitários")
        f1, f2 = st.columns(2)
        v_mat = f1.number_input("Custo Material (R$)", value=preco_base)
        v_mo = f2.number_input("Custo Mão de Obra (R$)", value=0.0)
        
        st.info("Aqui entraremos com as fórmulas que você vai enviar.")
        
        if st.form_submit_button("Salvar Detalhamento"):
            st.session_state.respostas[index] = {
                "Desc": nova_desc,
                "Total": (v_mat + v_mo) * qtd,
                "Status": "✅"
            }
            st.rerun()

# --- 3. UPLOAD ---
st.title("🏗️ Orçamentador Universal")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

# --- 4. EXIBIÇÃO ---
if arq_obra and arq_mp:
    try:
        df_obra = pd.read_excel(arq_obra, skiprows=7).dropna(how='all')
        
        # Lê MP Valores
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        df_mp = pd.concat(dict_mp.values(), ignore_index=True)

        # Barra de ferramentas superior
        st.markdown("---")
        col_sel, col_stat = st.columns([3, 1])
        
        with col_sel:
            # Seletor para abrir o Modal
            item_selecionado = st.selectbox(
                "🎯 Escolha o item da planilha abaixo para detalhar:",
                options=df_obra.index,
                format_func=lambda x: f"Linha {x+8}: {str(df_obra.iloc[x].iloc[1])[:60]}..."
            )
            if st.button("📝 Abrir Detalhamento do Item"):
                abrir_modal(item_selecionado, df_obra.loc[item_selecionado], df_mp)
        
        with col_stat:
            st.metric("Itens Concluídos", f"{len(st.session_state.respostas)} / {len(df_obra)}")

        # Exibição da Planilha Completa (Com barra de rolagem nativa)
        st.write("### Visualização da Planilha Original")
        st.dataframe(df_obra, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
else:
    st.warning("Aguardando os arquivos para começar...")
