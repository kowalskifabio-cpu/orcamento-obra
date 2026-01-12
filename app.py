import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v11", layout="wide")

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

# --- 2. COMPONENTE DE BLOCO (FRAGMENTO ESTÁVEL) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    
    # Prepara o DataFrame da memória
    df_memoria = st.session_state.composicoes[idx][chave]
    
    # Garante Código Automático antes de exibir
    if len(df_memoria) > 0:
        df_memoria = df_memoria.reset_index(drop=True)
        df_memoria["Código"] = range(1, len(df_memoria) + 1)

    # Editor de Dados
    df_ed = st.data_editor(
        df_memoria,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_v11_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # BOTÃO PARA PROCESSAR (Evita erros de sincronia ao digitar)
    if st.button(f"Calcular {titulo}", key=f"btn_v11_{chave}_{idx}"):
        df_ed = df_ed.reset_index(drop=True)
        for i, r in df_ed.iterrows():
            df_ed.at[i, "Código"] = i + 1 # Re-numeração forçada
            
            # Busca MP
            if r['Descrição'] and (pd.isna(r['Valor Unit.']) or r['Valor Unit.'] == 0):
                u, v = buscar_dados_mp(r['Descrição'])
                if u:
                    df_ed.at[i, 'Unid.'] = u
                    df_ed.at[i, 'Valor Unit.'] = v
            
            # Cálculos
            q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
            vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
            f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo_total = q * vu
            df_ed.at[i, "Valor Total"] = custo_total
            if tipo_fator == "perc":
                df_ed.at[i, "Valor Final"] = custo_total * (1 + (f / 100))
            else:
                df_ed.at[i, "Valor Final"] = custo_total * (f if f != 0 else 1)
        
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")

    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 3. DIÁLOGO PRINCIPAL ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 {linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    total = v1 + v2 + v3
    st.divider()
    st.metric("TOTAL DE VENDA", f"R$ {total:,.2f}")
    
    if st.button("💾 Finalizar Item e Salvar na Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 4. INTERFACE PRINCIPAL ---
st.title("Orçamentador Profissional")

with st.sidebar:
    st.header("⚙️ Projeto")
    if st.session_state.df_obra is not None:
        proj = {"df_obra": st.session_state.df_obra.to_json(orient="split"), 
                "composicoes": {str(k): {b: df.to_json(orient="split") for b in v} for k, v in st.session_state.composicoes.items()}}
        st.download_button("📥 Baixar Progresso (.json)", json.dumps(proj), "projeto.json")
    
    arq_proj = st.file_uploader("📂 Retomar Projeto", type=["json"])
    if arq_proj and st.button("Restaurar Dados"):
        dados = json.load(arq_proj)
        st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
        st.session_state.composicoes = {int(k): {b: pd.read_json(js, orient="split") for b in v} for k, v in dados["composicoes"].items()}
        st.rerun()

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("1. Planilha Obra", type=["xlsx", "csv"])
with c2: arq_m = st.file_uploader("2. MP Valores", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m) if arq_m.name.endswith('.xlsx') else pd.read_csv(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]; df.insert(0, 'STATUS', '⭕'); df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_v11")
    idx = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx}", type="primary"):
        modal_cpu(idx, st.session_state.df_obra.iloc[idx])
