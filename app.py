import streamlit as st
import pandas as pd
from io import BytesIO
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. MEMÓRIA E LOGO ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# --- 2. CAIXA DE DETALHAMENTO COM 3 BLOCOS ---
@st.dialog("Composição Técnica por Grupos", width="large")
def abrir_cpu_detalhada(idx, dados_linha):
    st.write(f"### 🛠️ Item: {dados_linha.get('DESCRIÇÃO', 'Item')}")
    st.info(f"**Especificação:** {dados_linha.get('OBSERVAÇÕES', 'N/A')}")

    # Inicializa estrutura de 3 blocos se não existir
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator/Acrésc."]
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=cols),
            "servico": pd.DataFrame(columns=cols),
            "material": pd.DataFrame(columns=cols)
        }

    comp = st.session_state.composicoes[idx]

    # --- FUNÇÃO PARA RENDERIZAR BLOCO ---
    def renderizar_bloco(titulo, chave, label_fator, help_text):
        st.subheader(f"📦 {titulo}")
        st.caption(help_text)
        
        df_edit = st.data_editor(
            comp[chave],
            num_rows="dynamic",
            column_config={
                "Valor Unit.": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn("Subtotal", format="R$ %.2f", disabled=True),
                "Fator/Acrésc.": st.column_config.TextColumn(label_fator)
            },
            use_container_width=True,
            key=f"editor_{chave}_{idx}"
        )
        
        # Cálculos Internos do Bloco
        if not df_edit.empty:
            df_edit["Valor Total"] = pd.to_numeric(df_edit["Quant."], errors='coerce').fillna(0) * \
                                     pd.to_numeric(df_edit["Valor Unit."], errors='coerce').fillna(0)
            comp[chave] = df_edit
            return df_edit["Valor Total"].sum()
        return 0.0

    # BLOCO 1: Material Terceirizado (+%)
    t1 = renderizar_bloco("Material Terceirizado", "terceirizado", "Acréscimo (%)", "Ex: 40 para somar 40% ao custo.")
    
    # BLOCO 2: Material Terceirizado C/ Serviço (x Fator)
    t2 = renderizar_bloco("Material Terceirizado C/ Serviço", "servico", "Multiplicador (x)", "Ex: 2 para dobrar o custo.")
    
    # BLOCO 3: Material (x Fator)
    t3 = renderizar_bloco("Material", "material", "Multiplicador (x)", "Ex: 3 para triplicar o custo.")

    st.divider()
    total_custo_direto = t1 + t2 + t3
    st.metric("Custo Direto Total Acumulado", f"R$ {total_custo_direto:,.2f}")

    if st.button("✅ Salvar Composição Técnica"):
        st.session_state.df_obra.at[idx, 'Custo Unitário Final'] = total_custo_direto
        st.session_state.df_obra.at[idx, 'Status'] = "✅"
        st.rerun()

# --- 3. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Marcenaria & Mármore")

u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df
    
    st.write("### Planilha Master (Editável)")
    df_master = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_edit")
    st.session_state.df_obra = df_master

    st.divider()
    idx_sel = st.number_input("Índice da linha para detalhar:", min_value=0, max_value=len(df_master)-1, step=1)
    if st.button(f"🔎 Abrir Composição da Linha {idx_sel}", type="primary"):
        abrir_cpu_detalhada(idx_sel, df_master.iloc[idx_sel])
