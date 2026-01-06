import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Orçamentador Pro - Detalhamento", layout="wide")

# Inicializa a memória de composição se não existir
if 'composicao_itens' not in st.session_state:
    st.session_state.composicao_itens = {}

@st.dialog("Detalhamento da Composição (CPU)", width="large")
def modal_detalhes(index_item, descricao_original, df_mp):
    st.write(f"### 🛠️ Composição: {descricao_original}")
    
    # Recupera ou inicializa a lista de insumos para este item específico
    if index_item not in st.session_state.composicao_itens:
        # Cria uma linha inicial padrão baseada na busca da MP
        st.session_state.composicao_itens[index_item] = pd.DataFrame([
            {"Tipo": "Material", "Insumo": descricao_original, "Unid": "un", "Qtd": 1.0, "Custo Unit": 0.0}
        ])

    df_cpu = st.session_state.composicao_itens[index_item]

    # Botões de Gerenciamento de Linhas
    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("➕ Adicionar Insumo/Serviço"):
        nova_linha = pd.DataFrame([{"Tipo": "Material", "Insumo": "", "Unid": "un", "Qtd": 1.0, "Custo Unit": 0.0}])
        st.session_state.composicao_itens[index_item] = pd.concat([df_cpu, nova_linha], ignore_index=True)
        st.rerun()

    # Tabela Editável de Insumos
    st.write("---")
    df_editado = st.data_editor(
        st.session_state.composicao_itens[index_item],
        num_rows="dynamic", # Permite excluir linhas selecionando e apertando DEL
        column_config={
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Material", "Serviço", "Terceirizado"]),
            "Custo Unit": st.column_config.NumberColumn("Custo Unit (R$)", format="R$ %.2f"),
        },
        use_container_width=True,
        key=f"editor_{index_item}"
    )
    
    # Salva as edições
    st.session_state.composicao_itens[index_item] = df_editado
    
    # Cálculos de Resumo
    total_cpu = (df_editado['Qtd'] * df_editado['Custo Unit']).sum()
    st.metric("Subtotal do Item (Custo Direto)", f"R$ {total_cpu:,.2f}")

    if st.button("✅ Confirmar Detalhamento"):
        # Aqui você pode salvar o resultado final de volta na planilha principal
        st.success("Composição salva com sucesso!")
        st.rerun()

# --- ÁREA DE UPLOAD E TABELA PRINCIPAL ---
# (Manter a lógica de carregamento da planilha da construtora e MP Valores que já funciona)
st.info("Suba a Planilha da Construtora e o MP Valores para habilitar o detalhamento por linha.")

# Simulador de clique (Exemplo)
if st.button("Teste: Abrir Detalhamento da Linha 240"):
    # Passamos df_mp como None para o exemplo, mas no seu código ele virá do upload
    modal_detalhes(240, "EXEMPLO: Porta de Madeira Marcenaria", None)
