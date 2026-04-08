import streamlit as st
import pandas as pd
from datetime import timedelta
import io
import re
import plotly.express as px

# Configurações da página do Streamlit
st.set_page_config(layout="wide", page_title="Análise de campanha de cobrança")

st.title("📊 Análise de eficiência de campanha de cobrança via Whatsapp")
st.markdown("Faça o upload dos seus arquivos para analisar a performance da campanha de notificações.")

# --- Funções de Processamento ---

@st.cache_data
def load_and_process_envios(uploaded_file):
    """Carrega e processa o arquivo de envios (notificações)."""
    try:
        df = pd.read_excel(uploaded_file)

        required_cols = ['To', 'Send At']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Envios: Colunas esperadas '{required_cols[0]}' e '{required_cols[1]}' não encontradas.")
            return None

        df_envios = df[['To', 'Send At']].copy()
        df_envios.rename(columns={'To': 'TELEFONE_ENVIO', 'Send At': 'DATA_ENVIO'}, inplace=True)

        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_envios['TELEFONE_ENVIO'] = df_envios['TELEFONE_ENVIO'].str.strip()

        df_envios['DATA_ENVIO'] = pd.to_datetime(df_envios['DATA_ENVIO'], errors='coerce', dayfirst=True)
        df_envios.dropna(subset=['DATA_ENVIO'], inplace=True)

        st.sidebar.success("Arquivo de Envios processado com sucesso!")
        return df_envios
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Envios: {e}")
        return None

@st.cache_data
def load_and_process_pagamentos(uploaded_file):
    """Carrega e processa o arquivo de pagamentos (CSV ou XLSX)."""
    try:
        df = None
        if uploaded_file.name.endswith('.csv'):
            for encoding in ['latin1', 'utf-8', 'cp1252']:
                try:
                    df = pd.read_csv(uploaded_file, sep=';', decimal=',', encoding=encoding, header=None)
                    uploaded_file.seek(0)
                    break
                except Exception:
                    uploaded_file.seek(0)
                    continue
            if df is None:
                raise ValueError("Não foi possível ler o arquivo CSV com as codificações tentadas.")
        elif uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file, header=None)
        else:
            raise ValueError("Formato de arquivo de pagamentos não suportado. Use .csv ou .xlsx.")

        if df is None or df.empty:
            st.sidebar.error("Arquivo de Pagamentos está vazio ou não pôde ser lido.")
            return None

        if df.shape[1] < 10:
            st.sidebar.error(f"Arquivo de Pagamentos: Esperava pelo menos 10 colunas, mas encontrou {df.shape[1]}.")
            return None

        # ALTERAÇÃO: incluir índice 18 para capturar a coluna Tipo Pagamento
        # Verificar se a coluna de índice 18 existe no arquivo
        col_indices = [0, 6, 9]
        col_names = ['MATRICULA_PAGAMENTO', 'DATA_PAGAMENTO', 'VALOR_PAGO']

        if df.shape[1] > 18:
            col_indices.append(18)
            col_names.append('TIPO_PAGAMENTO')

        df_pagamentos = df.iloc[:, col_indices].copy()
        df_pagamentos.columns = col_names

        df_pagamentos['MATRICULA_PAGAMENTO'] = df_pagamentos['MATRICULA_PAGAMENTO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_pagamentos['DATA_PAGAMENTO'] = pd.to_datetime(df_pagamentos['DATA_PAGAMENTO'], errors='coerce', dayfirst=True)
        df_pagamentos.dropna(subset=['DATA_PAGAMENTO'], inplace=True)

        df_pagamentos['VALOR_PAGO'] = df_pagamentos['VALOR_PAGO'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df_pagamentos['VALOR_PAGO'] = pd.to_numeric(df_pagamentos['VALOR_PAGO'], errors='coerce')
        df_pagamentos.dropna(subset=['VALOR_PAGO'], inplace=True)

        # Limpar a coluna TIPO_PAGAMENTO se ela existir
        if 'TIPO_PAGAMENTO' in df_pagamentos.columns:
            df_pagamentos['TIPO_PAGAMENTO'] = df_pagamentos['TIPO_PAGAMENTO'].astype(str).str.strip()
            df_pagamentos['TIPO_PAGAMENTO'] = df_pagamentos['TIPO_PAGAMENTO'].replace('nan', 'Não informado')

        st.sidebar.success("Arquivo de Pagamentos processado com sucesso!")
        return df_pagamentos
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Pagamentos: {e}")
        return None

@st.cache_data
def load_and_process_clientes(uploaded_file):
    """Carrega e processa o arquivo de identificação de clientes."""
    try:
        df = pd.read_excel(uploaded_file)

        required_cols = ['TELEFONE', 'MATRICULA', 'SITUACAO']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Arquivo de Clientes: Colunas esperadas '{required_cols[0]}', '{required_cols[1]}' e '{required_cols[2]}' não encontradas.")
            return None

        df_clientes = df[['TELEFONE', 'MATRICULA', 'SITUACAO']].copy()
        df_clientes.rename(columns={
            'TELEFONE': 'TELEFONE_CLIENTE',
            'MATRICULA': 'MATRICULA_CLIENTE'
        }, inplace=True)

        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].astype(str).str.replace(r'^55', '', regex=True).str.replace(r'\.0$', '', regex=True)
        df_clientes['TELEFONE_CLIENTE'] = df_clientes['TELEFONE_CLIENTE'].str.strip()

        df_clientes['MATRICULA_CLIENTE'] = df_clientes['MATRICULA_CLIENTE'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        df_clientes['SITUACAO'] = pd.to_numeric(df_clientes['SITUACAO'], errors='coerce').fillna(0)

        df_clientes.drop_duplicates(subset=['TELEFONE_CLIENTE', 'MATRICULA_CLIENTE'], inplace=True)

        st.sidebar.success("Arquivo de Clientes processado com sucesso!")
        return df_clientes
    except Exception as e:
        st.sidebar.error(f"Erro ao processar arquivo de Clientes: {e}")
        return None

# --- Interface Streamlit ---

st.sidebar.header("Upload de Arquivos")
uploaded_envios = st.sidebar.file_uploader("1. Base de Envios (Notificações - .xlsx)", type=["xlsx"])
uploaded_pagamentos = st.sidebar.file_uploader("2. Base de Pagamentos (.csv ou .xlsx)", type=["csv", "xlsx"])
uploaded_clientes = st.sidebar.file_uploader("3. Base de Identificação de Clientes (.xlsx)", type=["xlsx"])

st.sidebar.header("Configurações da Análise")
janela_dias = st.sidebar.slider("Janela de dias para considerar o pagamento após o envio da notificação:", 0, 30, 7)

executar_analise = st.sidebar.button("Executar Análise")

df_envios = None
df_pagamentos = None
df_clientes = None

if uploaded_envios:
    df_envios = load_and_process_envios(uploaded_envios)
if uploaded_pagamentos:
    df_pagamentos = load_and_process_pagamentos(uploaded_pagamentos)
if uploaded_clientes:
    df_clientes = load_and_process_clientes(uploaded_clientes)

if st.sidebar.checkbox("Mostrar pré-visualização dos dados processados"):
    if df_envios is not None:
        st.subheader("Pré-visualização da Base de Envios")
        st.dataframe(df_envios.head())
    if df_pagamentos is not None:
        st.subheader("Pré-visualização da Base de Pagamentos")
        st.dataframe(df_pagamentos.head())
    if df_clientes is not None:
        st.subheader("Pré-visualização da Base de Clientes")
        st.dataframe(df_clientes.head())

if executar_analise:
    if df_envios is not None and df_pagamentos is not None and df_clientes is not None:
        st.subheader("Processando e Cruzando Dados...")

        # Total de clientes notificados = telefones únicos direto do df_envios
        total_clientes_notificados = df_envios['TELEFONE_ENVIO'].nunique()

        # Total da dívida dos notificados
        df_telefones_unicos_envios = df_envios[['TELEFONE_ENVIO']].drop_duplicates()
        df_lookup_divida = pd.merge(
            df_telefones_unicos_envios,
            df_clientes[['TELEFONE_CLIENTE', 'SITUACAO']],
            left_on='TELEFONE_ENVIO',
            right_on='TELEFONE_CLIENTE',
            how='left'
        )
        total_divida_notificados = df_lookup_divida['SITUACAO'].sum()

        # 1. Cruzar Envios com Clientes para obter a Matrícula
        df_campanha = pd.merge(
            df_envios,
            df_clientes,
            left_on='TELEFONE_ENVIO',
            right_on='TELEFONE_CLIENTE',
            how='left'
        )

        df_campanha.dropna(subset=['MATRICULA_CLIENTE'], inplace=True)
        df_campanha.rename(columns={'MATRICULA_CLIENTE': 'MATRICULA'}, inplace=True)
        df_campanha.drop(columns=['TELEFONE_CLIENTE'], inplace=True)

        df_campanha_unique_notifications = df_campanha.drop_duplicates(subset=['MATRICULA', 'DATA_ENVIO'])

        if not df_campanha_unique_notifications.empty:
            st.subheader("Realizando Análise de Pagamentos Pós-Campanha")

            # 2. Cruzar com Pagamentos
            df_resultados = pd.merge(
                df_campanha_unique_notifications,
                df_pagamentos,
                left_on='MATRICULA',
                right_on='MATRICULA_PAGAMENTO',
                how='left'
            )

            # Filtrar pagamentos dentro da janela
            df_pagamentos_campanha = df_resultados[
                (df_resultados['DATA_PAGAMENTO'] > df_resultados['DATA_ENVIO']) &
                (df_resultados['DATA_PAGAMENTO'] <= df_resultados['DATA_ENVIO'] + timedelta(days=janela_dias))
            ].copy()

            clientes_que_pagaram_matriculas = df_pagamentos_campanha['MATRICULA'].nunique()
            valor_total_arrecadado = df_pagamentos_campanha['VALOR_PAGO'].sum() if not df_pagamentos_campanha.empty else 0
            taxa_eficiencia_clientes = (clientes_que_pagaram_matriculas / total_clientes_notificados * 100) if total_clientes_notificados > 0 else 0
            taxa_eficiencia_valor = (valor_total_arrecadado / total_divida_notificados * 100) if total_divida_notificados > 0 else 0
            ticket_medio = (valor_total_arrecadado / clientes_que_pagaram_matriculas) if clientes_que_pagaram_matriculas > 0 else 0

            st.subheader("Resultados da Análise da Campanha")

            # Primeira linha de métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(label="Total de clientes notificados", value=f"{total_clientes_notificados}")
            with col2:
                st.metric(label="Clientes que pagaram na janela", value=f"{clientes_que_pagaram_matriculas}")
            with col3:
                st.metric(label="Taxa de eficiência (clientes)", value=f"{taxa_eficiencia_clientes:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
            with col4:
                st.metric(label="Ticket médio", value=f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            # Segunda linha de métricas
            col5, col6, col7 = st.columns(3)
            with col5:
                st.metric(label="Valor total arrecadado na campanha", value=f"R$ {valor_total_arrecadado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col6:
                st.metric(label="Total da dívida dos notificados", value=f"R$ {total_divida_notificados:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col7:
                st.metric(label="Taxa de eficiência (valor)", value=f"{taxa_eficiencia_valor:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))

            if not df_pagamentos_campanha.empty:

                # ALTERAÇÃO: gráficos lado a lado — pagamentos por dia e por canal de pagamento
                
                
            				st.subheader(f"Pagamentos por Dia Após o Envio (Janela de {janela_dias} dias)")

                    df_pagamentos_campanha['DIAS_APOS_ENVIO'] = (df_pagamentos_campanha['DATA_PAGAMENTO'] - df_pagamentos_campanha['DATA_ENVIO']).dt.days

                    pagamentos_por_dia = df_pagamentos_campanha.groupby('DIAS_APOS_ENVIO')['VALOR_PAGO'].sum().reset_index()
                    pagamentos_por_dia.rename(columns={'DIAS_APOS_ENVIO': 'Dias Após Envio', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)

                    fig_dias = px.bar(
                        pagamentos_por_dia,
                        x='Dias Após Envio',
                        y='Valor Total Pago',
                        title='Valor Arrecadado por Dia Após o Envio',
                        labels={'Dias Após Envio': 'Dias Após o Envio', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                        hover_data={'Valor Total Pago': ':.2f'}
                    )
                    fig_dias.update_layout(xaxis_title="Dias Após o Envio", yaxis_title="Valor Total Pago (R$)")
                    st.plotly_chart(fig_dias, use_container_width=True)
                
                
                    # ALTERAÇÃO: gráfico de valor arrecadado por canal de pagamento
                    if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                        st.subheader("Valor Arrecadado por Canal de Pagamento")

                        pagamentos_por_canal = df_pagamentos_campanha.groupby('TIPO_PAGAMENTO')['VALOR_PAGO'].sum().reset_index()
                        pagamentos_por_canal.rename(columns={'TIPO_PAGAMENTO': 'Canal de Pagamento', 'VALOR_PAGO': 'Valor Total Pago'}, inplace=True)
                        pagamentos_por_canal = pagamentos_por_canal.sort_values('Valor Total Pago', ascending=False)

                        fig_canal = px.bar(
                            pagamentos_por_canal,
                            x='Canal de Pagamento',
                            y='Valor Total Pago',
                            title='Valor Arrecadado por Canal de Pagamento',
                            labels={'Canal de Pagamento': 'Canal de Pagamento', 'Valor Total Pago': 'Valor Total Pago (R$)'},
                            hover_data={'Valor Total Pago': ':.2f'},
                            color='Canal de Pagamento'
                        )
                        fig_canal.update_layout(
                            xaxis_title="Canal de Pagamento",
                            yaxis_title="Valor Total Pago (R$)",
                            showlegend=False
                        )
                        st.plotly_chart(fig_canal, use_container_width=True)
                    else:
                        st.info("Coluna 'Tipo Pagamento' não encontrada no arquivo de pagamentos.")

		                st.subheader("Detalhes dos Pagamentos Atribuídos à Campanha")

                # Colunas para exibição, incluindo TIPO_PAGAMENTO se disponível
                colunas_exibicao = ['MATRICULA', 'TELEFONE_ENVIO', 'DATA_ENVIO', 'DATA_PAGAMENTO', 'VALOR_PAGO', 'DIAS_APOS_ENVIO']
                if 'TIPO_PAGAMENTO' in df_pagamentos_campanha.columns:
                    colunas_exibicao.append('TIPO_PAGAMENTO')

                df_detalhes_pagamentos = df_pagamentos_campanha[colunas_exibicao].drop_duplicates(
                    subset=['MATRICULA', 'DATA_PAGAMENTO', 'VALOR_PAGO']
                )

                st.dataframe(df_detalhes_pagamentos)

                csv_output = df_detalhes_pagamentos.to_csv(index=False, sep=';', decimal=',')
                st.download_button(
                    label="Baixar Detalhes dos Pagamentos da Campanha (CSV)",
                    data=csv_output,
                    file_name="pagamentos_campanha.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum pagamento encontrado dentro da janela definida para a campanha.")

        else:
            st.error("Não foi possível processar um ou mais arquivos. Verifique os formatos e as colunas esperadas ou se há matrículas válidas após o cruzamento.")
    else:
        st.warning("Por favor, carregue todos os três arquivos para iniciar a análise.")
