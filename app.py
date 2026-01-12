import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v16", layout="wide")

# --- 1. MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# --- 2. CONFIGURAÇÕES TRIBUTÁRIAS E LOGÍSTICAS (Baseado na aba Tributos/Resumo) ---
with st.sidebar:
    st.header("⚖️ Impostos e Taxas (BDI)")
    st.session_state.perc_imposto = st.number_input("Tributos/Impostos (%)", value=15.0, step=0.5)
    st.session_state.perc_frete = st.number_input("Frete/Logística (%)", value=3.0, step=0.1)
    st.session_state.perc_comissao = st.number_input("Comissão/Vendas (%)", value=5.0, step=0.5)
    st.session_state.margem_lucro = st.number_input("Margem de Lucro Desejada (%)", value=20.0, step=1.0)
    
    st.divider()
    st.info("Estas taxas serão aplicadas sobre o Custo Direto Total para gerar o Preço de Venda Final.")

# --- 3. FUNÇÕES DE BUSCA E CÁLCULO (Versão Estável v15+) ---
def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    col_nome = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_unid = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_preco = next((c for c in base.columns if 'VLR / PÇ.' in c.upper() or 'VLR/PÇ' in c.upper()), None)
    if not col_nome: return None, None
    match = base[base[col_nome].astype(str).str.strip().str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    if not match.empty:
        u = str(match[col_unid].iloc[0]) if col_unid else "un"
        p = float(pd.to_numeric(match[col_preco].iloc[0], errors='coerce') or 0.0)
        return u, p
    return "un", 0.0

@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_memoria = st.session_state.composicoes[idx][chave]
    if len(df_memoria) > 0:
        df_memoria = df_memoria.reset_index(drop=True)
        df_memoria["Código"] = range(1, len(df_memoria) + 1)

    df_ed = st.data_editor(
        df_memoria, num_rows="dynamic", use_container_width=True, key=f"ed_v16_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    if not df_ed.equals(df_memoria):
        df_ed["Código"] = range(1, len(df_ed) + 1)
        for i, r in df_ed.iterrows():
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                unid, preco = buscar_dados_mp(r['Descrição'])
                if unid: df_ed.at[i, 'Unid.'], df_ed.at[i, 'Valor Unit.'] = unid, preco
            q = float(pd.to_numeric(r.get('Quant.'), errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            fat = float(pd.to_numeric(r.get('Fator'), errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            custo_t = q * vu
            df_ed.at[i, "Valor Total"] = custo_t
            df_ed.at[i, "Valor Final"] = custo_t * (1 + (fat / 100)) if tipo_fator == "perc" else custo_t * (fat if fat != 0 else 1)
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. MODAL COM CÁLCULO DE IMPOSTOS ---
@st.dialog("Composição Técnica e Fechamento", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 Detalhando: {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    custo_direto_detalhado = v1 + v2 + v3
    
    # Aplicação das Taxas Globais (Regra de Negócio da Planilha Modelo)
    fator_bdi = 1 + ((st.session_state.perc_imposto + st.session_state.perc_frete + st.session_state.perc_comissao + st.session_state.margem_lucro) / 100)
    venda_com_impostos = custo_direto_detalhado * fator_bdi

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Custo Direto", f"R$ {custo_direto_detalhado:,.2f}")
    c2.metric("Preço com BDI/Impostos", f"R$ {venda_com_impostos:,.2f}", delta=f"{fator_bdi-1:.1%}")
    
    if st.button("💾 Salvar e Atualizar Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda_com_impostos
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 5. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional v16")

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("1. Planilha da Construtora", type=["xlsx", "xlsm"])
with c2: arq_m = st.file_uploader("2. MP Valores", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m) if arq_m.name.endswith('.xlsx') else pd.read_csv(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_v16")
    idx_sel = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento da Linha {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
