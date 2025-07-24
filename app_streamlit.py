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
st.markdown(
    "<h3 style='text-align: center; font-size: 24px;'>Conversor de Perguntas em SQL</h3>",
    unsafe_allow_html=True,
)

arquivo = st.file_uploader(
    "📂 Faça upload do arquivo `schema.json`",
    type="json",
)

if arquivo:
    schema_dict = json.load(arquivo)
    st.success("✅ Schema carregado com sucesso!")

    if "limpar_campos" not in st.session_state:
        st.session_state["limpar_campos"] = False

    if st.session_state["limpar_campos"]:
        st.session_state["pergunta"] = ""
        st.session_state["tabelas_selecionadas"] = []
        st.session_state["limpar_campos"] = False
        st.rerun()

    if "pergunta" not in st.session_state:
        st.session_state["pergunta"] = ""
    if "tabelas_selecionadas" not in st.session_state:
        st.session_state["tabelas_selecionadas"] = []

    pergunta = st.text_area(
        "💬 Pergunta em português",
        placeholder="Ex: Gerar consulta",
        key="pergunta",
    )

    tabelas_detectadas = (
        detectar_tabelas(st.session_state["pergunta"], schema_dict)
        if st.session_state["pergunta"]
        else []
    )

    nome_schema = st.sidebar.text_input(
        "Informe o nome do schema",
        placeholder='Exemplo: "b2b0bef6-545f-11f0-ad81-86f9ff72f4df"',
    ).strip()

    st.sidebar.markdown("### 📌 Tabelas e colunas")

    tabelas_selecionadas = st.sidebar.multiselect(
        "Selecione as tabelas a usar",
        options=list(schema_dict.keys()),
        default=tabelas_detectadas,
        placeholder="Selecione as tabelas",
        key="tabelas_selecionadas",
    )

    colunas_selecionadas_por_tabela = {}
    for tabela in st.session_state["tabelas_selecionadas"]:
        st.sidebar.markdown(f"#### 🧩 Selecione colunas da tabela `{tabela}`")
        colunas = [col["name"] for col in schema_dict[tabela]["columns"]]

        colunas_selecionadas = []
        for col in colunas:
            if st.sidebar.checkbox(col, key=f"{tabela}_{col}"):
                colunas_selecionadas.append(col)

        colunas_selecionadas_por_tabela[tabela] = colunas_selecionadas

    col1, col2 = st.columns([1, 1])
    with col1:
        gerar_sql = st.button("🚀 Gerar SQL")
    with col2:
        limpar = st.button("🧹 Limpar Campos")

    if limpar:
        st.session_state["limpar_campos"] = True
        st.rerun()

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

            with st.expander("📖 Schema contextualizado"):
                st.code(schema_textual, language="markdown")

            colunas_contexto = ""
            for tabela, colunas in colunas_selecionadas_por_tabela.items():
                nome_tabela = f"{nome_schema}.{tabela}" if nome_schema else tabela
                if colunas:
                    colunas_str = ", ".join(colunas)
                else:
                    colunas_str = "todas as colunas"
                colunas_contexto += f"- {nome_tabela}: {colunas_str}\n"

            llm = ChatOpenAI(
                temperature=0,
                model="gpt-3.5-turbo",
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            prompt = PromptTemplate(
                input_variables=["pergunta"],
                template=f"""
Você é um assistente SQL útil que converte perguntas em português para SQL.
Sua tarefa é gerar a query considerando o seguinte schema do banco de dados PostgreSQL:

{schema_textual}

O usuário selecionou as seguintes colunas para exibir na consulta:
{colunas_contexto}

Considere que as tabelas estão no schema SQL chamado "{nome_schema}". Use esse schema ao referenciar as tabelas (ex: {nome_schema}.tabela).

Com base nesse schema e nessas colunas, escreva apenas a consulta SQL (sem explicações) para responder à pergunta abaixo.
Importante nunca usar apelidos ou alias para os nomes das tabelas.

Pergunta: {{pergunta}}
SQL:""",
            ).partial(schema=schema_textual)

            sql_chain = prompt | llm
            resposta = sql_chain.invoke({"pergunta": st.session_state["pergunta"]})
            sql_final = resposta.content.strip()

            st.subheader("📌 SQL Gerada")
            st.code(sql_final, language="sql")

            st.download_button(
                label="💾 Baixar como .sql",
                data=sql_final.encode("utf-8"),
                file_name="consulta.sql",
                mime="text/sql",
            )
