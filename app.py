import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Orçamentador Marcenaria Pro", layout="wide")

# --- 1. MEMÓRIA DO SISTEMA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}
if 'taxas' not in st.session_state:
    st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "lucro": 20.0, "comissao": 5.0}

# --- 2. FUNÇÕES DE BUSCA E APOIO ---
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

def exportar_projeto_json():
    projeto = {
        "df_obra": st.session_state.df_obra.to_json(orient="split") if st.session_state.df_obra is not None else None,
        "taxas": st.session_state.taxas,
        "composicoes": {str(k): {b: df.to_json(orient="split") for b, df in v.items()} for k, v in st.session_state.composicoes.items()}
    }
    return json.dumps(projeto)

# --- 3. COMPONENTE DE BLOCO TÉCNICO (FRAGMENTO) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_memoria = st.session_state.composicoes[idx][chave].reset_index(drop=True)
    df_memoria["Código"] = range(1, len(df_memoria) + 1)

    df_ed = st.data_editor(df_memoria, num_rows="dynamic", use_container_width=True, key=f"ed_v19_{chave}_{idx}")

    if not df_ed.equals(df_memoria):
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

# --- 4. DIÁLOGO DE COMPOSIÇÃO ---
@st.dialog("Composição Técnica (CPU)", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 Item: {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    c_direto = v1 + v2 + v3
    bdi_total = sum(st.session_state.taxas.values())
    venda_final = c_direto * (1 + (bdi_total / 100))

    st.divider()
    st.metric("PREÇO DE VENDA FINAL", f"R$ {venda_final:,.2f}", delta=f"Custo Direto: R$ {c_direto:,.2f}")
    if st.button("💾 Salvar no Orçamento Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda_final
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 5. INTERFACE PRINCIPAL ---
with st.sidebar:
    # Correção do erro MediaFileStorageError
    if os.path.exists("logo.png"):
        st.image("logo.png")
    else:
        st.title("🪚 Marcenaria Pro")
    
    st.header("⚙️ Configurações Globais (%)")
    for k in st.session_state.taxas:
        st.session_state.taxas[k] = st.number_input(f"{k.capitalize()}", value=st.session_state.taxas[k])
    
    st.divider()
    if st.session_state.df_obra is not None:
        st.download_button("📥 Salvar Progresso (.json)", exportar_projeto_json(), "projeto_orcamento.json")

st.title("🏗️ Sistema de Orçamentação e Produção")

tabs = st.tabs(["📝 Orçamento Master", "🔍 Relatório Analítico", "🛒 Listão de Compras", "📄 Proposta Comercial"])

# TAB 1: ORÇAMENTO MASTER
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1: arq_o = st.file_uploader("Subir Planilha Obra", type=["xlsx", "xlsm"])
    with c2: arq_m = st.file_uploader("Subir MP Valores", type=["xlsx", "csv"])

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

        st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_table")
        idx_sel = st.number_input("Selecione o índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
        if st.button(f"🔎 Detalhar Item {idx_sel}", type="primary"):
            modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

# TAB 2: RELATÓRIO ANALÍTICO (AUDITORIA)
with tabs[1]:
    st.subheader("Auditoria de Composições (Explosão de Itens)")
    dados_explodidos = []
    for idx, comps in st.session_state.composicoes.items():
        master_desc = st.session_state.df_obra.at[idx, 'DESCRIÇÃO']
        for grupo, df in comps.items():
            if not df.empty:
                df_c = df.copy()
                df_c['Item Master'] = master_desc
                df_c['Categoria'] = grupo.upper()
                dados_explodidos.append(df_c)
    
    if dados_explodidos:
        df_total = pd.concat(dados_explodidos)
        st.dataframe(df_total[['Item Master', 'Categoria', 'Descrição', 'Quant.', 'Unid.', 'Valor Unit.', 'Valor Final']], use_container_width=True)
    else:
        st.info("Nenhum item detalhado para auditoria.")

# TAB 3: LISTÃO DE COMPRAS
with tabs[2]:
    st.subheader("Consolidado de Materiais para Compra")
    if dados_explodidos:
        listao = pd.concat(dados_explodidos).groupby(['Descrição', 'Unid.']).agg({'Quant.': 'sum', 'Valor Unit.': 'mean'}).reset_index()
        st.dataframe(listao, use_container_width=True)
        # Exportar Listão
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            listao.to_excel(writer, index=False, sheet_name='Compras')
        st.download_button("💾 Baixar Listão em Excel", out.getvalue(), "listao_compras.xlsx")
    else:
        st.info("Adicione itens na composição para gerar o listão.")

# TAB 4: PROPOSTA COMERCIAL
with tabs[3]:
    st.subheader("Visualização da Proposta Comercial")
    if st.session_state.df_obra is not None:
        st.markdown(f"### PROPOSTA: {datetime.now().strftime('%d/%m/%Y')}")
        orc_final = st.session_state.df_obra[st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] > 0]
        st.table(orc_final[['DESCRIÇÃO', 'UNID', 'QUANT', 'CUSTO UNITÁRIO FINAL']])
        
        total_geral = orc_final['CUSTO UNITÁRIO FINAL'].sum()
        st.markdown(f"## TOTAL GERAL: R$ {total_geral:,.2f}")
    else:
        st.info("Carregue o projeto para visualizar a proposta.")
