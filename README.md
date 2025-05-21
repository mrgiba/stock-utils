# Stock Utils - Ferramentas para Gestão de Ações

Este projeto inclui ferramentas para automatizar a extração de dados de transações de ações da Morgan Stanley e consultar cotações do dólar do Banco Central do Brasil

## Funcionalidades

- Extrai automaticamente dados de transações de PDFs da Morgan Stanley usando AWS Bedrock (Claude 3.7 Sonnet)
- Busca taxas de câmbio automaticamente da API do Banco Central do Brasil (API Olinda)
- Gera arquivos CSV formatados

## Requisitos

- Python 3.11+
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

### Conversão para formato Bastter System

Para converter os dados de transações para o formato aceito pelo Bastter System:

```
python convert_to_bastter.py [opções]
```

Opções disponíveis:
- `-i, --input ARQUIVO`: Especifica o arquivo CSV de entrada (padrão: transacoes.csv)
- `-o, --output ARQUIVO`: Especifica o arquivo XLSX de saída (padrão: bastter_import.xlsx)

Exemplos:
```
# Usar os nomes de arquivo padrão
python convert_to_bastter.py

# Especificar arquivos de entrada e saída
python convert_to_bastter.py -i minhas_transacoes.csv -o importar_bastter.xlsx
```

O script irá:
1. Ler o arquivo CSV de entrada
2. Processar os dados conforme o formato do Bastter System:
   - 1ª coluna: ticker
   - 2ª coluna: data
   - 3ª coluna: quantidade (positiva para compra, negativa para venda)
   - 4ª coluna: total + custos (para compra) / total - custos (para venda)
   - 5ª coluna: 0,00 (para compra) / total sem descontar custos (para venda)
3. Gerar um arquivo XLSX pronto para importação no Bastter System

## Formato de PDF Suportado

O extrator foi projetado para trabalhar com os PDFs de confirmação de transação da Morgan Stanley.

## Taxas de Câmbio

O script busca automaticamente as taxas de câmbio do Banco Central do Brasil para as datas de transação e aquisição:

- Para venda de ações (recebimento de USD): usa a taxa de **compra** do dólar
- Para compra de ações (pagamento em USD): usa a taxa de **venda** do dólar

Caso não seja possível obter as taxas automaticamente (por exemplo, em feriados ou finais de semana), o script tentará buscar a taxa do dia útil anterior.

Se você preferir inserir as taxas manualmente, pressione Ctrl+C durante a busca automática.

### Utilitário de Consulta de Cotações

O projeto também inclui um utilitário independente para consultar cotações do dólar diretamente do Banco Central:

```
python cotacao_dolar_bcb.py [opções]
```

Opções disponíveis:
- `-d, --data DATA`: Consulta cotação para uma data específica (formato DD/MM/AAAA)
- `-p, --periodo INICIO FIM`: Consulta cotações para um período (formato DD/MM/AAAA DD/MM/AAAA)
- `-o, --output ARQUIVO`: Salva os resultados em um arquivo CSV
- `--quiet`: Não exibe os resultados na tela

Exemplos:
```
# Consultar cotação para uma data específica
python cotacao_dolar_bcb.py -d 15/05/2023

# Consultar cotações para um período e salvar em CSV
python cotacao_dolar_bcb.py -p 01/01/2023 31/01/2023 -o cotacoes_janeiro.csv
```

