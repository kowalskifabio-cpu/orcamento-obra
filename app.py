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
def abrir_cpu(idx, dados_linha, df_mp):
    # Identifica colunas de forma flexível
    col_desc = next((c for c in dados_linha.index if 'DESCRIÇÃO' in str(c).upper()), dados_linha.index[1])
    col_obs = next((c for c in dados_linha.index if 'OBSERVAÇÕES' in str(c).upper()), None)
    
    st.write(f"### 🛠️ Composição Técnica")
    
    # CAMPOS DE CABEÇALHO EDITÁVEIS DENTRO DO POP-UP
    new_desc = st.text_input("Descrição do Item", value=str(dados_linha[col_desc]))
    
    # Campo Observações (Especificação) agora é um text_area editável
    val_obs = str(dados_linha[col_obs]) if col_obs and pd.notnull(dados_linha[col_obs]) else ""
    new_spec = st.text_area("Especificação (Observações da Construtora)", value=val_obs, height=100)
    
    if idx not in st.session_state.cpus:
        st.session_state.cpus[idx] = pd.DataFrame(columns=[
            "Tipo", "Insumo/Material", "Unid", "Qtd", "Preço Unit. (MP)", "Observações Técnicas", "Subtotal"
        ])

    df_atual = st.session_state.cpus[idx]

    with st.container(border=True):
        # Tabela de Insumos
        df_editado = st.data_editor(
            df_atual,
            num_rows="dynamic",
            column_config={
                "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Material", "Mão de Obra", "Terceirizado", "Ferragem"]),
                "Preço Unit. (MP)": st.column_config.NumberColumn("Custo Unit. (R$)", format="R$ %.2f"),
                "Observações Técnicas": st.column_config.TextColumn("Observações Técnicas", width="large"),
                "Subtotal": st.column_config.NumberColumn("Subtotal", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"cpu_editor_{idx}"
        )

        if not df_editado.empty:
            df_editado["Subtotal"] = df_editado["Qtd"].fillna(0) * df_editado["Preço Unit. (MP)"].fillna(0)
            total_direto = df_editado["Subtotal"].sum()
        else:
            total_direto = 0.0

        st.divider()
        st.metric("Custo Direto Total", f"R$ {total_direto:,.2f}")
        
        if st.button("✅ Salvar e Atualizar Master"):
            # Atualiza a memória da CPU
            st.session_state.cpus[idx] = df_editado
            # Atualiza os dados na planilha principal (Master)
            st.session_state.df_obra.at[idx, col_desc] = new_desc
            if col_obs:
                st.session_state.df_obra.at[idx, col_obs] = new_spec
            st.session_state.df_obra.at[idx, 'Custo Unitário Final'] = total_direto
            st.session_state.df_obra.at[idx, 'Status'] = "✅"
            st.rerun()

# --- 3. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Flexível")

u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    # Carregamento MP
    try:
        df_mp = pd.read_csv(arq_mp) if arq_mp.name.endswith('.csv') else pd.read_excel(arq_mp)
    except:
        df_mp = None

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.insert(0, 'Status', '⭕')
        df['Custo Unitário Final'] = 0.0
        st.session_state.df_obra = df
    
    st.write("### Planilha Master (Editável)")
    st.info("Você pode editar os dados diretamente na tabela abaixo ou usar o botão Detalhar.")

    # TABELA PRINCIPAL 100% EDITÁVEL
    df_master_editado = st.data_editor(
        st.session_state.df_obra,
        use_container_width=True,
        hide_index=False,
        num_rows="dynamic",
        key="master_editor"
    )
    st.session_state.df_obra = df_master_editado

    # Sistema de seleção para o Modal
    st.divider()
    idx_selecionado = st.number_input("Digite o número do índice da linha para detalhar (lado esquerdo):", 
                                     min_value=0, max_value=len(st.session_state.df_obra)-1, step=1)
    
    if st.button(f"🔎 Abrir Detalhamento da Linha {idx_selecionado}", type="primary"):
        abrir_cpu(idx_selecionado, st.session_state.df_obra.iloc[idx_selecionado], df_mp)

else:
    st.session_state.df_obra = None
