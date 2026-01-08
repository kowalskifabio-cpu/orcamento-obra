import streamlit as st
import pandas as pd
from io import BytesIO
import time

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. MEMÓRIA ESTÁVEL ---
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

# --- 2. MODAL DE COMPOSIÇÃO COM FEEDBACK INSTANTÂNEO ---
@st.dialog("Composição Técnica", width="large")
def abrir_cpu(idx, linha_master):
    st.write(f"### 🛠️ Item: {linha_master.get('DESCRIÇÃO', 'Item')}")
    
    colunas_padrao = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
    
    if idx not in st.session_state.composicoes:
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=colunas_padrao),
            "servico": pd.DataFrame(columns=colunas_padrao),
            "material": pd.DataFrame(columns=colunas_padrao)
        }

    # Bloco de processamento com aviso visual
    def processar_bloco(titulo, chave, tipo_fator):
        st.subheader(f"📦 {titulo}")
        df = st.session_state.composicoes[idx][chave]
        
        # O data_editor agora captura mudanças mais rápido
        df_ed = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{chave}_{idx}",
            column_config={
                "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
                "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
                "Fator": st.column_config.NumberColumn("Fator (%)" if tipo_fator == "perc" else "Fator (x)")
            }
        )

        # Detecta mudança e processa imediatamente
        if not df_ed.equals(df):
            with st.spinner('Processando cálculos...'):
                for i, r in df_ed.iterrows():
                    # Busca automática se a descrição mudou e o valor unitário for 0
                    if r['Descrição'] and (pd.isna(r['Valor Unit.']) or r['Valor Unit.'] == 0):
                        u, c = buscar_dados_mp(r['Descrição'])
                        if u: 
                            df_ed.at[i, 'Unid.'] = u
                            df_ed.at[i, 'Valor Unit.'] = c
                    
                    # Garantia de valores numéricos para evitar erros
                    qtd = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
                    v_u = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
                    fat = float(pd.to_numeric(r['Fator'], errors='coerce') or (1.0 if tipo_fator == "mult" else 0.0))
                    
                    custo_total = qtd * v_u
                    df_ed.at[i, "Valor Total"] = custo_total
                    
                    if tipo_fator == "perc":
                        df_ed.at[i, "Valor Final"] = custo_total * (1 + (fat / 100))
                    else:
                        df_ed.at[i, "Valor Final"] = custo_total * fat
                
                st.session_state.composicoes[idx][chave] = df_ed
                st.toast(f"Cálculos de {titulo} atualizados!", icon="✅")
                st.rerun() # Força a atualização da interface com apenas um Enter
        
        return df_ed["Valor Final"].sum()

    v1 = processar_bloco("Material Terceirizado", "terceirizado", "perc")
    v2 = processar_bloco("Material Terceirizado C/ Serviço", "servico", "mult")
    v3 = processar_bloco("Material", "material", "mult")

    total_item = v1 + v2 + v3
    st.divider()
    st.metric("Total de Venda do Item", f"R$ {total_item:,.2f}")

    if st.button("Salvar Tudo e Sair"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_item
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun()

# --- 3. INTERFACE PRINCIPAL ---
st.title("Orçamentador Profissional")
c1, c2 = st.columns(2)
with c1: arq_obra = st.file_uploader("Upload Obra", type=["xlsx", "csv"])
with c2: arq_mp = st.file_uploader("Upload MP Valores", type=["xlsx", "csv"])

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

    # Planilha Master
    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_editor")
    
    idx_sel = st.number_input("Selecione o índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"Abrir Detalhamento {idx_sel}", type="primary"):
        abrir_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
