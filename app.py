import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v12", layout="wide")

# --- 1. MEMÓRIA E BUSCA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc:
        return None, None
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    
    # Identifica as colunas alvo
    col_nome = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_unid = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_preco = next((c for c in base.columns if 'VLR / PÇ.' in c.upper() or 'VLR/PÇ' in c.upper()), None)

    if not col_nome: return None, None

    match = base[base[col_nome].astype(str).str.strip().str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        u = str(match[col_unid].iloc[0]) if col_unid else "un"
        p = float(pd.to_numeric(match[col_preco].iloc[0], errors='coerce') or 0.0) if col_preco else 0.0
        return u, p
    return "N/A", 0.0

# --- 2. COMPONENTE DE BLOCO TÉCNICO ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_memoria = st.session_state.composicoes[idx][chave]
    
    if len(df_memoria) > 0:
        df_memoria = df_memoria.reset_index(drop=True)
        df_memoria["Código"] = range(1, len(df_memoria) + 1)

    df_ed = st.data_editor(
        df_memoria,
        num_rows="dynamic",
        use_container_width=True,
        key=f"ed_v12_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    if st.button(f"Calcular {titulo}", key=f"btn_v12_{chave}_{idx}"):
        df_ed = df_ed.reset_index(drop=True)
        itens_encontrados = 0
        for i, r in df_ed.iterrows():
            df_ed.at[i, "Código"] = i + 1
            if r.get('Descrição'):
                unid, preco = buscar_dados_mp(r['Descrição'])
                if unid and unid != "N/A":
                    df_ed.at[i, 'Unid.'] = unid
                    df_ed.at[i, 'Valor Unit.'] = preco
                    itens_encontrados += 1
            
            q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            custo_t = q * vu
            df_ed.at[i, "Valor Total"] = custo_t
            df_ed.at[i, "Valor Final"] = custo_t * (1 + (f/100)) if tipo_fator == "perc" else custo_t * (f if f != 0 else 1)
        
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 3. DIÁLOGO (POP-UP) ---
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
    st.metric("PREÇO DE VENDA TOTAL", f"R$ {total:,.2f}")
    if st.button("💾 Finalizar e Salvar na Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 4. GESTÃO DE PROJETOS ---
def exportar_projeto():
    proj = {"df_obra": st.session_state.df_obra.to_json(orient="split"), 
            "composicoes": {str(k): {b: df.to_json(orient="split") for b in v} for k, v in st.session_state.composicoes.items()}}
    return json.dumps(proj)

# --- 5. UI PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional")

with st.sidebar:
    st.header("⚙️ Projeto")
    if st.session_state.df_obra is not None:
        st.download_button("📥 Salvar Progresso (.json)", exportar_projeto(), "projeto.json")
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

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_v12")
    idx_sel = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

    if st.button("📊 Baixar Excel Final"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            st.session_state.df_obra.to_excel(writer, index=False)
        st.download_button("Clique para Baixar", out.getvalue(), "Orcamento.xlsx")

