import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v10", layout="wide")

# --- 1. MEMÓRIA E BUSCA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    base = st.session_state.df_mp
    termo = str(desc).strip().lower()
    col_nome = 'NOME PRODUTO' if 'NOME PRODUTO' in base.columns else base.columns[1]
    match = base[base[col_nome].astype(str).str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    if not match.empty:
        u = str(match['PÇIDADE'].iloc[0]) if 'PÇIDADE' in match.columns else "un"
        c = float(pd.to_numeric(match['VLR / PÇ.'].iloc[0], errors='coerce') or 0.0)
        return u, c
    return None, None

# --- 2. LÓGICA DE PROCESSAMENTO AUTOMÁTICO ---
def processar_df(df, tipo_fator):
    """Aplica Código automático e Cálculos sem necessidade de botão."""
    df = df.reset_index(drop=True)
    for i, r in df.iterrows():
        # Código Automático
        df.at[i, "Código"] = i + 1
        
        # Busca na MP
        if r['Descrição'] and (pd.isna(r['Valor Unit.']) or r['Valor Unit.'] == 0):
            u, v = buscar_dados_mp(r['Descrição'])
            if u:
                df.at[i, 'Unid.'] = u
                df.at[i, 'Valor Unit.'] = v
        
        # Cálculos
        q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
        vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
        f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
        
        subtotal = q * vu
        df.at[i, "Valor Total"] = subtotal
        if tipo_fator == "perc":
            df.at[i, "Valor Final"] = subtotal * (1 + (f / 100))
        else:
            df.at[i, "Valor Final"] = subtotal * f
    return df

# --- 3. COMPONENTE DE BLOCO (FRAGMENTO ESTÁVEL) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.subheader(f"📦 {titulo}")
    
    # Prepara o DF com códigos antes de mostrar
    df_orig = st.session_state.composicoes[idx][chave]
    if len(df_orig) > 0:
        df_orig["Código"] = range(1, len(df_orig) + 1)

    # Editor de Dados
    df_ed = st.data_editor(
        df_orig,
        num_rows="dynamic",
        use_container_width=True,
        key=f"v10_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Acréscimo %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # Atualiza memória e recalcula se houver mudança
    if not df_ed.equals(df_orig):
        st.session_state.composicoes[idx][chave] = processar_df(df_ed, tipo_fator)
        st.rerun(scope="fragment")

    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. DIÁLOGO PRINCIPAL ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 {linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    total = v1 + v2 + v3
    st.divider()
    st.metric("TOTAL DE VENDA", f"R$ {total:,.2f}")
    
    if st.button("💾 Finalizar e Salvar Tudo", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- UI PRINCIPAL ---
st.title("Orçamentador Profissional")

# Sidebar para Salvar/Carregar JSON (Essencial para não perder dados)
with st.sidebar:
    st.header("💾 Gestão de Projeto")
    if st.session_state.df_obra is not None:
        proj = {"df_obra": st.session_state.df_obra.to_json(orient="split"), 
                "composicoes": {str(k): {b: df.to_json(orient="split") for b in v} for k, v in st.session_state.composicoes.items()}}
        st.download_button("Baixar Progresso (.json)", json.dumps(proj), "orcamento.json")
    
    arq_proj = st.file_uploader("Retomar Projeto", type=["json"])
    if arq_proj and st.button("Restaurar Dados"):
        dados = json.load(arq_proj)
        st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
        st.session_state.composicoes = {int(k): {b: pd.read_json(js, orient="split") for b in v} for k, v in dados["composicoes"].items()}
        st.rerun()

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("Upload Obra", type=["xlsx", "csv"])
with c2: arq_m = st.file_uploader("Upload MP", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m) if arq_m.name.endswith('.xlsx') else pd.read_csv(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]; df.insert(0, 'STATUS', '⭕'); df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_v10")
    idx = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"Abrir Detalhamento {idx}", type="primary"):
        modal_cpu(idx, st.session_state.df_obra.iloc[idx])
