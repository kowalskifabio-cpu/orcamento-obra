import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Orçamentador Pro v7", layout="wide")

# --- 1. FUNÇÕES DE PERSISTÊNCIA (SALVAR/CARREGAR) ---

def exportar_projeto():
    """Converte o estado atual para um arquivo JSON baixável."""
    projeto = {
        "df_obra": st.session_state.df_obra.to_json(orient="split") if st.session_state.df_obra is not None else None,
        "composicoes": {
            str(k): {bloco: df.to_json(orient="split") for bloco, df in v.items()}
            for k, v in st.session_state.composicoes.items()
        }
    }
    return json.dumps(projeto)

def importar_projeto(arquivo_json):
    """Restaura o estado a partir de um arquivo JSON enviado."""
    dados = json.load(arquivo_json)
    if dados["df_obra"]:
        st.session_state.df_obra = pd.read_json(dados["df_obra"], orient="split")
    
    nova_comp = {}
    for k, v in dados["composicoes"].items():
        nova_comp[int(k)] = {bloco: pd.read_json(js, orient="split") for bloco, js in v.items()}
    st.session_state.composicoes = nova_comp
    st.success("Projeto restaurado com sucesso!")

# --- 2. MEMÓRIA DO SISTEMA ---
if 'df_obra' not in st.session_state: st.session_state.df_obra = None
if 'df_mp' not in st.session_state: st.session_state.df_mp = None
if 'composicoes' not in st.session_state: st.session_state.composicoes = {}

# (Mantenha aqui as funções buscar_dados_mp, renderizar_bloco_com_calculos e modal_cpu do código anterior)

# --- 3. BARRA LATERAL (GESTÃO DE PROJETOS) ---
with st.sidebar:
    st.header("💾 Gestão de Trabalho")
    
    # SALVAR
    if st.session_state.df_obra is not None:
        st.subheader("Pausar Trabalho")
        json_projeto = exportar_projeto()
        st.download_button(
            label="📥 Baixar Arquivo de Projeto",
            data=json_projeto,
            file_name="projeto_orcamento.json",
            mime="application/json",
            help="Salve este arquivo para continuar depois."
        )
    
    st.divider()
    
    # CARREGAR
    st.subheader("Retomar Trabalho")
    arq_projeto = st.file_uploader("Subir arquivo .json", type=["json"])
    if arq_projeto:
        if st.button("🔄 Restaurar Dados"):
            importar_projeto(arq_projeto)
            st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.title("🏗️ Orçamentador Profissional")

c1, c2 = st.columns(2)
with c1: arq_obra = st.file_uploader("1. Planilha da CONSTRUTORA", type=["xlsx", "csv"])
with c2: arq_mp = st.file_uploader("2. MP Valores (Listão)", type=["xlsx", "csv"])

# Lógica de carregamento inicial (Mantenha a mesma do código anterior)
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

    # Exibição Master
    st.session_state.df_obra = st.data_editor(st.session_state.df_obra, use_container_width=True, key="master_editor")
    
    idx_sel = st.number_input("Índice da linha:", 0, len(st.session_state.df_obra)-1, 0)
    if st.button(f"🔎 Abrir Detalhamento {idx_sel}", type="primary"):
        # Importante: A função modal_cpu deve estar definida acima
        modal_cpu(idx_sel, st.session_state.df_obra.iloc[idx_sel])

# --- 5. EXPORTAÇÃO FINAL (EXCEL) ---
if st.session_state.df_obra is not None:
    st.divider()
    st.subheader("🏁 Finalização")
    if st.button("📊 Gerar Excel Final para Cliente"):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df_obra.to_excel(writer, index=False, sheet_name='Orcamento')
        st.download_button(
            label="💾 Baixar Planilha Orçada",
            data=output.getvalue(),
            file_name="Orcamento_Finalizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
