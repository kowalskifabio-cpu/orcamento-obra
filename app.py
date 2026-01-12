import streamlit as st
import pandas as pd

st.set_page_config(page_title="Orçamentador Marcenaria v5", layout="wide")

# --- 1. MEMÓRIA DO SISTEMA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

def buscar_dados_mp(desc):
    if st.session_state.df_mp is None or not desc: return None, None
    base = st.session_state.df_mp
    termo = str(desc).strip().lower()
    col_nome = 'NOME PRODUTO' if 'NOME PRODUTO' in base.columns else base.columns[1]
    
    # Busca exata ou por contém
    match = base[base[col_nome].astype(str).str.lower() == termo]
    if match.empty:
        match = base[base[col_nome].astype(str).str.lower().str.contains(termo, na=False)]
    
    if not match.empty:
        u = str(match['PÇIDADE'].iloc[0]) if 'PÇIDADE' in match.columns else "un"
        c = float(pd.to_numeric(match['VLR / PÇ.'].iloc[0], errors='coerce') or 0.0)
        return u, c
    return None, None

# --- 2. FRAGMENTO PARA ATUALIZAÇÃO INSTANTÂNEA ---
@st.fragment
def renderizar_blocos_cpu(idx, linha_master):
    st.write(f"### 📋 Item: {linha_master.get('DESCRIÇÃO', 'Item')}")
    
    # Colunas que o sistema gerencia
    colunas = ["Código", "Descrição", "Quant.", "Unid.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]
    
    if idx not in st.session_state.composicoes:
        st.session_state.composicoes[idx] = {
            "terceirizado": pd.DataFrame(columns=colunas),
            "servico": pd.DataFrame(columns=colunas),
            "material": pd.DataFrame(columns=colunas)
        }

    def processar_bloco(titulo, chave, tipo_fator):
        st.subheader(f"📦 {titulo}")
        df_atual = st.session_state.composicoes[idx][chave]
        
        # Garante que as colunas numéricas existam para evitar erros de cálculo
        for c in ["Quant.", "Valor Unit.", "Valor Total", "Fator", "Valor Final"]:
            if c in df_atual.columns:
                df_atual[c] = pd.to_numeric(df_atual[c], errors='coerce').fillna(0.0)

        df_editado = st.data_editor(
            df_atual,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{chave}_{idx}",
            column_config={
                "Código": st.column_config.NumberColumn("Item #", disabled=True),
                "Valor Total": st.column_config.NumberColumn("Custo Total", disabled=True, format="R$ %.2f"),
                "Valor Final": st.column_config.NumberColumn("Preço Venda", disabled=True, format="R$ %.2f"),
                "Fator": st.column_config.NumberColumn("Markup %" if tipo_fator == "perc" else "Multiplicador x")
            }
        )

        # SE HOUVE MUDANÇA (Editou, Adicionou ou Deletou linha)
        if not df_editado.equals(df_atual):
            # 1. FORÇA A RE-SEQUENCIAÇÃO DO CÓDIGO (1, 2, 3...)
            df_editado = df_editado.reset_index(drop=True)
            df_editado["Código"] = range(1, len(df_editado) + 1)
            
            # 2. PROCESSA LINHA POR LINHA
            for i, r in df_editado.iterrows():
                # Busca automática se a descrição estiver preenchida e unidade vazia
                if r['Descrição'] and (not r['Unid.'] or r['Unid.'] == "0" or r['Unid.'] == ""):
                    u, c = buscar_dados_mp(r['Descrição'])
                    if u: 
                        df_editado.at[i, 'Unid.'] = u
                        df_editado.at[i, 'Valor Unit.'] = c
                
                # Cálculos Matemáticos
                qtd = float(r['Quant.'])
                vu = float(r['Valor Unit.'])
                f = float(r['Fator'])
                
                # Se for multiplicador e o usuário deixar 0, assume 1 para não zerar o preço
                if tipo_fator == "mult" and f == 0: f = 1.0
                
                custo_total = qtd * vu
                df_editado.at[i, "Valor Total"] = custo_total
                
                if tipo_fator == "perc":
                    df_editado.at[i, "Valor Final"] = custo_total * (1 + (f / 100))
                else:
                    df_editado.at[i, "Valor Final"] = custo_total * f
            
            # Salva na memória e recarrega APENAS o fragmento (mantém a caixa aberta)
            st.session_state.composicoes[idx][chave] = df_editado
            st.rerun(scope="fragment")
        
        return df_editado["Valor Final"].sum()

    v1 = processar_bloco("Material Terceirizado", "terceirizado", "perc")
    v2 = processar_bloco("Material Terceirizado C/ Serviço", "servico", "mult")
    v3 = processar_bloco("Material", "material", "mult")

    total_venda = v1 + v2 + v3
    st.divider()
    st.metric("VALOR TOTAL DO ITEM (VENDA)", f"R$ {total_venda:,.2f}")

    if st.button("💾 Finalizar e Salvar Tudo", type="primary"):
        st.session_state.df_obra.at[idx, 'CUSTO UNITÁRIO FINAL'] = total_venda
        st.session_state.df_obra.at[idx, 'STATUS'] = "✅"
        st.rerun(scope="app") # Atualiza a planilha master lá fora

# --- 3. DIÁLOGO (POP-UP) ---
@st.dialog("Composição Técnica", width="large")
def modal_cpu(idx, linha_master):
    renderizar_blocos_cpu(idx, linha_master)

# --- 4. INTERFACE PRINCIPAL ---
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
    
    st.divider()
    idx_sel = st.number_input("Digite o índice da linha para detalhar:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])
