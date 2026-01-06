import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
import os

st.set_page_config(page_title="Orçamentador Pro - Detalhamento", layout="wide")

# --- LOGO ---
nome_logo = "WhatsApp Image 2026-01-06 at 08.45.15.jpeg"
if os.path.exists(nome_logo):
    st.sidebar.image(Image.open(nome_logo), use_container_width=True)

st.title("🏗️ Detalhamento de Itens - Orçamento")

# --- UPLOAD DE ARQUIVOS ---
col_up1, col_up2 = st.columns(2)
with col_up1:
    arq_obra = st.file_uploader("Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with col_up2:
    arq_mp = st.file_uploader("MP Valores", type=["xlsx", "csv"])

# --- SIDEBAR (PARÂMETROS) ---
with st.sidebar:
    st.header("⚙️ Regras Gerais")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro (%)", value=20.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# --- PROCESSAMENTO ---
if arq_obra and arq_mp:
    try:
        # Lendo a Obra
        df_obra = pd.read_excel(arq_obra, skiprows=7) if arq_obra.name.endswith('.xlsx') else pd.read_csv(arq_obra, skiprows=7)
        df_obra.columns = [c if not str(c).startswith('Unnamed') else f'C_{i}' for i, c in enumerate(df_obra.columns)]
        
        # Lendo a Base MP (Buscando as 3 colunas específicas de preço)
        df_mp = pd.read_excel(arq_mp, sheet_name=None)
        # Consolida todas as abas caso não saiba em qual está a MP
        df_mp_final = pd.concat(df_mp.values(), ignore_index=True) if isinstance(df_mp, dict) else df_mp
        
        # --- SELEÇÃO DE ITEM PARA DETALHAMENTO ---
        st.markdown("---")
        st.subheader("📦 Selecione um Item para Compor o Preço")
        
        # Filtra apenas linhas que parecem ter descrição (evita linhas de título vazias)
        opcoes_itens = df_obra.dropna(subset=[df_obra.columns[1]]) # Coluna B
        escolha = st.selectbox("Escolha o item da planilha para orçar:", 
                               opcoes_itens.index, 
                               format_func=lambda x: f"{df_obra.iloc[x][0]} - {df_obra.iloc[x][1]}")

        item_selecionado = df_obra.iloc[escolha]

        # --- FORMULÁRIO DE PREENCHIMENTO (A TELA 100% EDITÁVEL) ---
        st.info(f"Editando: **{item_selecionado[1]}**")
        
        with st.form("detalhe_item"):
            c1, c2, c3 = st.columns([3, 1, 1])
            desc_manual = c1.text_input("Descrição do Item (Edite se necessário)", value=item_selecionado[1])
            unid_manual = c2.text_input("Unidade", value=item_selecionado.get('UND', 'und'))
            qtd_manual = c3.number_input("Quantidade", value=float(pd.to_numeric(item_selecionado.get('QDT', 1.0), errors='coerce') or 1.0))

            st.write("### 💰 Composição de Custos")
            f1, f2, f3 = st.columns(3)
            
            # BUSCA AUTOMÁTICA NO MP VALORES
            # Procura o preço baseado na descrição exata nas colunas sugeridas
            preco_sugerido = 0.0
            cols_busca = ["Material Terceirizado", "MATERIAL TERCEIRIZADO C/ SERVIÇOS", "MATERIAL", "NOME PRODUTO", "PREÇO"]
            
            # Tenta achar o preço no seu listão
            match = df_mp_final[df_mp_final.astype(str).apply(lambda x: x.str.contains(desc_manual, case=False, na=False)).any(axis=1)]
            if not match.empty:
                # Tenta pegar valor de colunas de preço conhecidas
                for col_p in ["PREÇO", "VALOR", "CUSTO"]:
                    if col_p in match.columns:
                        preco_sugerido = float(match[col_p].iloc[0])
                        st.success(f"Preço de R$ {preco_sugerido} encontrado na base MP!")
                        break

            custo_mat = f1.number_input("Custo Material (R$)", value=preco_sugerido, format="%.2f")
            custo_mo = f2.number_input("Custo Mão de Obra Unit. (R$)", value=0.0, format="%.2f")
            outros_custos = f3.number_input("Outros/Frete (R$)", value=0.0, format="%.2f")

            # BOTÃO DE CALCULAR
            if st.form_submit_button("Calcular e Salvar na Planilha"):
                mo_enc = custo_mo * (1 + perc_encargos/100)
                custo_direto = custo_mat + mo_enc + outros_custos
                venda_unit = custo_direto / divisor
                total_item = venda_unit * qtd_manual
                
                st.session_state[f"total_{escolha}"] = total_item
                st.success(f"Item Orçado: Preço de Venda Unitário R$ {venda_unit:.2f} | Total: R$ {total_item:.2f}")

        # Exibição da Planilha de Resumo abaixo
        st.markdown("---")
        st.subheader("📋 Resumo do Orçamento Atual")
        st.write("Aqui aparecerão os itens que você já detalhou.")
        # (Lógica para acumular itens será o próximo passo conforme você desejar)

    except Exception as e:
        st.error(f"Erro ao carregar ou processar: {e}")
else:
    st.warning("Aguardando os dois arquivos para iniciar a 'brincadeira'!")

