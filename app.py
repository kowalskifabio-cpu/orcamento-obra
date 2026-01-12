import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v9", layout="wide")

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

# --- 2. FUNÇÃO DE CÁLCULO (O "CÉREBRO" DO SISTEMA) ---
def processar_calculos_bloco(df_editado, tipo_fator):
    """Gera códigos automáticos, busca preços e calcula totais."""
    # 1. Renumeração automática
    df_editado = df_editado.reset_index(drop=True)
    df_editado["Código"] = range(1, len(df_editado) + 1)
    
    for i, r in df_editado.iterrows():
        # 2. Busca automática de Preço e Unidade
        if r['Descrição'] and (pd.isna(r['Valor Unit.']) or r['Valor Unit.'] == 0):
            u, v = buscar_dados_mp(r['Descrição'])
            if u: 
                df_editado.at[i, 'Unid.'] = u
                df_editado.at[i, 'Valor Unit.'] = v
        
        # 3. Matemática de Custo e Venda
        q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
        vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
        f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
        
        custo = q * vu
        df_editado.at[i, "Valor Total"] = custo
        
        if tipo_fator == "perc":
            df_editado.at[i, "Valor Final"] = custo * (1 + (f / 100))
        else:
            df_editado.at[i, "Valor Final"] = custo * f
            
    return df_editado

# --- 3. COMPONENTE DE BLOCO TÉCNICO ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.subheader(f"📦 {titulo}")
    
    # Exibe o Editor
    df_ed = st.data_editor(
        st.session_state.composicoes[idx][chave],
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_v9_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # BOTÃO PARA ATUALIZAR (Gera código, busca preço e calcula)
    if st.button(f"🔄 Atualizar {titulo}", key=f"btn_calc_{chave}_{idx}"):
        df_processado = processar_calculos_bloco(df_ed, tipo_fator)
        st.session_state.composicoes[idx][chave] = df_processado
        st.rerun(scope="fragment")
        
    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 4. DIÁLOGO PRINCIPAL ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha):
    st.write(f"### 📋 {linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {b: pd.DataFrame(columns=cols) for b in ["terceirizado", "servico", "material"]}
    
    v1 = renderizar_bloco(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco(idx, "servico", "Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco(idx, "material", "Material Puro", "mult")
    
    total = v1 + v2 + v3
    st.divider()
    st.metric("TOTAL DO ITEM (VENDA)", f"R$ {total:,.2f}")
    
    if st.button("💾 Finalizar e Salvar Tudo", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- UI PRINCIPAL ---
st.title("Orçamentador Marcenaria Profissional")

# Sidebar para Salvar/Carregar JSON (Manter conforme código v8)
with st.sidebar:
    st.header("⚙️ Gerenciar Projeto")
    # ... (lógica de salvar/carregar JSON aqui)

c1, c2 = st.columns(2)
with c1: arq_o = st.file_uploader("Upload Planilha Construtora", type=["xlsx", "csv"])
with c2: arq_m = st.file_uploader("Upload MP Valores", type=["xlsx", "csv"])

if arq_o and arq_m:
    if st.session_state.df_mp is None:
        st.session_state.df_mp = pd.read_excel(arq_m) if arq_m.name.endswith('.xlsx') else pd.read_csv(arq_m)
        st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_o, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]; df.insert(0, 'STATUS', '⭕'); df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_v9")
    idx = st.number_input("Índice da Linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento da Linha {idx}", type="primary"):
        modal_cpu(idx, st.session_state.df_obra.iloc[idx])
