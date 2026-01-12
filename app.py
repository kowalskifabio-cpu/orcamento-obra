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

# --- 2. LÓGICA DE PROCESSAMENTO (ESTÁVEL) ---
def aplicar_regras_calculo(df, tipo_fator):
    """Calcula códigos, preços e totais de forma sequencial e segura."""
    df = df.reset_index(drop=True)
    for i, r in df.iterrows():
        # Código Sequencial Automático
        df.at[i, "Código"] = i + 1
        
        # Busca automática na MP (apenas se descrição existir e unidade estiver vazia)
        if r['Descrição'] and (pd.isna(r['Unid.']) or r['Unid.'] == "" or r['Unid.'] == "0"):
            u, v = buscar_dados_mp(r['Descrição'])
            if u:
                df.at[i, 'Unid.'] = u
                df.at[i, 'Valor Unit.'] = v
        
        # Matemática de Custo e Venda
        try:
            q = float(r['Quant.']) if not pd.isna(r['Quant.']) else 0.0
            vu = float(r['Valor Unit.']) if not pd.isna(r['Valor Unit.']) else 0.0
            fat = float(r['Fator']) if not pd.isna(r['Fator']) else (0.0 if tipo_fator == "perc" else 1.0)
            
            custo_total = q * vu
            df.at[i, "Valor Total"] = custo_total
            
            if tipo_fator == "perc":
                df.at[i, "Valor Final"] = custo_total * (1 + (fat / 100))
            else:
                df.at[i, "Valor Final"] = custo_total * fat
        except:
            continue
    return df

# --- 3. BLOCO DE COMPOSIÇÃO (FRAGMENTO) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.subheader(f"📦 {titulo}")
    
    # Carrega dados e garante que o 'Código' esteja atualizado antes de exibir
    df_memoria = st.session_state.composicoes[idx][chave]
    if len(df_memoria) > 0:
        df_memoria["Código"] = range(1, len(df_memoria) + 1)

    # O Editor de Dados
    df_ed = st.data_editor(
        df_memoria,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_estavel_{chave}_{idx}", # Chave única e persistente
        column_config={
            "Código": st.column_config.NumberColumn("Item #", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Acréscimo %" if tipo_fator == "perc" else "Multiplicador x")
        }
    )

    # Detecta mudança: se o que saiu do editor é diferente do que está na memória
    if not df_ed.equals(df_memoria):
        # Processa e salva
        df_processado = aplicar_regras_calculo(df_ed, tipo_fator)
        st.session_state.composicoes[idx][chave] = df_processado
        st.rerun(scope="fragment")

    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. DIÁLOGO E INTERFACE MASTER ---
@st.dialog("Composição Técnica por Grupos", width="large")
def modal_cpu(idx, linha_master):
    st.write(f"### 🛠️ {linha_master.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    total_venda = v1 + v2 + v3
    st.divider()
    st.metric("PREÇO DE VENDA FINAL DO ITEM", f"R$ {total_venda:,.2f}")
    
    if st.button("💾 Finalizar e Salvar", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- UI PRINCIPAL ---
st.title("Orçamentador Profissional")

# Sidebar para Salvar/Carregar JSON (Essencial para segurança)
with st.sidebar:
    st.header("💾 Salvar Trabalho")
    if st.session_state.df_obra is not None:
        dados = {"df_obra": st.session_state.df_obra.to_json(orient="split"), 
                 "composicoes": {str(k): {b: df.to_json(orient="split") for b in v} for k, v in st.session_state.composicoes.items()}}
        st.download_button("📥 Baixar JSON do Projeto", json.dumps(dados), "projeto_orcamento.json")
    
    st.divider()
    arq_proj = st.file_uploader("📂 Retomar do JSON", type=["json"])
    if arq_proj and st.button("🔄 Restaurar Projeto"):
        p = json.load(arq_proj)
        st.session_state.df_obra = pd.read_json(p["df_obra"], orient="split")
        st.session_state.composicoes = {int(k): {b: pd.read_json(js, orient="split") for b in v} for k, v in p["composicoes"].items()}
        st.rerun()

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("Obra", type=["xlsx", "csv"])
with c2: arq_m = st.file_uploader("MP Valores", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m) if arq_m.name.endswith('.xlsx') else pd.read_csv(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]; df.insert(0, 'STATUS', '⭕'); df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_editor_final")
    idx = st.number_input("Índice da Linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Detalhar Item {idx}", type="primary"):
        modal_cpu(idx, st.session_state.df_obra.iloc[idx])
