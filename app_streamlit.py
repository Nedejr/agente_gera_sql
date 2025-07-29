import json
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma
from langchain.schema.document import Document
from langchain_openai import OpenAIEmbeddings

# Carrega variáveis de ambiente do .env
load_dotenv()

CHROMA_PATH = "./chroma_schema"
CHROMA_COLLECTION = "schema_docs"

# ============================ Funções Auxiliares ============================


def detectar_tabelas(pergunta, schema_dict):
    palavras = set(pergunta.lower().split())
    return [t for t in schema_dict if t.lower() in palavras]


def schema_dict_para_documentos(schema_dict, nome_schema=""):
    documentos = []
    for tabela, dados in schema_dict.items():
        nome_completo = f"{nome_schema}.{tabela}" if nome_schema else tabela
        comentario_tabela = dados.get("comment", "Sem comentário")
        texto_tabela = f"Tabela: {nome_completo} — {comentario_tabela}\n"
        for col in dados["columns"]:
            col_name = col["name"]
            col_type = col["data_type"]
            pk = "PK" if col["is_primary_key"] else ""
            fk = (
                f"FK → {col['references']}"
                if col["is_foreign_key"] and col["references"]
                else ""
            )
            comentario = col.get("comment", "Sem comentário")
            anotacoes = " / ".join(filter(None, [pk, fk]))
            texto_tabela += f"- {col_name} ({col_type})"
            if anotacoes:
                texto_tabela += f" [{anotacoes}]"
            texto_tabela += f" — {comentario}\n"
        documentos.append(texto_tabela.strip())
    return documentos


def salvar_schema_no_chroma(
    schema_dict, nome_schema="", collection_name=CHROMA_COLLECTION
):
    embedding = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))

    colecao_path = Path(CHROMA_PATH) / collection_name
    if colecao_path.exists():
        print(colecao_path.exists())
        st.sidebar.info(
            f"ℹ️ A coleção `{collection_name}` já existe. Pulando criação para economizar tokens."
        )

        with st.sidebar.expander("⚙️ Opções avançadas"):
            if st.button(
                "🗑️ Resetar embeddings (remover coleção existente)",
                key="resetar_embeddings",
            ):
                resetar_colecao_chroma()
                st.rerun()
        return

    # Criação de nova coleção
    documentos_texto = schema_dict_para_documentos(schema_dict, nome_schema)
    docs = [Document(page_content=doc) for doc in documentos_texto]

    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embedding,
        collection_name=collection_name,
        persist_directory=CHROMA_PATH,
    )
    vectordb.persist()

    st.sidebar.success(f"✅ Coleção `{collection_name}` criada com sucesso.")


def buscar_contexto_chroma(pergunta, collection_name=CHROMA_COLLECTION):
    embedding = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embedding,
        persist_directory=CHROMA_PATH,
    )
    docs_relevantes = vectordb.similarity_search(pergunta, k=4)
    return "\n\n".join([doc.page_content for doc in docs_relevantes])


def resetar_colecao_chroma():
    chroma_dir = Path(CHROMA_PATH)
    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
        st.warning("⚠️ Todas as coleções foram removidas (diretório Chroma apagado).")
    else:
        st.info("ℹ️ Nenhuma coleção encontrada para remover.")


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
    salvar_schema_no_chroma(schema_dict)

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

    pergunta_usuario = st.text_area(
        "💬 Descreva sua consuta : *",
        value=st.session_state["pergunta"],
        placeholder="Ex: Descreva sua consulta",
    )
    st.session_state["pergunta"] = pergunta_usuario

    if not st.session_state["tabelas_detectadas"] and pergunta_usuario:
        st.session_state["tabelas_detectadas"] = detectar_tabelas(
            pergunta_usuario, schema_dict
        )

    nome_schema = st.sidebar.text_input(
        "Informe o nome do schema",
        placeholder='Exemplo: "b2b0bef6-545f-11f0-ad81-86f9ff72f4df"',
    ).strip()

    st.sidebar.markdown("### 📌 Tabelas e colunas")

    tabelas_selecionadas = st.sidebar.multiselect(
        "Selecione as tabelas a usar",
        options=list(schema_dict.keys()),
        default=st.session_state["tabelas_detectadas"],
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

    if gerar_codigo or gerar_sql:
        if not st.session_state["pergunta"]:
            st.warning("❗ Digite uma pergunta para gerar a SQL.")
        elif not st.session_state["tabelas_selecionadas"]:
            st.warning("❗ Selecione ao menos uma tabela.")
        else:
            schema_textual = buscar_contexto_chroma(pergunta_usuario)

            with col4:
                with st.expander("📖 Schema contextualizado"):
                    st.code(schema_textual, language="markdown")

            colunas_contexto = ""
            for tabela, colunas in colunas_selecionadas_por_tabela.items():
                nome_tabela = f"{nome_schema}.{tabela}" if nome_schema else tabela
                colunas_str = ", ".join(colunas) if colunas else "todas as colunas"
                colunas_contexto += f"- {nome_tabela}: {colunas_str}\n"

            modelo = "gpt-3.5-turbo"
            tarefa = (
                "gerar uma função Python usando SQLAlchemy"
                if gerar_codigo
                else "gerar uma consulta SQL PostgreSQL"
            )

            llm = ChatOpenAI(
                temperature=0, model=modelo, api_key=os.getenv("OPENAI_API_KEY")
            )

            prompt = PromptTemplate(
                input_variables=["pergunta"],
                template=f"""
                        Você é um assistente que converte perguntas em português para {tarefa}.

                        Schema:
                        {schema_textual}

                        Colunas selecionadas:
                        {colunas_contexto}

                        Considere que o schema SQL é "{nome_schema}" e deve ser incluído nos nomes das tabelas (ex: {nome_schema}.tabela).

                        Pergunta: {{pergunta}}
                        Resultado:""",
            ).partial(schema=schema_textual)

            resposta = (prompt | llm).invoke({"pergunta": pergunta_usuario})
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
