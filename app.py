import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v17", layout="wide")

# --- 1. INICIALIZAÇÃO DE MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# Valores padrão para as taxas (caso não existam no JSON)
if 'taxas' not in st.session_state:
    st.session_state.taxas = {"imposto": 15.0, "frete": 3.0, "comissao": 5.0, "lucro": 20.0}

# --- 2. FUNÇÕES DE PERSISTÊNCIA (SALVAR/CARREGAR) CORRIGIDAS ---
def exportar_projeto_json():
    """Gera o arquivo de salvamento completo incluindo taxas e composições."""
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
    """Restaura o projeto e converte chaves de texto para inteiro."""
    try:
        dados = json.load(arquivo_json)
        # 1. Restaura Planilha Master
        if dados["df_obra"]:
            st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
        
        # 2. Restaura Taxas da Lateral
        if "taxas" in dados:
            st.session_state.taxas = dados["taxas"]
            
        # 3. Restaura Composições Detalhadas (Corrigindo o erro de string/int)
        nova_comp = {}
        for idx_str, blocos in dados["composicoes"].items():
            idx_int = int(idx_str) # Converte "0" para 0
            nova_comp[idx_int] = {
                nome_bloco: pd.read_json(conteudo_json, orient="split") 
                for nome_bloco, conteudo_json in blocos.items()
            }
        st.session_state.composicoes = nova_comp
        return True
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {e}")
        return False

# --- 3. BARRA LATERAL (GESTÃO E TAXAS) ---
with st.sidebar:
    st.header("💾 Gestão do Projeto")
    
    # Botão de Download (Aparece se houver dados)
    if st.session_state.df_obra is not None:
        json_data = exportar_projeto_json()
        st.download_button(
            label="📥 Baixar Projeto Atual (.json)",
            data=json_data,
            file_name="projeto_orcamento.json",
            mime="application/json"
        )
    
    # Upload para retomar
    st.divider()
    st.subheader("Retomar Trabalho")
    arq_subido = st.file_uploader("Subir arquivo JSON", type=["json"])
    if arq_subido:
        if st.button("🔄 Restaurar Dados Agora"):
            if carregar_projeto_json(arq_subido):
                st.success("Projeto carregado!")
                st.rerun()

    st.divider()
    st.header("⚖️ Taxas Globais (BDI)")
    st.session_state.taxas["imposto"] = st.number_input("Impostos (%)", value=st.session_state.taxas["imposto"])
    st.session_state.taxas["frete"] = st.number_input("Frete (%)", value=st.session_state.taxas["frete"])
    st.session_state.taxas["comissao"] = st.number_input("Comissão (%)", value=st.session_state.taxas["comissao"])
    st.session_state.taxas["lucro"] = st.number_input("Margem Lucro (%)", value=st.session_state.taxas["lucro"])

# --- 4. BUSCA E CÁLCULOS ---
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
        df_memoria, num_rows="dynamic", use_container_width=True, key=f"ed_v17_{chave}_{idx}",
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

# --- 5. MODAL DE FECHAMENTO ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 Detalhando: {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    custo_direto = v1 + v2 + v3
    
    # Cálculo de BDI baseado nas taxas da lateral
    tx = st.session_state.taxas
    bdi_total = tx["imposto"] + tx["frete"] + tx["comissao"] + tx["lucro"]
    preco_venda_final = custo_direto * (1 + (bdi_total / 100))

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Custo Direto Acumulado", f"R$ {custo_direto:,.2f}")
    c2.metric("Venda Final (com BDI)", f"R$ {preco_venda_final:,.2f}", delta=f"BDI: {bdi_total}%")

    if st.button("✅ Confirmar e Salvar no Master"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = preco_venda_final
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 6. TELA PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional v17")

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

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_v17")
    idx_sel = st.number_input("Índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
