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

st.title("🏗️ Detalhamento de Itens (Regras Simples)")

# --- 2. UPLOAD ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with col_up2:
    arq_mp = st.file_uploader("2. MP Valores", type=["xlsx", "csv"])

# --- 3. MEMÓRIA DE DADOS (Para não perder o que foi preenchido) ---
if 'respostas' not in st.session_state:
    st.session_state.respostas = {}

# --- 4. PROCESSAMENTO ---
if arq_obra and arq_mp:
    try:
        # Lendo a Obra (Pula 7 linhas)
        df_obra = pd.read_excel(arq_obra, skiprows=7) if arq_obra.name.endswith('.xlsx') else pd.read_csv(arq_obra, skiprows=7)
        # Limpa nomes de colunas ocultas
        df_obra.columns = [str(c).strip() for c in df_obra.columns]
        # Remove apenas linhas onde TODA a linha é vazia
        df_obra = df_obra.dropna(how='all').reset_index(drop=True)

        # Lendo a MP Valores (Buscando em todas as abas)
        dict_mp = pd.read_excel(arq_mp, sheet_name=None)
        df_mp = pd.concat(dict_mp.values(), ignore_index=True) if isinstance(dict_mp, dict) else dict_mp
        df_mp.columns = [str(c).strip() for c in df_mp.columns]

        # --- 5. INTERFACE DIVIDIDA ---
        col_lista, col_form = st.columns([1, 2])

        with col_lista:
            st.subheader("📋 Itens da Obra")
            # Criamos uma lista de botões ou um rádio para selecionar o item
            titulos = df_obra.apply(lambda x: f"{x[0] if pd.notnull(x[0]) else '-'} | {x[1] if pd.notnull(x[1]) else 'Sem Descrição'}", axis=1)
            item_idx = st.radio("Selecione o item para detalhar:", range(len(df_obra)), format_func=lambda x: titulos[x])

        with col_form:
            item_atual = df_obra.iloc[item_idx]
            desc_cliente = str(item_atual.iloc[1]) # Coluna da Descrição
            
            st.subheader(f"🛠️ Editar: {desc_cliente}")
            
            with st.container(border=True):
                # Campos Editáveis
                nova_desc = st.text_input("Descrição na Proposta", value=desc_cliente)
                c1, c2 = st.columns(2)
                unid = c1.text_input("Unidade", value=str(item_atual.get('UND', 'und')))
                qtd = c2.number_input("Quantidade da Construtora", value=float(pd.to_numeric(item_atual.get('QDT', 0), errors='coerce') or 0.0))

                st.markdown("---")
                st.write("#### 🔍 Busca Automática no MP Valores")
                
                # REGRA DE BUSCA NAS COLUNAS ESPECÍFICAS
                # O sistema tenta achar o nome do material nas colunas que você indicou
                custo_sugerido = 0.0
                cols_precos = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "PREÇO", "NOME PRODUTO"]
                
                # Busca simplificada por nome
                busca_mp = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(desc_cliente, case=False, na=False)).any(axis=1)]
                
                if not busca_mp.empty:
                    st.success("Item encontrado na base MP!")
                    # Tenta extrair o valor de uma das colunas de preço
                    for c in cols_precos:
                        if c in busca_mp.columns:
                            custo_sugerido = float(pd.to_numeric(busca_mp[c].iloc[0], errors='coerce') or 0.0)
                            if custo_sugerido > 0: break
                    st.info(f"Preço sugerido da Base MP: R$ {custo_sugerido:.2f}")

                # Campos de Cálculo
                custo_unit = st.number_input("Valor Unitário (Custo Material)", value=custo_sugerido, format="%.2f")
                mo_unit = st.number_input("Custo Mão de Obra Unitário", value=0.0)
                
                # Aqui entrarão as próximas regras que você enviar
                st.warning("Próximas fórmulas serão inseridas aqui...")

                if st.button("💾 Salvar este Item"):
                    st.session_state.respostas[item_idx] = {
                        "Desc": nova_desc,
                        "Custo": custo_unit,
                        "Total": custo_unit * qtd
                    }
                    st.toast("Dados salvos temporariamente!")

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
else:
    st.warning("Aguardando os dois arquivos para iniciar.")
