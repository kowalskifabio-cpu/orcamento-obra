import streamlit as st
import pandas as pd
from io import BytesIO
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# --- 2. FUNÇÃO DE BUSCA NA BASE MP ---
def buscar_dados_mp(descricao_pesquisada):
    if st.session_state.df_mp is None or not descricao_pesquisada:
        return None, None
    base = st.session_state.df_mp
    termo = str(descricao_pesquisada).strip().lower()
    col_nome = 'NOME PRODUTO' if 'NOME PRODUTO' in base.columns else base.columns[1]
    
    match = base[base[col_nome].astype(str).str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        unid = str(match['PÇIDADE'].iloc[0]) if 'PÇIDADE' in match.columns else "un"
        custo = float(pd.to_numeric(match['VLR / PÇ.'].iloc[0], errors='coerce') or 0.0)
        return unid, custo
    return None, None

# --- 3. CAIXA DE DETALHAMENTO ESTÁVEL ---
@st.dialog("Composição Técnica por Grupos", width="large")
def abrir_cpu_detalhada(idx, dados_linha):
    st.write(f"### 🛠️ Item: {dados_linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=cols),
            "servico": pd.DataFrame(columns=cols),
            "material": pd.DataFrame(columns=cols)
        }

    comp = st.session_state.composicoes[idx]

    def renderizar_bloco(titulo, chave, tipo_fator):
        st.subheader(f"📦 {titulo}")
        label_ajuda = "Digite a % de acréscimo" if tipo_fator == "percentual" else "Digite o multiplicador (x)"
        
        df_edit = st.data_editor(
            comp[chave],
            num_rows="dynamic",
            column_config={
                "Valor Unit.": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn("Subtotal Custo", format="R$ %.2f", disabled=True),
                "Fator": st.column_config.NumberColumn(f"Fator ({label_ajuda})", default=1.0 if tipo_fator != "percentual" else 40.0),
                "Valor Final": st.column_config.NumberColumn("Valor c/ Fator", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"ed_{chave}_{idx}"
        )

        if not df_edit.empty:
            # Lógica de processamento das linhas
            for i, row in df_edit.iterrows():
                # Busca automática por descrição
                if row['Descrição'] and (pd.isna(row['Valor Unit.']) or row['Valor Unit.'] == 0):
                    u, c = buscar_dados_mp(row['Descrição'])
                    if u is not None:
                        df_edit.at[i, 'Unid.'] = u
                        df_edit.at[i, 'Valor Unit.'] = c
                
                # Cálculos de Custo e Venda
                q = pd.to_numeric(row["Quant."], errors='coerce', default=0)
                vu = pd.to_numeric(row["Valor Unit."], errors='coerce', default=0)
                fat = pd.to_numeric(row["Fator"], errors='coerce', default=0)
                
                custo_calc = q * vu
                df_edit.at[i, "Valor Total"] = custo_calc
                
                if tipo_fator == "percentual":
                    df_edit.at[i, "Valor Final"] = custo_calc * (1 + (fat / 100))
                else:
                    df_edit.at[i, "Valor Final"] = custo_calc * fat
            
            st.session_state.composicoes[idx][chave] = df_edit
            return df_edit["Valor Final"].sum()
        return 0.0

    # Chamada dos Blocos
    v1 = renderizar_bloco("Material Terceirizado", "terceirizado", "percentual")
    v2 = renderizar_bloco("Material Terceirizado C/ Serviço", "servico", "multiplicador")
    v3 = renderizar_bloco("Material", "material", "multiplicador")

    st.divider()
    venda_total = v1 + v2 + v3
    st.metric("PREÇO DE VENDA TOTAL DO ITEM", f"R$ {venda_total:,.2f}")

    if st.button("✅ Salvar e Aplicar na Planilha"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = venda_total
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Estável")
u1, u2 = st.columns(2)
with u1: arq_obra = st.file_uploader("📋 Planilha CONSTRUTORA", type=["xlsx", "csv"])
with u2: arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_mp is None:
        df_mp_raw = pd.read_csv(arq_mp) if arq_mp.name.endswith('.csv') else pd.read_excel(arq_mp)
        df_mp_raw.columns = [str(c).strip() for c in df_mp_raw.columns]
        st.session_state.df_mp = df_mp_raw

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df
    
    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_edit")

    st.divider()
    idx_sel = st.number_input("Índice da linha:", min_value=0, max_value=len(st.session_state.df_obra)-1, step=1)
    if st.button(f"🔎 Abrir Composição da Linha {idx_sel}"):
        abrir_cpu_detalhada(idx_sel, st.session_state.df_obra.iloc[idx_sel])
