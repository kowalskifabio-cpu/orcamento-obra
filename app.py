import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria Pro", layout="wide")

# --- 1. INICIALIZAÇÃO SEGURA DO SISTEMA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    """Busca Unidade e Preço na planilha MP Valores."""
    if st.session_state.df_mp is None or not desc:
        return None, None
    
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    
    # Identifica colunas dinamicamente para evitar erros de nomes
    col_nome = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_unid = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_preco = next((c for c in base.columns if 'VLR / PÇ.' in c.upper() or 'VLR/PÇ' in c.upper()), None)

    if not col_nome: return None, None

    # Busca exata ou por aproximação
    match = base[base[col_nome].astype(str).str.strip().str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        u = str(match[col_unid].iloc[0]) if col_unid else "un"
        p = float(pd.to_numeric(match[col_preco].iloc[0], errors='coerce') or 0.0)
        return u, p
    return "un", 0.0

# --- 2. COMPONENTE DE BLOCO (AUTOMAÇÃO TOTAL) ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    
    # Busca dados na memória e garante que a coluna Código esteja lá
    df_atual = st.session_state.composicoes[idx][chave]
    df_atual = df_atual.reset_index(drop=True)
    df_atual["Código"] = range(1, len(df_atual) + 1)

    # Editor de Dados Estabilizado
    df_ed = st.data_editor(
        df_atual,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_v14_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # Lógica Automática ao mudar a tabela
    if not df_ed.equals(df_atual):
        # 1. Re-numera Código 1, 2, 3...
        df_ed["Código"] = range(1, len(df_ed) + 1)
        
        # 2. Processa buscas e cálculos matemáticos seguros
        for i, r in df_ed.iterrows():
            # Busca MP automática se o nome mudar
            if r.get('Descrição') and (pd.isna(r.get('Valor Unit.')) or r.get('Valor Unit.') == 0):
                unid, preco = buscar_dados_mp(r['Descrição'])
                if unid:
                    df_ed.at[i, 'Unid.'] = unid
                    df_ed.at[i, 'Valor Unit.'] = preco
            
            # Cálculos protegidos contra TypeError (converte None para 0)
            q = float(pd.to_numeric(r.get('Quant.'), errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            fat = float(pd.to_numeric(r.get('Fator'), errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo_t = q * vu
            df_ed.at[i, "Valor Total"] = custo_t
            
            if tipo_fator == "perc":
                df_ed.at[i, "Valor Final"] = custo_t * (1 + (fat / 100))
            else:
                df_ed.at[i, "Valor Final"] = custo_t * (fat if fat != 0 else 1)
        
        # Salva na memória e atualiza APENAS o fragmento (mantém a caixa aberta)
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment")

    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 3. DIÁLOGO (POP-UP) ---
@st.dialog("Detalhamento da Composição", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 {linha.get('DESCRIÇÃO', 'Item')}")
    
    # Inicializa sub-tabelas se for a primeira vez
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material", "mult")
    
    total = v1 + v2 + v3
    st.divider()
    st.metric("PREÇO DE VENDA TOTAL DO ITEM", f"R$ {total:,.2f}")
    
    if st.button("💾 Salvar e Atualizar Planilha Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 4. GESTÃO DE PROJETOS E UI ---
def exportar_projeto():
    proj = {
        "df_obra": st.session_state.df_obra.to_json(orient="split") if st.session_state.df_obra is not None else None,
        "composicoes": {str(k): {b: df.to_json(orient="split") for b, df in v.items()} for k, v in st.session_state.composicoes.items()}
    }
    return json.dumps(proj)

st.title("🏗️ Orçamentador Profissional v14")

with st.sidebar:
    st.header("💾 Gestão de Trabalho")
    if st.session_state.df_obra is not None:
        st.download_button("📥 Baixar Arquivo de Projeto (.json)", exportar_projeto(), "projeto.json")
    
    arq_proj = st.file_uploader("📂 Retomar Projeto Salvo", type=["json"])
    if arq_proj and st.button("🔄 Restaurar Dados"):
        dados = json.load(arq_proj)
        if dados["df_obra"]: st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
        st.session_state.composicoes = {int(k): {b: pd.read_json(js, orient="split") for b, js in v.items()} for k, v in dados["composicoes"].items()}
        st.rerun()

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("1. Planilha da Construtora", type=["xlsx", "csv"])
with c2: arq_m = st.file_uploader("2. Planilha MP Valores", type=["xlsx", "csv"])

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

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_master")
    
    idx_sel = st.number_input("Índice da linha para detalhar:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

    if st.button("📊 Exportar Excel Final"):
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            st.session_state.df_obra.to_excel(writer, index=False)
        st.download_button("💾 Baixar Excel Orçado", out.getvalue(), "Orcamento_Final.xlsx")
