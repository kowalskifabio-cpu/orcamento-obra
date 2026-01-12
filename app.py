import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Pro", layout="wide")

# --- 1. MEMÓRIA DO SISTEMA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    base = st.session_state.df_mp
    termo = str(desc).strip().lower()
    # Busca na coluna NOME PRODUTO conforme sua planilha MP
    col_nome = 'NOME PRODUTO' if 'NOME PRODUTO' in base.columns else base.columns[1]
    match = base[base[col_nome].astype(str).str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    if not match.empty:
        u = str(match['PÇIDADE'].iloc[0]) if 'PÇIDADE' in match.columns else "un"
        # Busca na coluna F (VLR / PÇ.)
        c = float(pd.to_numeric(match['VLR / PÇ.'].iloc[0], errors='coerce') or 0.0)
        return u, c
    return None, None

# --- 2. CONTEÚDO DA CAIXA (FRAGMENTO PARA NÃO FECHAR) ---
@st.fragment
def renderizar_detalhamento(idx, linha_master):
    st.write(f"### 📋 Detalhando: {linha_master.get('DESCRIÇÃO', 'Item')}")
    
    colunas_padrao = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
    
    if idx not in st.session_state.composicoes:
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=colunas_padrao),
            "servico": pd.DataFrame(columns=colunas_padrao),
            "material": pd.DataFrame(columns=colunas_padrao)
        }

    def processar_bloco(titulo, chave, tipo_fator):
        st.subheader(f"📦 {titulo}")
        df_atual = st.session_state.composicoes[idx][chave]
        
        # O Editor de Dados
        df_editado = st.data_editor(
            df_atual,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{chave}_{idx}",
            column_config={
                "Código": st.column_config.NumberColumn("Item #", disabled=True, help="Numeração automática"),
                "Valor Total": st.column_config.NumberColumn("Subtotal Custo", disabled=True, format="R$ %.2f"),
                "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
                "Fator": st.column_config.NumberColumn("Acréscimo %" if tipo_fator == "perc" else "Multiplicador x")
            }
        )

        # Lógica disparada ao mudar qualquer dado (ou adicionar linha)
        if not df_editado.equals(df_atual):
            # 1. Atualiza Contador Automático (Código) e Processa Cálculos
            for i, r in df_editado.iterrows():
                # Código automático sequencial
                df_editado.at[i, "Código"] = i + 1
                
                # Busca automática na MP se a descrição existir e o valor for zero
                if r['Descrição'] and (pd.isna(r['Valor Unit.']) or r['Valor Unit.'] == 0):
                    u, c = buscar_dados_mp(r['Descrição'])
                    if u: 
                        df_editado.at[i, 'Unid.'] = u
                        df_editado.at[i, 'Valor Unit.'] = c
                
                # Cálculos Matemáticos
                q = float(pd.to_numeric(r['Quant.'], errors='coerce') or 0.0)
                vu = float(pd.to_numeric(r['Valor Unit.'], errors='coerce') or 0.0)
                f = float(pd.to_numeric(r['Fator'], errors='coerce') or (0.0 if tipo_fator == "perc" else 1.0))
                
                custo_total = q * vu
                df_editado.at[i, "Valor Total"] = custo_total
                
                if tipo_fator == "perc":
                    df_editado.at[i, "Valor Final"] = custo_total * (1 + (f / 100))
                else:
                    df_editado.at[i, "Valor Final"] = custo_total * f
            
            # Salva na memória e força atualização visual do fragmento
            st.session_state.composicoes[idx][chave] = df_editado
            st.rerun(scope="fragment")
        
        return df_editado["Valor Final"].sum()

    # Renderização dos 3 blocos
    v1 = processar_bloco("Material Terceirizado", "terceirizado", "perc")
    v2 = processar_bloco("Material Terceirizado C/ Serviço", "servico", "mult")
    v3 = processar_bloco("Material", "material", "mult")

    total_venda = v1 + v2 + v3
    st.divider()
    st.metric("VALOR TOTAL DE VENDA (ITEM)", f"R$ {total_venda:,.2f}")

    if st.button("💾 Finalizar e Salvar na Planilha Master", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app") # Fecha a caixa e atualiza a planilha master lá fora

# --- 3. DIÁLOGO (POP-UP) ---
@st.dialog("Composição Técnica de Marcenaria", width="large")
def modal_cpu(idx, linha_master):
    renderizar_detalhamento(idx, linha_master)

# --- 4. TELA PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional")

col1, col2 = st.columns(2)
with col1: arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with col2: arq_mp = st.file_uploader("2. MP Valores (Listão)", type=["xlsx", "csv"])

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

    # Tabela Master
    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="main_editor")
    
    st.divider()
    idx_sel = st.number_input("Digite o índice da linha para detalhar:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento da Linha {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
