import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v18", layout="wide")

# --- 1. INICIALIZAÇÃO DE MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}
if 'taxas' not in st.session_state:
    st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "comissao": 5.0, "lucro": 20.0}

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
    return json.dumps(projeto)

def carregar_projeto_json(arquivo_json):
    try:
        dados = json.load(arquivo_json)
        if dados["df_obra"]:
            # Restaura e força o reset do índice para garantir sincronia
            df_restaurado = pd.read_json(dados["df_obra"], orient="split")
            st.session_state.df_obra = df_restaurado.reset_index(drop=True)
        
        if "taxas" in dados:
            st.session_state.taxas = dados["taxas"]
            
        nova_comp = {}
        for idx_str, blocos in dados["composicoes"].items():
            idx_int = int(idx_str)
            nova_comp[idx_int] = {
                nome_bloco: pd.read_json(conteudo_json, orient="split") 
                for nome_bloco, conteudo_json in blocos.items()
            }
        st.session_state.composicoes = nova_comp
        return True
    except Exception as e:
        st.error(f"Erro na restauração: {e}")
        return False

# --- 3. COMPONENTE DE BLOCO TÉCNICO (v15+) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    df_memoria = st.session_state.composicoes[idx][chave]
    
    # Garante que a sequência 1, 2, 3... funcione desde a primeira linha
    df_memoria = df_memoria.reset_index(drop=True)
    df_memoria["Código"] = range(1, len(df_memoria) + 1)

    df_ed = st.data_editor(
        df_memoria, num_rows="dynamic", use_container_width=True, key=f"v18_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Venda", disabled=True, format="R$ %.2f"),
        }
    )

    if not df_ed.equals(df_memoria):
        # Processamento automático de sequência e cálculos
        df_ed = df_ed.reset_index(drop=True)
        df_ed["Código"] = range(1, len(df_ed) + 1)
        for i, r in df_ed.iterrows():
            # Busca MP
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                u, p = buscar_dados_mp(r['Descrição'])
                if u: df_ed.at[i, 'Unid.'], df_ed.at[i, 'Valor Unit.'] = u, p
            
            # Matemática Segura
            q = float(pd.to_numeric(r.get('Quant.'), errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            fat = float(pd.to_numeric(r.get('Fator'), errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo_t = q * vu
            df_ed.at[i, "Valor Total"] = custo_t
            df_ed.at[i, "Valor Final"] = custo_t * (1 + (fat/100)) if tipo_fator == "perc" else custo_t * (fat if fat != 0 else 1)
            
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. BUSCA E DIÁLOGO ---
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

@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 Detalhando: {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    custo_d = v1 + v2 + v3
    bdi = sum(st.session_state.taxas.values())
    venda_f = custo_d * (1 + (bdi / 100))

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Custo Direto", f"R$ {custo_d:,.2f}")
    c2.metric("Venda Final (BDI)", f"R$ {venda_f:,.2f}")

    if st.button("✅ Salvar no Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda_f
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 5. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional v18")

with st.sidebar:
    st.header("💾 Gestão")
    if st.session_state.df_obra is not None:
        st.download_button("📥 Baixar JSON", exportar_projeto_json(), "projeto.json")
    
    arq_json = st.file_uploader("📂 Retomar JSON", type=["json"])
    if arq_json and st.button("Restaurar"):
        if carregar_projeto_json(arq_json): st.rerun()

    st.divider()
    st.header("⚖️ Taxas (BDI)")
    for k in st.session_state.taxas:
        st.session_state.taxas[k] = st.number_input(f"{k.capitalize()} (%)", value=st.session_state.taxas[k])

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("1. Planilha Obra", type=["xlsx", "xlsm"])
with c2: arq_m = st.file_uploader("2. MP Valores", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        # RESET DE ÍNDICE CRÍTICO PARA FUNCIONAR A LINHA 0
        st.session_state.df_obra = df.reset_index(drop=True)
        st.session_state.df_obra.insert(0, 'STATUS', '⭕')
        st.session_state.df_obra['CUSTO UNITÁRIO FINAL'] = 0.0

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_v18")
    idx_sel = st.number_input("Índice:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Detalhar Linha {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
