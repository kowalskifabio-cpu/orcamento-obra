import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Orçamentador Marcenaria v22", layout="wide")

# --- 1. INICIALIZAÇÃO DE MEMÓRIA ---
def inicializar_estado():
    if 'df_obra' not in st.session_state: st.session_state.df_obra = None
    if 'df_mp' not in st.session_state: st.session_state.df_mp = None
    if 'composicoes' not in st.session_state: st.session_state.composicoes = {}
    if 'taxas' not in st.session_state:
        st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "lucro": 20.0, "comissao": 5.0}

inicializar_estado()

# --- 2. FUNÇÕES DE PERSISTÊNCIA (JSON) ---
def exportar_projeto_json():
    projeto = {
        "df_obra": st.session_state.df_obra.to_json(orient="split") if st.session_state.df_obra is not None else None,
        "taxas": st.session_state.taxas,
        "composicoes": {
            str(k): {bloco: df.to_json(orient="split") for bloco, df in v.items()}
            for k, v in st.session_state.composicoes.items()
        }
    }
    return json.dumps(projeto, indent=4)

def carregar_projeto_json(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        # Limpa o estado atual antes de restaurar
        st.session_state.composicoes = {}
        
        if dados.get("df_obra"):
            df_temp = pd.read_json(dados["df_obra"], orient="split")
            st.session_state.df_obra = df_temp.reset_index(drop=True)
            if 'CUSTO UNITÁRIO FINAL' in st.session_state.df_obra.columns:
                st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] = pd.to_numeric(st.session_state.df_obra['CUSTO UNITÁRIO FINAL']).fillna(0.0)
        
        if "taxas" in dados:
            st.session_state.taxas = dados["taxas"]
        
        if dados.get("composicoes"):
            nova_comp = {}
            for idx_str, blocos in dados["composicoes"].items():
                idx_int = int(idx_str)
                nova_comp[idx_int] = {}
                for nome_bloco, js in blocos.items():
                    nova_comp[idx_int][nome_bloco] = pd.read_json(js, orient="split")
            st.session_state.composicoes = nova_comp
        return True
    except Exception as e:
        st.error(f"Falha na restauração: {e}")
        return False

# --- 3. COMPONENTE DE BLOCO (FRAGMENTO) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_mem = st.session_state.composicoes[idx][chave].reset_index(drop=True)
    df_mem["Código"] = range(1, len(df_mem) + 1)

    df_ed = st.data_editor(df_mem, num_rows="dynamic", use_container_width=True, key=f"v22_{chave}_{idx}_{st.session_state.get('last_load', 0)}")

    if not df_ed.equals(df_mem):
        df_ed = df_ed.reset_index(drop=True)
        df_ed["Código"] = range(1, len(df_ed) + 1)
        for i, r in df_ed.iterrows():
            # Busca MP
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                u, p = buscar_dados_mp(r['Descrição'])
                if u: df_ed.at[i, 'Unid.'], df_ed.at[i, 'Valor Unit.'] = u, p
            
            # Cálculos
            q = float(pd.to_numeric(r.get('Quant.'), errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            fat = float(pd.to_numeric(r.get('Fator'), errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            custo = q * vu
            df_ed.at[i, "Valor Total"] = custo
            df_ed.at[i, "Valor Final"] = custo * (1 + (fat/100)) if tipo_fator == "perc" else custo * (fat if fat != 0 else 1)
        
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. DIÁLOGO DE DETALHAMENTO ---
@st.dialog("Detalhamento Técnico", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 Item: {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Terceirizado c/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    c_direto = v1 + v2 + v3
    bdi = sum(st.session_state.taxas.values())
    venda = c_direto * (1 + (bdi / 100))

    st.divider()
    st.metric("PREÇO DE VENDA SUGERIDO", f"R$ {venda:,.2f}", delta=f"Custo Direto: R$ {c_direto:,.2f}")
    if st.button("💾 Aplicar Preço na Planilha Principal"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 5. BUSCA NA MP ---
def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    col_n = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_u = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_p = next((c for c in base.columns if 'VLR / PÇ.' in c.upper()), None)
    if not col_n: return None, None
    match = base[base[col_n].astype(str).str.strip().str.lower() == termo]
    if match.empty: match = base[base[col_n].astype(str).str.lower().str.contains(termo, na=False)]
    if not match.empty:
        return str(match[col_u].iloc[0]), float(pd.to_numeric(match[col_p].iloc[0], errors='coerce') or 0.0)
    return "un", 0.0

# --- 6. INTERFACE ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png")
    st.header("💾 Gestão de Projeto")
    if st.session_state.df_obra is not None:
        st.download_button("📥 Baixar Backup JSON", exportar_projeto_json(), f"projeto_{datetime.now().strftime('%d_%H%M')}.json")
    
    arq_proj = st.file_uploader("📂 Retomar Projeto", type=["json"])
    if arq_proj:
        if st.button("🔄 Restaurar Dados"):
            if carregar_projeto_json(arq_proj):
                st.session_state.last_load = datetime.now().timestamp()
                st.rerun()

    st.divider()
    st.header("⚖️ Taxas (%)")
    for k in st.session_state.taxas:
        st.session_state.taxas[k] = st.number_input(f"{k.capitalize()}", value=st.session_state.taxas[k])

st.title("🏗️ Orçamentador Profissional")
tabs = st.tabs(["📝 Orçamento", "🔍 Auditoria", "🛒 Compras", "📄 Proposta"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1: arq_o = st.file_uploader("Planilha Obra", type=["xlsx", "xlsm"])
    with c2: arq_m = st.file_uploader("Planilha MP", type=["xlsx", "csv"])
    
    if arq_o and arq_m:
        if st.session_state.df_mp is None:
            st.session_state.df_mp = pd.read_excel(arq_m)
            st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
        if st.session_state.df_obra is None:
            df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0).reset_index(drop=True)
            df.columns = [str(c).upper() for c in df.columns]
            df.insert(0, 'STATUS', '⭕')
            df['CUSTO UNITÁRIO FINAL'] = 0.0
            st.session_state.df_obra = df
        
        st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key=f"master_v22_{st.session_state.get('last_load', 0)}")
        idx_sel = st.number_input("Selecione a linha:", 0, len(st.session_state.df_obra)-1, 0)
        if st.button(f"🔎 Detalhar Item {idx_sel}", type="primary"):
            modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

# --- ABAS DE APOIO ---
dados_consolidar = []
if st.session_state.df_obra is not None:
    for i, comps in st.session_state.composicoes.items():
        for g, df in comps.items():
            if not df.empty:
                df_c = df.copy()
                df_c['Item Master'] = st.session_state.df_obra.at[i, 'DESCRIÇÃO']
                dados_consolidar.append(df_c)

with tabs[1]:
    if dados_consolidar: st.dataframe(pd.concat(dados_consolidar), use_container_width=True)
    else: st.info("Abra o detalhamento de um item para auditar.")

with tabs[2]:
    if dados_consolidar:
        listao = pd.concat(dados_consolidar).groupby(['Descrição', 'Unid.']).agg({'Quant.': 'sum'}).reset_index()
        st.dataframe(listao, use_container_width=True)

with tabs[3]:
    if st.session_state.df_obra is not None:
        venda_df = st.session_state.df_obra[st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] > 0]
        st.table(venda_df[['DESCRIÇÃO', 'UNID', 'QUANT', 'CUSTO UNITÁRIO FINAL']])
        st.write(f"### TOTAL DO ORÇAMENTO: R$ {venda_df['CUSTO UNITÁRIO FINAL'].sum():,.2f}")
