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
        st.caption("Próximas fórmulas automáticas serão configuradas aqui.")

        if st.form_submit_button("Concluir e Salvar"):
            st.session_state.respostas[index] = {
                "Concluído": "✅",
                "Desc": nova_desc,
                "Venda": (val_mat + val_mo) * 1.2 # Exemplo de markup
            }
            st.rerun()

# --- 3. UPLOAD ---
st.title("🏗️ Orçamentador Universal")
col_u1, col_u2 = st.columns(2)
with col_u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with col_up2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

# --- 4. EXIBIÇÃO ---
if arq_obra and arq_mp:
    try:
        # Lemos a obra por completo
        df_obra = pd.read_excel(arq_obra, skiprows=7) if arq_obra.name.endswith('.xlsx') else pd.read_csv(arq_obra, skiprows=7)
        
        # Lemos a MP
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        df_mp = pd.concat(dict_mp.values(), ignore_index=True)

        st.markdown("---")
        st.subheader("Planilha da Construtora")
        st.caption("Role para os lados para ver todas as colunas. Clique em 'Editar' para abrir o pop-up.")

        # Criamos a área de scroll
        for i, row in df_obra.iterrows():
            status = st.session_state.respostas.get(i, {}).get("Concluído", "⭕")
            
            # Layout de linha horizontal larga
            with st.container(border=True):
                # Primeira coluna com botão e status, as demais são os dados do Excel
                cols = st.columns([0.5, 1] + [2] * (len(df_obra.columns) - 1))
                cols[0].write(status)
                if cols[1].button("Editar", key=f"ed_{i}"):
                    abrir_modal_edicao(i, row, df_mp)
                
                # Preenche o resto da linha com as colunas originais
                for idx, valor in enumerate(row):
                    if idx < len(cols) - 2: # Limite para não estourar as colunas criadas
                        cols[idx+2].write(f"{valor}" if pd.notnull(valor) else "")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.warning("Suba os arquivos para ver a planilha completa.")
