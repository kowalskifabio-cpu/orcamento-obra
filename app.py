import streamlit as st
import pandas as pd
from io import BytesIO
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. LOGO E MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# --- 2. FUNÇÃO DE BUSCA NA BASE MP ---
def buscar_dados_mp(descricao_pesquisada):
    if st.session_state.df_mp is None:
        return "un", 0.0
    
    base = st.session_state.df_mp
    # Busca aproximada (contém o nome)
    match = base[base.astype(str).apply(lambda x: x.str.contains(descricao_pesquisada, case=False, na=False)).any(axis=1)]
    
    if not match.empty:
        # Pega o primeiro resultado encontrado
        unidade = str(match['PÇIDADE'].iloc[0]) if 'PÇIDADE' in match.columns else "un"
        custo = float(pd.to_numeric(match['VLR / PÇ.'].iloc[0], errors='coerce') or 0.0)
        return unidade, custo
    
    return "un", 0.0

# --- 3. CAIXA DE DETALHAMENTO COM LÓGICA DE BUSCA ---
@st.dialog("Composição Técnica por Grupos", width="large")
def abrir_cpu_detalhada(idx, dados_linha):
    st.write(f"### 🛠️ Item: {dados_linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator/Acrésc."]
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=cols),
            "servico": pd.DataFrame(columns=cols),
            "material": pd.DataFrame(columns=cols)
        }

    comp = st.session_state.composicoes[idx]

    def renderizar_bloco(titulo, chave, label_fator):
        st.subheader(f"📦 {titulo}")
        
        # Editor de Tabela
        df_edit = st.data_editor(
            comp[chave],
            num_rows="dynamic",
            column_config={
                "Descrição": st.column_config.TextColumn("Descrição (Digite para buscar)"),
                "Unid.": st.column_config.TextColumn("Unid. (Auto)"),
                "Valor Unit.": st.column_config.NumberColumn("Custo (Auto)", format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn("Subtotal", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"editor_{chave}_{idx}"
        )

        # LÓGICA DE ATUALIZAÇÃO AUTOMÁTICA
        if not df_edit.empty:
            for i, row in df_edit.iterrows():
                # Se o usuário digitou uma descrição mas a unidade/custo estão zerados, tenta buscar
                if pd.notnull(row['Descrição']) and row['Descrição'] != "" and row['Valor Unit.'] == 0:
                    u, c = buscar_dados_mp(row['Descrição'])
                    df_edit.at[i, 'Unid.'] = u
                    df_edit.at[i, 'Valor Unit.'] = c
            
            df_edit["Valor Total"] = pd.to_numeric(df_edit["Quant."], errors='coerce').fillna(0) * \
                                     pd.to_numeric(df_edit["Valor Unit."], errors='coerce').fillna(0)
            st.session_state.composicoes[idx][chave] = df_edit
            return df_edit["Valor Total"].sum()
        return 0.0

    t1 = renderizar_bloco("Material Terceirizado", "terceirizado", "Acréscimo (%)")
    t2 = renderizar_bloco("Material Terceirizado C/ Serviço", "servico", "Multiplicador (x)")
    t3 = renderizar_bloco("Material", "material", "Multiplicador (x)")

    st.divider()
    total_custo_direto = t1 + t2 + t3
    st.metric("Custo Direto Total", f"R$ {total_custo_direto:,.2f}")

    if st.button("✅ Salvar e Atualizar Planilha Master"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_custo_direto
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Marcenaria & Mármore")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    # Carregamento e identificação de colunas da MP
    if st.session_state.df_mp is None:
        if arq_mp.name.endswith('.csv'):
            st.session_state.df_mp = pd.read_csv(arq_mp)
        else:
            st.session_state.df_mp = pd.read_excel(arq_mp)

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df
    
    df_master = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_edit")
    st.session_state.df_obra = df_master

    st.divider()
    idx_sel = st.number_input("Índice da linha para detalhar:", min_value=0, max_value=len(df_master)-1, step=1)
    if st.button(f"🔎 Abrir Composição da Linha {idx_sel}"):
        abrir_cpu_detalhada(idx_sel, df_master.iloc[idx_sel])
