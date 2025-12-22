import streamlit as st
import pandas as pd
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Orçamentador Flexível", layout="wide")

st.title("🏗️ Orçamentador com Edição Total")
st.markdown("---")

# 1. BARRA LATERAL (Configurações Financeiras)
with st.sidebar:
    st.header("Configurações Globais")
    perc_imposto = st.number_input("Impostos (%)", value=15.0)
    perc_encargos = st.number_input("Encargos Sociais M.O. (%)", value=125.0)
    perc_lucro = st.number_input("Margem de Lucro/BDI (%)", value=20.0)
    frete_fixo = st.number_input("Frete/Logística Total (R$)", value=0.0)

divisor = 1 - ((perc_imposto + perc_lucro) / 100)

# 2. GESTÃO DOS DADOS (Memória do Site)
# Usamos o 'session_state' para o site não esquecer as linhas novas ao clicar em botões
if 'dados_orcamento' not in st.session_state:
    st.session_state.dados_orcamento = None

# 3. IMPORTAÇÃO
st.subheader("1. Entrada de Dados")
arquivo_subido = st.file_uploader("Importar planilha da construtora", type=["xlsx", "csv"])

if arquivo_subido is not None and st.session_state.dados_orcamento is None:
    try:
        if arquivo_subido.name.endswith('.csv'):
            df_ini = pd.read_csv(arquivo_subido, skiprows=7)
        else:
            df_ini = pd.read_excel(arquivo_subido, skiprows=7)
        
        colunas_alvo = ['ITEM', 'DESCRIÇÃO', 'OBSERVAÇÕES', 'IMAGEM', 'UND', 'QDT']
        colunas_existentes = [c for c in colunas_alvo if c in df_ini.columns]
        df_ini = df_ini[colunas_existentes].copy()
        df_ini = df_ini.dropna(subset=['DESCRIÇÃO'])
        
        # Inicializa colunas de custo
        df_ini['Custo Mat. Unit.'] = 0.0
        df_ini['Mão de Obra Unit.'] = 0.0
        
        st.session_state.dados_orcamento = df_ini
    except Exception as e:
        st.error(f"Erro na importação: {e}")

# 4. TABELA EDITÁVEL E INCLUSÃO DE LINHAS
if st.session_state.dados_orcamento is not None:
    
    st.subheader("2. Planilha de Orçamento (Edição Livre)")
    
    # Botão para adicionar linha manual
    if st.button("➕ Adicionar Nova Linha"):
        nova_linha = pd.DataFrame([{
            'ITEM': '', 'DESCRIÇÃO': 'Novo Item Manual', 'OBSERVAÇÕES': '', 
            'IMAGEM': '', 'UND': 'und', 'QDT': 1.0, 
            'Custo Mat. Unit.': 0.0, 'Mão de Obra Unit.': 0.0
        }])
        st.session_state.dados_orcamento = pd.concat([st.session_state.dados_orcamento, nova_linha], ignore_index=True)
        st.rerun() # Atualiza a tela para mostrar a linha nova

    # Interface de Edição (Todas as colunas liberadas)
    df_editado = st.data_editor(
        st.session_state.dados_orcamento,
        num_rows="dynamic", # Permite que o usuário delete linhas também selecionando e apertando 'del'
        column_config={
            "Custo Mat. Unit.": st.column_config.NumberColumn("Material Unit. (R$)", format="R$ %.2f"),
            "Mão de Obra Unit.": st.column_config.NumberColumn("M.O. Unit. (R$)", format="R$ %.2f"),
            "QDT": st.column_config.NumberColumn("Quantidade", format="%.2f"),
        },
        use_container_width=True,
        hide_index=True,
    )
    
    # Atualiza a memória com o que foi editado na tabela
    st.session_state.dados_orcamento = df_editado

    # 5. CÁLCULOS TÉCNICOS
    # M.O. com encargos
    mo_enc = df_editado['Mão de Obra Unit.'] * (1 + perc_encargos/100)
    custo_direto = df_editado['Custo Mat. Unit.'] + mo_enc
    
    # Preço Final por Unidade (Markup)
    precos_unitarios = custo_direto / divisor
    totais_por_item = precos_unitarios * df_editado['QDT']

    total_geral_obra = totais_por_item.sum() + frete_fixo

    # EXIBIÇÃO DE RESULTADOS
    st.markdown("---")
    st.metric("VALOR TOTAL DA PROPOSTA (Líquido)", f"R$ {total_geral_obra:,.2f}")
    
    # Botão de Exportação
    def converter_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df['Preço Final Unit.'] = precos_unitarios
            df['Total do Item'] = totais_por_item
            df.to_excel(writer, index=False, sheet_name='Orcamento_Final')
        return output.getvalue()

    st.download_button(
        label="💾 Baixar Planilha Finalizada",
        data=converter_excel(df_editado),
        file_name=f"Orcamento_Obra.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
