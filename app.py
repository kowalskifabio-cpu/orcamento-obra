import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v8", layout="wide")

# --- 1. MEMÓRIA DO SISTEMA ---
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

# --- 2. GESTÃO DE PROJETOS (SALVAR/CARREGAR) ---
def exportar_projeto():
    projeto = {
        "df_obra": st.session_state.df_obra.to_json(orient="split") if st.session_state.df_obra is not None else None,
        "composicoes": {str(k): {bloco: df.to_json(orient="split") for bloco, df in v.items()} for k, v in st.session_state.composicoes.items()}
    }
    return json.dumps(projeto)

def importar_projeto(arquivo_json):
    dados = json.load(arquivo_json)
    if dados["df_obra"]: st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
    st.session_state.composicoes = {int(k): {bloco: pd.read_json(js, orient="split") for bloco, js in v.items()} for k, v in dados["composicoes"].items()}

# --- 3. COMPONENTE DE BLOCO TÉCNICO ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.subheader(f"📦 {titulo}")
    df_atual = st.session_state.composicoes[idx][chave]
    
    # Editor Estabilizado
    df_editado = st.data_editor(
        df_atual,
        num_rows="dynamic",
        use_container_width=True,
        key=f"ed_v8_{chave}_{idx}", # Chave única para evitar erro de widget
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # Processamento APENAS se houver mudança detectada
    if not df_editado.equals(df_atual):
        # Reinicia e numera automaticamente
        df_editado = df_editado.reset_index(drop=True)
        df_editado["Código"] = range(1, len(df_editado) + 1)
        
        for i, r in df_editado.iterrows():
            # Busca automática
            if r['Descrição'] and (not r['Unid.'] or r['Unid.'] == "0"):
                u, v = buscar_dados_mp(r['Descrição'])
                if u: 
                    df_editado.at[i, 'Unid.'] = u
                    df_editado.at[i, 'Valor Unit.'] = v
            
            # Cálculos matemáticos protegidos
            q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
            vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
            f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo = q * vu
            df_editado.at[i, "Valor Total"] = custo
            df_editado.at[i, "Valor Final"] = custo * (1 + (f/100)) if tipo_fator == "perc" else custo * f
            
        st.session_state.composicoes[idx][chave] = df_editado
        st.rerun(scope="fragment")
        
    return df_editado["Valor Final"].sum()

# --- 4. DIÁLOGO E INTERFACE ---
@st.dialog("Detalhamento de Composição", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 {linha.get('DESCRIÇÃO', 'Item')}")
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor
