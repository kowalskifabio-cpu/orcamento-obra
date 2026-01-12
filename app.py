import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Orçamentador Marcenaria v23", layout="wide")

# --- 1. INICIALIZAÇÃO E TRATAMENTO DE COLUNAS ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}
if 'taxas' not in st.session_state:
    st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "lucro": 20.0, "comissao": 5.0}

def obter_coluna_flexivel(df, nomes_possiveis):
    """Retorna o nome real da coluna no DF a partir de uma lista de possibilidades."""
    for nome in nomes_possiveis:
        for col_real in df.columns:
            if nome.upper() in str(col_real).upper().strip():
                return col_real
    return None

# --- 2. PERSISTÊNCIA (JSON) BLINDADA ---
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
        st.session_state.composicoes = {}
        
        if dados.get("df_obra"):
            df_temp = pd.read_json(dados["df_obra"], orient="split")
            # Garante que os nomes das colunas fiquem limpos e padronizados
            df_temp.columns = [str(c).strip().upper() for c in df_temp.columns]
            st.session_state.df_obra = df_temp.reset_index(drop=True)
            
            # Garante coluna de custo
            col_custo = obter_coluna_flexivel(st.session_state.df_obra, ["CUSTO UNITÁRIO FINAL", "FINAL", "VALOR"])
            if col_custo:
                st.session_state.df_obra[col_custo] = pd.to_numeric(st.session_state.df_obra[col_custo], errors='coerce').fillna(0.0)
        
        if "taxas" in dados:
            st.session_state.taxas = dados["taxas"]
        
        if dados.get("composicoes"):
            nova_comp = {}
            for idx_str, blocos in dados["composicoes"].items():
                idx_int = int(idx_str)
                nova_comp[idx_int] = {b: pd.read_json(js, orient="split") for b, js in blocos.items()}
            st.session_state.composicoes = nova_comp
        return True
    except Exception as e:
        st.error(f"Erro ao restaurar: {e}")
        return False

# --- 3. BUSCA NA MP ---
def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    col_n = obter_coluna_flexivel(base, ["NOME PRODUTO", "PRODUTO", "DESCRICAO"])
    col_u = obter_coluna_flexivel(base, ["PÇIDADE", "UNID", "UN"])
    col_p = obter_coluna_flexivel(base, ["VLR / PÇ.", "VALOR", "PRECO"])
    
    if not col_n: return None, None
    
    match = base[base[col_n].astype(str).str.strip().str.lower() == termo]
    if match.empty:
        match = base[base[col_n].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        u = str(match[col_u].iloc[0]) if col_u else "un"
        p = float(pd.to_numeric(match[col_p].iloc[0], errors='coerce') or 0.0)
        return u, p
    return "un", 0.0

# --- 4. COMPONENTE DE BLOCO (FRAGMENTO) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_mem = st.session_state.composicoes[idx][chave].reset_index(drop=True)
    df_mem["Código"] = range(1, len(df_mem) + 1)

    df_ed = st.data_editor(df_mem, num_rows="dynamic", use_container_width=True, key=f"v23_{chave}_{idx}_{st.session_state.get('last_load', 0)}")

    if not df_ed.equals(df_mem):
        df_ed = df_ed.reset_index(drop=True)
        df_ed["Código"] = range(1, len(df_ed) + 1)
        for i, r in df_ed.iterrows():
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                u, p = buscar_dados_mp(r['Descrição'])
                if u: df_ed.at[i, 'Unid.'], df_ed.at[i, 'Valor Unit.'] = u, p
            
            q = float(pd.to_numeric(r.get('Quant.'), errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            fat = float(pd.to_numeric(r.get('Fator'), errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            custo = q * vu
            df_ed.at[i, "Valor Total"] = custo
            df_ed.at[i, "Valor Final"] = custo * (1 + (fat/100)) if tipo_fator == "perc" else custo * (fat if fat != 0 else 1)
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 5. DIÁLOGO DE DETALHAMENTO ---
@st.dialog("Composição Técnica", width="large")
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
    st.metric("PREÇO DE VENDA", f"R$ {venda:,.2f}", delta=f"Custo Direto: R$ {c_direto:,.2f}")
    if st.button("💾 Salvar no Orçamento"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 6. INTERFACE ---
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png")
    st.header("💾 Gestão")
    if st.session_state.df_obra is not None:
        st.download_button("📥 Baixar JSON", exportar_projeto_json(), f"orcamento_{datetime.now().strftime('%H%M')}.json")
    
    arq_proj = st.file_uploader("📂 Retomar Projeto", type=["json"])
    if arq_proj and st.button("🔄 Restaurar Dados"):
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
    with c1: arq_o = st.file_uploader("Obra (.xlsm)", type=["xlsx", "xlsm"])
    with c2: arq_m = st.file_uploader("MP (.xlsx)", type=["xlsx", "csv"])
    
    if arq_o and arq_m:
        if st.session_state.df_mp is None:
            st.session_state.df_mp = pd.read_excel(arq_m)
        if st.session_state.df_obra is None:
            df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0).reset_index(drop=True)
            df.columns = [str(c).strip().upper() for c in df.columns]
            df.insert(0, 'STATUS', '⭕')
            df['CUSTO UNITÁRIO FINAL'] = 0.0
            st.session_state.df_obra = df
        
        st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key=f"master_v23_{st.session_state.get('last_load', 0)}")
        idx_sel = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
        if st.button(f"🔎 Detalhar Linha {idx_sel}", type="primary"):
            modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

# --- ABAS DE RELATÓRIO COM TRATAMENTO DE ERRO (KeyError) ---
with tabs[1]:
    st.subheader("Auditoria Analítica")
    dados = []
    if st.session_state.df_obra is not None:
        for i, comps in st.session_state.composicoes.items():
            for g, df in comps.items():
                if not df.empty:
                    df_c = df.copy()
                    col_desc = obter_coluna_flexivel(st.session_state.df_obra, ["DESCRIÇÃO", "NOME", "ITEM"])
                    df_c['Item Master'] = st.session_state.df_obra.at[i, col_desc] if col_desc else "Item"
                    dados.append(df_c)
    if dados: st.dataframe(pd.concat(dados), use_container_width=True)

with tabs[2]:
    st.subheader("Listão de Materiais")
    if dados:
        listao = pd.concat(dados).groupby(['Descrição', 'Unid.']).agg({'Quant.': 'sum'}).reset_index()
        st.dataframe(listao, use_container_width=True)

with tabs[3]:
    st.subheader("Proposta Comercial")
    if st.session_state.df_obra is not None:
        # Resolve o KeyError procurando os nomes reais das colunas
        df_p = st.session_state.df_obra.copy()
        c_desc = obter_coluna_flexivel(df_p, ["DESCRIÇÃO", "NOME"])
        c_unid = obter_coluna_flexivel(df_p, ["UNID", "UN"])
        c_quant = obter_coluna_flexivel(df_p, ["QUANT", "QTD"])
        c_preco = obter_coluna_flexivel(df_p, ["CUSTO UNITÁRIO FINAL", "FINAL"])
        
        # Filtra apenas o que foi orçado
        venda_df = df_p[df_p[c_preco] > 0] if c_preco else pd.DataFrame()
        
        cols_mostrar = [c for c in [c_desc, c_unid, c_quant, c_preco] if c is not None]
        if not venda_df.empty:
            st.table(venda_df[cols_mostrar])
            st.write(f"### TOTAL DO ORÇAMENTO: R$ {venda_df[c_preco].sum():,.2f}")
        else:
            st.info("Nenhum item orçado para exibir na proposta.")
