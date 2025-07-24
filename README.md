# Agente Gera SQL

Este projeto é uma aplicação Streamlit que utiliza um agente de IA para gerar consultas SQL a partir de instruções em linguagem natural.

## Funcionalidades

- Interface web interativa com Streamlit.
- Geração automática de comandos SQL a partir de perguntas ou instruções do usuário.
- Exibição do SQL gerado e possibilidade de copiar para área de transferência.
- Histórico das consultas realizadas.

## Como usar

1. Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
2. Execute o aplicativo:
    ```bash
    streamlit run app_streamlit.py
    ```
3. Acesse o endereço fornecido pelo Streamlit no navegador.

## Estrutura do Código

- `app_streamlit.py`: Arquivo principal da aplicação. Contém a interface Streamlit, integração com o agente de IA e lógica de geração de SQL.

## Exemplo de Uso

Digite uma instrução como:
```
Gera ruma consulta SQL com base nas tabelas selecionadas
```
O agente irá gerar a consulta SQL correspondente e exibi-la na tela.

## Requisitos

- Python 3.8+
- Streamlit
- Gerar uma chave de API na OpenAI (https://openai.com/pt-BR/)
- Outras dependências listadas em `requirements.txt`

## Arquivos

- app_streamlit.py (arquivo principal do projeto)
- .env_example (arquivo )
- schema_example.json (modelo de schema para teste)

## Licença

Este projeto está sob a licença MIT.
