import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. LOGO E MEMÓRIA ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    st.sidebar.image(Image.open(nome_logo), use_container_width=True)

if 'respostas' not in st.session_state:
    st.session_state.respostas = {}

# --- 2. UPLOAD ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with col_up2:
    arq_mp = st.file_uploader("2. MP Valores", type=["xlsx", "csv"])

# --- 3. DEFINIÇÃO DA JANELA DE EDIÇÃO (MODAL) ---
@st.dialog("Detalhamento do Item")
def abrir_edicao(index, linha, df_mp):
    st.write(f"### 🛠️ Editando: {linha['DESCRIÇÃO']}")
    
    # Busca automática na MP
    preco_sugerido = 0.0
    cols_busca = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "NOME PRODUTO", "PREÇO"]
    
    # Busca no listão pelo nome exato ou contido
    if df_mp is not None:
        match = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(str(linha['DESCRIÇÃO']), case=False, na=False)).any(axis=1)]
        if not match.empty:
            for c in cols_busca:
                if c in match.columns:
                    preco_sugerido = float(pd.to_numeric(match[c].iloc[0], errors='coerce') or 0.0)
                    if preco_sugerido > 0: break

    # Campos do Formulário
    nova_desc = st.text_input("Descrição para Proposta", value=linha['DESCRIÇÃO'])
    c1, c2 = st.columns(2)
    unid = c1.text_input("Unidade", value=str(linha.get('UND', 'und')))
    qtd = c2.number_input("Quantidade", value=float(pd.to_numeric(linha.get('QDT', 1), errors='coerce') or 1.0))
    
    custo_mat = st.number_input("Custo Material (Base MP)", value=preco_sugerido, format="%.2f")
    custo_mo = st.number_input("Custo Mão de Obra", value=0.0, format="%.2f")
    
    st.divider()
    if st.button("Salvar e Finalizar Item"):
        # Salva na memória do sistema
        st.session_state.respostas[index] = {
            "Concluído": "✅",
            "Desc_Final": nova_desc,
            "Custo_Mat": custo_mat,
            "Custo_MO": custo_mo,
            "Venda_Unit": (custo_mat + custo_mo) * 1.5 # Exemplo de fórmula simples
        }
        st.rerun()

# --- 4. PROCESSAMENTO ---
if arq_obra and arq_mp:
    try:
        df_obra = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        # Padroniza nomes das colunas para evitar erros
        df_obra.columns = [str(c).strip().upper() for c in df_obra.columns]
        
        # Lê MP Valores
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        df_mp = pd.concat(dict_mp.values(), ignore_index=True)
        
        st.subheader("📋 Planilha de Orçamento")
        
        # Prepara a visualização com o Status de Check
        df_visualizacao = df_obra.copy()
        df_visualizacao['STATUS'] = [st.session_state.respostas.get(i, {}).get("Concluído", "⭕") for i in df_visualizacao.index]
        
        # Reordena para o Status ser a primeira coluna
        cols = ['STATUS'] + [c for c in df_visualizacao.columns if c != 'STATUS']
        df_visualizacao = df_visualizacao[cols]

        # Tabela com Barra de Rolagem
        st.write("Clique no botão abaixo para editar a linha correspondente:")
        
        # Criando a tabela interativa onde cada linha tem um botão
        for i, row in df_visualizacao.iterrows():
            with st.container(border=True):
                col1, col2, col3, col4 = st.columns([0.5, 1, 4, 1])
                col1.write(row['STATUS'])
                col2.write(row.get('ITEM', '-'))
                col3.write(row.get('DESCRIÇÃO', 'Linha de Título/Vazia'))
                if col4.button("Editar", key=f"btn_{i}"):
                    abrir_edicao(i, row, df_mp)

    except Exception as e:
        st.error(f"Erro: {e}")
else:
    st.warning("Aguardando os arquivos para liberar o layout...")
