import json
import os
from dotenv import load_dotenv
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

# Carrega variáveis de ambiente do .env
load_dotenv()

# ============================ Funções Auxiliares ============================


def carregar_schema_textual(schema_dict, incluir_tabelas, nome_schema=""):
    """Gera uma descrição textual do schema das tabelas selecionadas, com nome do schema."""
    linhas = []
    for tabela in incluir_tabelas:
        if tabela not in schema_dict:
            continue
        dados = schema_dict[tabela]
        comentario_tabela = dados.get("comment", "Sem comentário")
        nome_completo = f"{nome_schema}.{tabela}" if nome_schema else tabela
        linhas.append(f"Tabela: {nome_completo} ({comentario_tabela})")
        for col in dados["columns"]:
            col_name = col["name"]
            col_type = col["data_type"]
            pk = "PK" if col["is_primary_key"] else ""
            fk = (
                f"FK → {col['references']}"
                if col["is_foreign_key"] and col["references"]
                else ""
            )
            anotacoes = " / ".join(filter(None, [pk, fk]))
            anotacoes = f" ({anotacoes})" if anotacoes else ""
            comentario = col.get("comment", "Sem comentário").strip()
            linhas.append(f"- {col_name} ({col_type}){anotacoes} — {comentario}")
        linhas.append("")
    return "\n".join(linhas)


def detectar_tabelas(pergunta, schema_dict):
    """Detecta nomes de tabelas mencionados na pergunta."""
    palavras = set(pergunta.lower().split())
    return [t for t in schema_dict if t.lower() in palavras]


# ============================ Interface Streamlit ============================

st.set_page_config(page_title="SQL Generator", layout="wide")
col1, col2 = st.columns([1, 1])
with col1:
    st.markdown(
        "<h3 style='text-align: center; font-size: 24px;'>Conversor de Perguntas em SQL</h3>",
        unsafe_allow_html=True,
    )


col3, col4 = st.columns([1, 1])
with col3:
    arquivo = st.file_uploader(
        "📂 Faça upload do arquivo `schema.json`", type="json", disabled=False
    )

if arquivo:
    schema_dict = json.load(arquivo)
    with col4:
        st.write("")
        st.write("")
        st.success("✅ Schema carregado com sucesso!")
        # st.json(schema_dict, expanded=False)

    # Inicializa estados
    if "limpar_campos" not in st.session_state:
        st.session_state["limpar_campos"] = False
    if "pergunta" not in st.session_state:
        st.session_state["pergunta"] = ""
    if "tabelas_detectadas" not in st.session_state:
        st.session_state["tabelas_detectadas"] = []

    if st.session_state["limpar_campos"]:
        st.session_state["pergunta"] = ""
        st.session_state["tabelas_detectadas"] = []
        st.session_state["limpar_campos"] = False
        st.rerun()

    # Campo de texto para a pergunta
    pergunta_usuario = st.text_area(
        "💬 Descreva sua consuta : *",
        value=st.session_state["pergunta"],
        placeholder="Ex: Descreva sua consulta",
    )

    # Atualiza a pergunta
    st.session_state["pergunta"] = pergunta_usuario

    # Atualiza as tabelas detectadas apenas se for a primeira vez
    if not st.session_state["tabelas_detectadas"] and pergunta_usuario:
        st.session_state["tabelas_detectadas"] = detectar_tabelas(
            pergunta_usuario, schema_dict
        )

    # Nome do schema SQL
    nome_schema = st.sidebar.text_input(
        "Informe o nome do schema",
        placeholder='Exemplo: "b2b0bef6-545f-11f0-ad81-86f9ff72f4df"',
    ).strip()

    st.sidebar.markdown("### 📌 Tabelas e colunas")

    # Widget multiselect controlado apenas por Streamlit
    tabelas_selecionadas = st.sidebar.multiselect(
        "Selecione as tabelas a usar",
        options=list(schema_dict.keys()),
        default=st.session_state["tabelas_detectadas"],
        placeholder="Selecione as tabelas",
        key="tabelas_selecionadas",
    )

    # Interface para seleção de colunas
    colunas_selecionadas_por_tabela = {}
    for tabela in st.session_state["tabelas_selecionadas"]:
        st.sidebar.markdown(f"#### 🧩 Selecione colunas da tabela `{tabela}`")
        colunas = [col["name"] for col in schema_dict[tabela]["columns"]]
        colunas_selecionadas = []
        for col in colunas:
            if st.sidebar.checkbox(col, key=f"{tabela}_{col}"):
                colunas_selecionadas.append(col)
        colunas_selecionadas_por_tabela[tabela] = colunas_selecionadas

    # Botões
    col_esq, col_meio, col_dir = st.columns([1, 5, 1])

    with col_esq:
        gerar_sql = st.button("🚀 Gerar SQL")

    with col_meio:
        gerar_codigo = st.button("🤖 Gerar Código Python")

    with col_dir:
        limpar = st.button("🧹 Limpar Campos")

    if limpar:
        st.session_state["limpar_campos"] = True
        st.rerun()

    if gerar_codigo:

        if not st.session_state["pergunta"]:
            st.warning("❗ Digite uma pergunta para gerar a SQL.")
        elif not st.session_state["tabelas_selecionadas"]:
            st.warning("❗ Selecione ao menos uma tabela.")
        else:
            schema_textual = carregar_schema_textual(
                schema_dict,
                st.session_state["tabelas_selecionadas"],
                nome_schema=nome_schema,
            )
            with col4:
                with st.expander("📖 Schema contextualizado"):
                    st.code(schema_textual, language="markdown")

            colunas_contexto = ""
            for tabela, colunas in colunas_selecionadas_por_tabela.items():
                nome_tabela = f"{nome_schema}.{tabela}" if nome_schema else tabela
                colunas_str = ", ".join(colunas) if colunas else "todas as colunas"
                colunas_contexto += f"- {nome_tabela}: {colunas_str}\n"

            # Configura LLM
            llm = ChatOpenAI(
                temperature=0,
                model="gpt-3.5-turbo",
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            prompt = PromptTemplate(
                input_variables=["pergunta"],
                template=f"""
                            Você é um assistente SQL útil que converte perguntas em português para gerar um script utilizando sqlalchemy.
                            Sua tarefa é gerar a query considerando o seguinte schema do banco de dados PostgreSQL:

                            {schema_textual}

                            O usuário selecionou as seguintes colunas para exibir na consulta:
                            {colunas_contexto}

                            Considere que as tabelas estão no schema SQL chamado "{nome_schema}". Use esse schema ao referenciar as tabelas (ex: {nome_schema}.tabela).

                            Com base nesse schema e nessas colunas, escreva uma função utilizando e python SqlAlchemy versão 1.4 (sem explicações) para responder à pergunta abaixo.
                            Importante: nunca use apelidos ou alias para os nomes das tabelas.

                            Pergunta: {{pergunta}}
                            SQL:""",
            ).partial(schema=schema_textual)

            sql_chain = prompt | llm
            resposta = sql_chain.invoke({"pergunta": st.session_state["pergunta"]})
            sql_final = resposta.content.strip()

            with st.container():
                st.markdown(
                    """
                    <style>
                    div[data-testid="stContainer"] > div {
                        border: 1px solid #cccccc;
                        border-radius: 10px;
                        padding: 15px;
                        background-color: #f9f9f9;
                        margin-bottom: 20px;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                st.code(sql_final, language="sql")
                st.download_button(
                    label="💾 Baixar como .sql",
                    data=sql_final.encode("utf-8"),
                    file_name="consulta.sql",
                    mime="text/sql",
                )

    if gerar_sql:
        if not st.session_state["pergunta"]:
            st.warning("❗ Digite uma pergunta para gerar a SQL.")
        elif not st.session_state["tabelas_selecionadas"]:
            st.warning("❗ Selecione ao menos uma tabela.")
        else:
            schema_textual = carregar_schema_textual(
                schema_dict,
                st.session_state["tabelas_selecionadas"],
                nome_schema=nome_schema,
            )
            with col4:
                with st.expander("📖 Schema contextualizado"):
                    st.code(schema_textual, language="markdown")

            colunas_contexto = ""
            for tabela, colunas in colunas_selecionadas_por_tabela.items():
                nome_tabela = f"{nome_schema}.{tabela}" if nome_schema else tabela
                colunas_str = ", ".join(colunas) if colunas else "todas as colunas"
                colunas_contexto += f"- {nome_tabela}: {colunas_str}\n"

            # Configura LLM
            llm = ChatOpenAI(
                temperature=0,
                model="gpt-3.5-turbo",
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            prompt = PromptTemplate(
                input_variables=["pergunta"],
                template=f"""
                            Você é um assistente SQL útil que converte perguntas em português para gerar um script SQL para utilizar em Postgres no PGAdmin.
                            Sua tarefa é gerar a query considerando o seguinte schema do banco de dados PostgreSQL:

                            {schema_textual}

                            O usuário selecionou as seguintes colunas para exibir na consulta:
                            {colunas_contexto}

                            Considere que as tabelas estão no schema SQL chamado "{nome_schema}". Use esse schema ao referenciar as tabelas (ex: {nome_schema}.tabela).

                            Com base nesse schema e nessas colunas, escreva uma função utilizando e python SQL (sem explicações) para responder à pergunta abaixo.
                            Importante: nunca use apelidos ou alias para os nomes das tabelas.

                            Pergunta: {{pergunta}}
                            SQL:""",
            ).partial(schema=schema_textual)

            sql_chain = prompt | llm
            resposta = sql_chain.invoke({"pergunta": st.session_state["pergunta"]})
            sql_final = resposta.content.strip()

            with st.container():
                st.markdown(
                    """
                    <style>
                    div[data-testid="stContainer"] > div {
                        border: 1px solid #cccccc;
                        border-radius: 10px;
                        padding: 15px;
                        background-color: #f9f9f9;
                        margin-bottom: 20px;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                st.code(sql_final, language="sql")
                st.download_button(
                    label="💾 Baixar como .sql",
                    data=sql_final.encode("utf-8"),
                    file_name="consulta.sql",
                    mime="text/sql",
                )
