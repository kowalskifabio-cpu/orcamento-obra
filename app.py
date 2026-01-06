import streamlit as st
import pandas as pd
from io import BytesIO
import os

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. LOGO E MEMÓRIA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# --- 2. FUNÇÃO DE BUSCA CORRIGIDA (Foco em NOME PRODUTO) ---
def buscar_dados_mp(descricao_pesquisada):
    if st.session_state.df_mp is None or not descricao_pesquisada:
        return None, None
    
    base = st.session_state.df_mp
    termo = str(descricao_pesquisada).strip().lower()
    
    # Garante que a coluna NOME PRODUTO existe
    col_nome = 'NOME PRODUTO' if 'NOME PRODUTO' in base.columns else base.columns[1]
    
    # 1. Tenta busca exata primeiro
    match = base[base[col_nome].astype(str).str.lower() == termo]
    
    # 2. Se não achou exato, tenta "contém"
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        # Mapeia colunas solicitadas: PÇIDADE e VLR / PÇ.
        unid_col = 'PÇIDADE' if 'PÇIDADE' in match.columns else 'PÇIDADE'
        vlr_col = 'VLR / PÇ.' if 'VLR / PÇ.' in match.columns else 'VLR / PÇ.'
        
        try:
            unidade = str(match[unid_col].iloc[0])
            custo = float(pd.to_numeric(match[vlr_col].iloc[0], errors='coerce') or 0.0)
            return unidade, custo
        except:
            return "un", 0.0
            
    return None, None

# --- 3. CAIXA DE DETALHAMENTO ---
@st.dialog("Composição Técnica por Grupos", width="large")
def abrir_cpu_detalhada(idx, dados_linha):
    st.write(f"### 🛠️ Item: {dados_linha.get('DESCRIÇÃO', 'Item')}")
    
    if idx not in st.session_state.composicoes:
        cols = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator/Acrésc."]
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=cols),
            "servico": pd.DataFrame(columns=cols),
            "material": pd.DataFrame(columns=cols)
        }

    comp = st.session_state.composicoes[idx]

    def renderizar_bloco(titulo, chave):
        st.subheader(f"📦 {titulo}")
        
        # Editor de Tabela
        df_edit = st.data_editor(
            comp[chave],
            num_rows="dynamic",
            column_config={
                "Descrição": st.column_config.TextColumn("Descrição (NOME PRODUTO)"),
                "Unid.": st.column_config.TextColumn("Unid. (MP)"),
                "Valor Unit.": st.column_config.NumberColumn("Custo (VLR / PÇ.)", format="R$ %.2f"),
                "Valor Total": st.column_config.NumberColumn("Total", format="R$ %.2f", disabled=True),
            },
            use_container_width=True,
            key=f"ed_{chave}_{idx}"
        )

        # Lógica de preenchimento automático ao mudar a descrição
        if not df_edit.empty:
            for i, row in df_edit.iterrows():
                desc = row.get('Descrição')
                # Só busca se tiver descrição e o valor ainda for zero (para não sobrescrever ajustes manuais)
                if desc and (pd.isna(row.get('Valor Unit.')) or row.get('Valor Unit.') == 0):
                    u, c = buscar_dados_mp(desc)
                    if u is not None:
                        df_edit.at[i, 'Unid.'] = u
                        df_edit.at[i, 'Valor Unit.'] = c
            
            # Cálculo do Total do Item
            df_edit["Valor Total"] = pd.to_numeric(df_edit["Quant."], errors='coerce').fillna(0) * \
                                     pd.to_numeric(df_edit["Valor Unit."], errors='coerce').fillna(0)
            
            st.session_state.composicoes[idx][chave] = df_edit
            return df_edit["Valor Total"].sum()
        return 0.0

    t1 = renderizar_bloco("Material Terceirizado", "terceirizado")
    t2 = renderizar_bloco("Material Terceirizado C/ Serviço", "servico")
    t3 = renderizar_bloco("Material", "material")

    st.divider()
    total_direto = t1 + t2 + t3
    st.metric("Custo Direto Total", f"R$ {total_direto:,.2f}")

    if st.button("✅ Salvar Composição"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_direto
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Marcenaria & Mármore")
u1, u2 = st.columns(2)
with u1:
    arq_obra = st.file_uploader("📋 Planilha CONSTRUTORA", type=["xlsx", "csv"])
with u2:
    arq_mp = st.file_uploader("💰 MP Valores", type=["xlsx", "csv"])

if arq_obra and arq_mp:
    if st.session_state.df_mp is None:
        # Carrega a MP e limpa nomes de colunas
        df_mp_raw = pd.read_csv(arq_mp) if arq_mp.name.endswith('.csv') else pd.read_excel(arq_mp)
        df_mp_raw.columns = [str(c).strip() for c in df_mp_raw.columns]
        st.session_state.df_mp = df_mp_raw

    if st.session_state.df_obra is None:
        df = pd.read_excel(arq_obra, skiprows=7).dropna(how='all', axis=0)
        df.columns = [str(c).upper() for c in df.columns]
        df.insert(0, 'STATUS', '⭕')
        df['CUSTO UNITÁRIO FINAL'] = 0.0
        st.session_state.df_obra = df
    
    df_master = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_edit")
    st.session_state.df_obra = df_master

    st.divider()
    idx_sel = st.number_input("Índice da linha para detalhar:", min_value=0, max_value=len(df_master)-1, step=1)
    if st.button(f"🔎 Abrir Composição da Linha {idx_sel}"):
        abrir_cpu_detalhada(idx_sel, df_master.iloc[idx_sel])
