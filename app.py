import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Orçamentador Marcenaria v20", layout="wide")

# --- 1. INICIALIZAÇÃO DE MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}
if 'taxas' not in st.session_state:
    st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "lucro": 20.0, "comissao": 5.0}

# --- 2. FUNÇÕES DE PERSISTÊNCIA (JSON) ---
def exportar_projeto_json():
    """Gera o arquivo de salvamento completo."""
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
    """Restaura o projeto do zero."""
    try:
        dados = json.load(arquivo_json)
        if dados["df_obra"]:
            st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split").reset_index(drop=True)
        if "taxas" in dados:
            st.session_state.taxas = dados["taxas"]
        
        # Converte chaves de string para int ao restaurar
        st.session_state.composicoes = {
            int(k): {b: pd.read_json(js, orient="split") for b, js in v.items()} 
            for k, v in dados["composicoes"].items()
        }
        st.success("✅ Projeto Restaurado com Sucesso!")
    except Exception as e:
        st.error(f"Erro ao carregar projeto: {e}")

# --- 3. BARRA LATERAL (GESTÃO E LOGO) ---
with st.sidebar:
    # Tenta carregar a logo, se falhar usa texto
    if os.path.exists("logo.png"):
        st.image("logo.png")
    else:
        st.title("🪚 Marcenaria Pro")
    
    st.header("💾 Salvar/Carregar Projeto")
    
    # Botão para Baixar (Salvar)
    if st.session_state.df_obra is not None:
        st.download_button(
            label="📥 Baixar Arquivo de Projeto (Backup)",
            data=exportar_projeto_json(),
            file_name=f"projeto_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            help="Clique aqui para salvar seu progresso no computador."
        )
    
    # Upload para Carregar
    st.divider()
    st.subheader("Retomar Trabalho")
    arq_subido = st.file_uploader("Subir arquivo .json", type=["json"])
    if arq_subido and st.button("🔄 Restaurar Dados"):
        carregar_projeto_json(arq_subido)
        st.rerun()

    st.divider()
    st.header("⚖️ Taxas Globais (%)")
    for k in st.session_state.taxas:
        st.session_state.taxas[k] = st.number_input(f"{k.capitalize()}", value=st.session_state.taxas[k])

# --- 4. FUNÇÕES DE BUSCA E BLOCOS ---
def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    col_nome = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_unid = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_preco = next((c for c in base.columns if 'VLR / PÇ.' in c.upper()), None)
    if not col_nome: return None, None
    match = base[base[col_nome].astype(str).str.strip().str.lower() == termo]
    if match.empty: match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    if not match.empty:
        return str(match[col_unid].iloc[0]), float(pd.to_numeric(match[col_preco].iloc[0], errors='coerce') or 0.0)
    return "un", 0.0

@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_mem = st.session_state.composicoes[idx][chave].reset_index(drop=True)
    df_mem["Código"] = range(1, len(df_mem) + 1)

    df_ed = st.data_editor(df_mem, num_rows="dynamic", use_container_width=True, key=f"ed_v20_{chave}_{idx}")

    if not df_ed.equals(df_mem):
        df_ed = df_ed.reset_index(drop=True)
        df_ed["Código"] = range(1, len(df_ed) + 1)
        for i, r in df_ed.iterrows():
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                u, p = buscar_dados_mp(r['Descrição'])
                if u: df_ed.at[i, 'Unid.'], df_ed.at[i, 'Valor Unit.'] = u, p
            q, vu = float(pd.to_numeric(r.get('Quant.'), 0)), float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], 0))
            fat = float(pd.to_numeric(r.get('Fator'), 0) or (0.0 if tipo_fator == "perc" else 1.0))
            custo = q * vu
            df_ed.at[i, "Valor Total"] = custo
            df_ed.at[i, "Valor Final"] = custo * (1 + (fat/100)) if tipo_fator == "perc" else custo * (fat if fat != 0 else 1)
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 5. DIÁLOGOS E TABS ---
@st.dialog("Composição Técnica (CPU)", width="large")
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
    if st.button("💾 Salvar no Master"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 6. INTERFACE PRINCIPAL ---
tabs = st.tabs(["📝 Orçamento", "🔍 Auditoria Analítica", "🛒 Listão de Compras", "📄 Proposta"])

with tabs[0]:
    c1, c2 = st.columns(2)
    with c1: arq_o = st.file_uploader("Planilha Obra", type=["xlsx", "xlsm"])
    with c2: arq_m = st.file_uploader("MP Valores", type=["xlsx", "csv"])
    if arq_o and arq_m:
        if st.session_state.df_mp is None:
            st.session_state.df_mp = pd.read_excel(arq_m)
            st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
        if st.session_state.df_obra is None:
            df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
            df.columns = [str(c).upper() for c in df.columns]
            st.session_state.df_obra = df.reset_index(drop=True)
            st.session_state.df_obra.insert(0, 'STATUS', '⭕')
            st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_v20")
        idx_sel = st.number_input("Índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
        if st.button(f"🔎 Detalhar Linha {idx_sel}", type="primary"):
            modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

with tabs[1]:
    st.subheader("Auditoria Analítica (Explosão de Itens)")
    dados = []
    for i, comps in st.session_state.composicoes.items():
        for g, df in comps.items():
            if not df.empty:
                df_c = df.copy(); df_c['Item Master'] = st.session_state.df_obra.at[i, 'DESCRIÇÃO']; dados.append(df_c)
    if dados: st.dataframe(pd.concat(dados), use_container_width=True)

with tabs[2]:
    st.subheader("Listão de Materiais")
    if dados:
        listao = pd.concat(dados).groupby(['Descrição', 'Unid.']).agg({'Quant.': 'sum'}).reset_index()
        st.dataframe(listao, use_container_width=True)

with tabs[3]:
    st.subheader("Proposta Comercial")
    if st.session_state.df_obra is not None:
        venda_df = st.session_state.df_obra[st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] > 0]
        st.table(venda_df[['DESCRIÇÃO', 'UNID', 'QUANT', 'CUSTO UNITÁRIO FINAL']])
        st.write(f"### TOTAL GERAL: R$ {venda_df['CUSTO UNITÁRIO FINAL'].sum():,.2f}")
