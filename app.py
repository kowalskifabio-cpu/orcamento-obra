import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Marcenaria v12", layout="wide")

# --- 1. MEMÓRIA E BUSCA ROBUSTA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc:
        return None, None
    
    # Limpa o texto digitado
    termo = str(desc).strip().lower()
    base = st.session_state.df_mp.copy()
    
    # Identifica as colunas alvo (independente de espaços extras no Excel)
    col_nome = next((c for c in base.columns if 'NOME PRODUTO' in c.upper()), None)
    col_unid = next((c for c in base.columns if 'PÇIDADE' in c.upper()), None)
    col_preco = next((c for c in base.columns if 'VLR / PÇ.' in c.upper() or 'VLR/PÇ' in c.upper()), None)

    if not col_nome:
        return None, None

    # Tenta busca exata primeiro, depois parcial (contains)
    match = base[base[col_nome].astype(str).str.strip().str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        u = str(match[col_unid].iloc[0]) if col_unid else "un"
        # Converte o preço da coluna F para número
        p = float(pd.to_numeric(match[col_preco].iloc[0], errors='coerce') or 0.0) if col_preco else 0.0
        return u, p
    
    return "N/A", 0.0

# --- 2. COMPONENTE DE BLOCO TÉCNICO ---
@st.fragment
def renderizar_bloco(idx, chave, titulo, tipo_fator):
    st.markdown(f"#### 📦 {titulo}")
    
    df_memoria = st.session_state.composicoes[idx][chave]
    
    # Numeração automática preventiva
    if len(df_memoria) > 0:
        df_memoria = df_memoria.reset_index(drop=True)
        df_memoria["Código"] = range(1, len(df_memoria) + 1)

    df_ed = st.data_editor(
        df_memoria,
        num_rows="dynamic",
        use_container_width=True,
        key=f"ed_v12_{chave}_{idx}",
        column_config={
            "Código": st.column_config.NumberColumn("Item", disabled=True),
            "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
            "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
            "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Mult. x")
        }
    )

    # BOTÃO CALCULAR: Agora com busca reforçada
    if st.button(f"Calcular {titulo}", key=f"btn_v12_{chave}_{idx}"):
        df_ed = df_ed.reset_index(drop=True)
        itens_encontrados = 0
        
        for i, r in df_ed.iterrows():
            df_ed.at[i, "Código"] = i + 1
            desc_digitada = r.get('Descrição')
            
            # Só busca se tiver descrição e o valor estiver zerado ou for novo
            if desc_digitada:
                unid, preco = buscar_dados_mp(desc_digitada)
                if unid and unid != "N/A":
                    df_ed.at[i, 'Unid.'] = unid
                    df_ed.at[i, 'Valor Unit.'] = preco
                    itens_encontrados += 1
            
            # Cálculos de matemática
            q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
            vu = float(pd.to_numeric(df_ed.at[i, 'Valor Unit.'], errors='coerce') or 0.0)
            f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
            
            custo_total = q * vu
            df_ed.at[i, "Valor Total"] = custo_total
            if tipo_fator == "perc":
                df_ed.at[i, "Valor Final"] = custo_total * (1 + (f / 100))
            else:
                df_ed.at[i, "Valor Final"] = custo_total * (f if f != 0 else 1)
        
        st.session_state.composicoes[idx][chave] = df_ed
        if itens_encontrados > 0:
            st.toast(f"{itens_encontrados} itens localizados na MP!", icon="🔍")
        else:
            st.toast("Nenhum item novo encontrado na MP.", icon="⚠️")
        st.rerun(scope="fragment")

    return st.session_state.composicoes[idx][chave]["Valor Final"].sum()

# --- 3. RESTANTE DO CÓDIGO (DIÁLOGO E UI) ---
# Mantenha as funções modal_cpu, exportar_projeto e a interface principal conforme a v11.
# Garanta que o carregamento da planilha MP limpe os nomes das colunas:
# st.session_state.df_mp.columns = [str(c).strip() for c in st.session_state.df_mp.columns]
