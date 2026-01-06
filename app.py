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

if 'df_obra' not in st.session_state:
    st.session_state.df_obra = None
if 'cpus' not in st.session_state:
    st.session_state.cpus = {} 

# --- 2. MODAL DE COMPOSIÇÃO TÉCNICA ---
@st.dialog("Detalhamento da Composição (CPU)", width="large")
def abrir_cpu(idx, dados_linha, df_mp):
    # Identifica Descrição e Observações (Especificação)
    # Busca flexível pelos nomes das colunas
    col_desc = next((c for c in dados_linha.index if 'DESCRIÇÃO' in str(c).upper()), dados_linha.index[1])
    col_obs = next((c for c in dados_linha.index if 'OBSERVAÇÕES' in str(c).upper()), None)
    
    desc_item = str(dados_linha[col_desc])
    especificacao = str(dados_linha[col_obs]) if col_obs else "Não informada"
    
    st.write(f"### 📋 Item: {desc_item}")
    st.info(f"**Especificação:** {especificacao}") # Alterado de Observação para Especificação
    
    if idx not in st.session_state.cpus:
        st.session_state.cpus[idx] = pd.DataFrame(columns=[
            "Tipo", "Insumo/Material", "Unid", "Qtd", "Preço Unit. (MP)", "Observações Técnicas", "Subtotal"
        ])

    df_atual = st.session_state.cpus[idx]

    with st.container(border=True):
        st.write("#### 🛠️ Composição Técnica de Insumos")
        
        # BUSCA AUTOMÁTICA NA ABERTURA (Sugestão de Preço)
        preco_sugerido = 0.0
        if df_mp is not None:
            # Busca o termo da 'Descrição' na base MP
            match = df_mp[df_mp.astype(str).apply(lambda x: x.str.contains(desc_item, case=False, na=False)).any(axis=1)]
            if not match.empty:
                # Prioriza a coluna 'PREÇO' conforme o seu arquivo
                if 'PREÇO' in match.columns:
                    preco_sugerido = float(pd.to_numeric(match['PREÇO'].iloc[0], errors='coerce') or 0.0)

        # Editor de Tabela
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
        st.metric("Custo Direto Total do Item", f"R$ {total_direto:,.2f}")
        
        if st.button("✅ Salvar Composição"):
            st.session_state.cpus[idx] = df_editado
            st.session_state.df_obra.at[idx, 'Custo Unitário Final'] = total_direto
            st.session_state.df_obra.at[idx, 'Status'] = "✅"
            st.rerun()

# --- 3. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional")

u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    # Carregamento da Base MP
    try:
        if arq_mp.name.endswith('.csv'):
            df_mp = pd.read_csv(arq_mp)
        else:
            df_mp = pd.read_excel(arq_mp, sheet_name='MP')
    except:
        df_mp = pd.read_excel(arq_mp) if not arq_mp.name.endswith('.csv') else None

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.insert(0, 'Status', '⭕')
        df['Custo Unitário Final'] = 0.0
        st.session_state.df_obra = df
    
    # Exibição da Tabela Master
    st.write("### Itens para Orçamento")
    selecao = st.dataframe(
        st.session_state.df_obra,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(selecao.selection.rows) > 0:
        idx_sel = selecao.selection.rows[0]
        row_sel = st.session_state.df_obra.iloc[idx_sel]
        
        if st.button(f"🔎 Detalhar: {row_sel.iloc[2]}", type="primary"):
            abrir_cpu(idx_sel, row_sel, df_mp)
else:
    st.session_state.df_obra = None
