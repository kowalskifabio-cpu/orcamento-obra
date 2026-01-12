import streamlit as st
import pandas as pd

st.set_page_config(page_title="Orçamentador Marcenaria v6", layout="wide")

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

# --- 2. COMPONENTE DE BLOCO (FRAGMENTO) ---
@st.fragment
def renderizar_bloco_com_calculos(idx, chave, titulo, tipo_fator):
    st.subheader(f"📦 {titulo}")
    
    # Busca o DF atual da memória
    df = st.session_state.composicoes[idx][chave]
    
    # FORÇA A NUMERAÇÃO AUTOMÁTICA ANTES DE MOSTRAR
    if len(df) > 0:
        df = df.reset_index(drop=True)
        df["Código"] = range(1, len(df) + 1)

    # Exibe o Editor
    df_ed = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item #", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # Se a tabela mudou, processamos e salvamos
    if not df_ed.equals(df):
        for i, r in df_ed.iterrows():
            # Numeração garantida na edição
            df_ed.at[i, "Código"] = i + 1
            
            # Busca automática
            if r['Descrição'] and (not r['Unid.'] or r['Unid.'] == "0"):
                u, c = buscar_dados_mp(r['Descrição'])
                if u:
                    df_ed.at[i, 'Unid.'] = u
                    df_ed.at[i, 'Valor Unit.'] = c
            
            # Cálculos
            q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
            vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
            f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo = q * vu
            df_ed.at[i, "Valor Total"] = custo
            
            if tipo_fator == "perc":
                df_ed.at[i, "Valor Final"] = custo * (1 + (f / 100))
            else:
                df_ed.at[i, "Valor Final"] = custo * f
        
        st.session_state.composicoes[idx][chave] = df_ed
        st.rerun(scope="fragment") # Agora o rerun está protegido pelo fragmento isolado

    return df_ed["Valor Final"].sum()

# --- 3. DIÁLOGO PRINCIPAL ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha_master):
    st.write(f"### 📋 Item: {linha_master.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=cols),
            "servico": pd.DataFrame(columns=cols),
            "material": pd.DataFrame(columns=cols)
        }

    # Renderiza cada bloco de forma independente
    v1 = renderizar_bloco_com_calculos(idx, "terceirizado", "Material Terceirizado", "perc")
    v2 = renderizar_bloco_com_calculos(idx, "servico", "Material Terceirizado C/ Serviço", "mult")
    v3 = renderizar_bloco_com_calculos(idx, "material", "Material", "mult")

    st.divider()
    total = v1 + v2 + v3
    st.metric("TOTAL DE VENDA", f"R$ {total:,.2f}")

    if st.button("💾 Finalizar e Salvar na Planilha", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app")

# --- 4. TELA PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional")

c1, c2 = st.columns(2)
with c1: arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with c2: arq_mp = st.file_uploader("2. MP Valores (Listão)", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_mp is None:
        df_mp = pd.read_csv(arq_mp) if arq_mp.name.endswith('.csv') else pd.read_excel(arq_mp)
        df_mp.columns = [str(c).strip() for c in df_mp.columns]
        st.session_state.df_mp = df_mp

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df

    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_editor")
    
    idx_sel = st.number_input("Índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
