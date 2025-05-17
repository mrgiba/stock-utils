# Extrator de Dados de Transações Morgan Stanley

Este projeto automatiza a extração de dados de transações de ações da Morgan Stanley

## Funcionalidades

- Extrai automaticamente dados de transações de PDFs da Morgan Stanley usando AWS Bedrock (Claude 3.7 Sonnet)
- Busca taxas de câmbio automaticamente da API do Banco Central do Brasil (API Olinda)
- Gera arquivos CSV formatados

## Requisitos

- Python 3.8+
- Credenciais AWS configuradas para acesso ao Bedrock
- Conexão com internet para acesso à API do Banco Central

## Instalação

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

## Configuração AWS

1. Configure suas credenciais AWS:
   ```
   aws configure
   ```

2. Para alterar a região AWS (padrão é a região configurada no perfil):
   ```
   export AWS_DEFAULT_REGION=us-west-2
   ```

## Estrutura do Projeto

- `extract_morgan.py`: Script principal para extração de dados
- `llm.py`: Módulo para interação com o AWS Bedrock
- `exchange_rates.py`: Módulo para obtenção de taxas de câmbio do Banco Central
- `requirements.txt`: Dependências do projeto
- `input/`: Diretório para armazenar os PDFs de entrada
- `output/`: Diretório onde os arquivos CSV serão gerados

## Uso

Execute o script principal passando o caminho para o PDF da Morgan Stanley:

```
python extract_morgan.py caminho/para/seu/arquivo.pdf
```

O script irá:
1. Extrair os dados do PDF usando o Claude via AWS Bedrock
2. Buscar automaticamente as taxas de câmbio do Banco Central (pressione Ctrl+C para inserir manualmente)
3. Gerar um arquivo CSV com os dados formatados

## Formato de PDF Suportado

O extrator foi projetado para trabalhar com os PDFs de confirmação de transação da Morgan Stanley.

## Taxas de Câmbio

O script busca automaticamente as taxas de câmbio do Banco Central do Brasil para as datas de transação e aquisição:

- Para venda de ações (recebimento de USD): usa a taxa de **compra** do dólar
- Para compra de ações (pagamento em USD): usa a taxa de **venda** do dólar

Caso não seja possível obter as taxas automaticamente (por exemplo, em feriados ou finais de semana), o script tentará buscar a taxa do dia útil anterior.

Se você preferir inserir as taxas manualmente, pressione Ctrl+C durante a busca automática.

