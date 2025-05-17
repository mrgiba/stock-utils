import os
import argparse
import json
import re
import sys
import csv
from datetime import datetime
from llm import invoke_llm, extract_last_item_from_tagged_list
from exchange_rates import get_exchange_rates_interactive
import traceback


def convert_date_format(date_str):
    """Converte formato de data para DD/MM/YYYY"""
    # Trata formato 'Month DD, YYYY' (ex: "June 5, 2023")
    months = {
        'January': '01', 'February': '02', 'March': '03', 'April': '04',
        'May': '05', 'June': '06', 'July': '07', 'August': '08',
        'September': '09', 'October': '10', 'November': '11', 'December': '12'
    }

    for month_name, month_num in months.items():
        if month_name in date_str:
            pattern = rf"{month_name}\s+(\d+),\s+(\d{{4}})"
            match = re.search(pattern, date_str)
            if match:
                day = match.group(1).zfill(2)
                year = match.group(2)
                return f"{day}/{month_num}/{year}"

    # Outros formatos comuns
    date_formats = [
        ('%m/%d/%Y', '%d/%m/%Y'),  # MM/DD/YYYY -> DD/MM/YYYY
        ('%d-%m-%Y', '%d/%m/%Y'),  # DD-MM-YYYY -> DD/MM/YYYY
    ]

    for input_fmt, output_fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str, input_fmt)
            return date_obj.strftime(output_fmt)
        except ValueError:
            continue

    return date_str


def format_currency_usd(amount):
    """Formata valor em formato decimal brasileiro sem símbolo de moeda"""
    return f"{amount:.2f}".replace('.', ',')


def format_currency_brl(amount):
    """Formata valor em formato decimal brasileiro sem símbolo de moeda"""
    return f"{amount:.2f}".replace('.', ',')


def format_number_br(value):
    """Formata número no formato decimal brasileiro (vírgula como separador decimal)"""
    return f"{value:.4f}".replace('.', ',')


def get_pdf_files(pdf_paths, is_directory):
    """
    Obtém a lista de arquivos PDF a serem processados.
    
    Args:
        pdf_paths: Lista de caminhos fornecidos pelo usuário
        is_directory: Se True, trata o primeiro caminho como um diretório
        
    Returns:
        list: Lista de caminhos de arquivos PDF
    """
    
    if is_directory:
        # Assume que o primeiro argumento é um diretório
        pdf_dir = pdf_paths[0]
        if not os.path.isdir(pdf_dir):
            print(f"Erro: '{pdf_dir}' não é um diretório válido.")
            sys.exit(1)
            
        # Lista todos os arquivos PDF no diretório
        pdf_files = [os.path.join(pdf_dir, f) for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        if not pdf_files:
            print(f"Nenhum arquivo PDF encontrado no diretório '{pdf_dir}'.")
            sys.exit(1)
    else:
        # Usa os caminhos fornecidos diretamente
        pdf_files = pdf_paths
        # Verifica se todos os arquivos existem
        for pdf_path in pdf_files:
            if not os.path.exists(pdf_path):
                print(f"Erro: O arquivo PDF '{pdf_path}' não existe.")
                sys.exit(1)
    
    return pdf_files


def display_transaction_data(transaction_data):
    """
    Exibe os dados da transação extraídos do PDF.
    
    Args:
        transaction_data: Dicionário com os dados da transação
    """
    print("\nDados de Transação Extraídos:")
    print(f"Data: {convert_date_format(transaction_data['transaction_date'])}")
    print(f"Ação: {transaction_data['ticker']}")
    print(f"Quantidade: {transaction_data['quantity']}")
    print(f"Preço por Ação: ${transaction_data['share_value']}")
    print(f"Valor Total: ${transaction_data['total_value']}")
    print(f"Comissão: ${transaction_data['commission']}")
    print(f"Taxa Suplementar: ${transaction_data['supplemental_fee']}")
    
    print("\nLotes de Aquisição:")
    for j, lot in enumerate(transaction_data['acquisition_lots']):
        print(f"  Lote {j+1}:")
        print(f"    Data: {convert_date_format(lot['acquisition_date'])}")
        print(f"    Quantidade: {lot['quantity']}")
        print(f"    Custo por Ação: ${lot['cost_basis_per_share']}")


def get_exchange_rates(transaction_data):
    """
    Obtém as taxas de câmbio para as datas de transação e aquisição.
    
    Args:
        transaction_data: Dicionário com os dados da transação
        
    Returns:
        tuple: (taxa_transacao, [taxas_aquisicao])
    """
    # Formata a data da transação para o formato DD/MM/YYYY para uso na API do Banco Central
    transaction_date = convert_date_format(transaction_data['transaction_date'])
    
    # Coleta todas as datas de aquisição para buscar taxas de câmbio
    acquisition_dates = [convert_date_format(lot['acquisition_date']) for lot in transaction_data['acquisition_lots']]
    
    print("\nBuscando taxas de câmbio para a data da transação e todas as datas de aquisição...")
    
    # Obtém as taxas de câmbio automaticamente ou manualmente
    # Primeiro para a data da transação
    print(f"\nBuscando taxa para data da venda ({transaction_date})...")
    transaction_rate = get_exchange_rates_interactive(transaction_date, None)[0]
    
    # Agora para cada data de aquisição
    acquisition_rates = []
    for date in acquisition_dates:
        print(f"\nBuscando taxa para data de aquisição ({date})...")
        acquisition_rate = get_exchange_rates_interactive(None, date)[1]
        acquisition_rates.append(acquisition_rate)
    
    # Combina as taxas
    return (transaction_rate, acquisition_rates)


def create_csv(transaction_data, exchange_rates, output_dir="output"):
    """Cria arquivo CSV com dados da transação, suportando múltiplos lotes de aquisição"""
    transaction_rate, acquisition_rates = exchange_rates
    
    # Valores comuns para todas as linhas
    costs = transaction_data["commission"] + transaction_data["supplemental_fee"]
    total_proceeds = transaction_data["total_value"]
    net_proceeds = total_proceeds - costs
    net_proceeds_brl = net_proceeds * transaction_rate  # Taxa de compra para venda de ações
    
    # Formata data da transação
    transaction_date = convert_date_format(transaction_data["transaction_date"])
    
    # Obtém os lotes de aquisição
    acquisition_lots = transaction_data["acquisition_lots"]
    
    # Verifica se a soma das quantidades dos lotes é igual à quantidade total vendida
    total_lot_quantity = sum(lot["quantity"] for lot in acquisition_lots)
    if total_lot_quantity != transaction_data["quantity"]:
        print(f"AVISO: A soma das quantidades dos lotes ({total_lot_quantity}) não corresponde à quantidade total vendida ({transaction_data['quantity']})")
        print("Ajustando proporcionalmente...")
        
        # Ajusta proporcionalmente as quantidades dos lotes
        adjustment_factor = transaction_data["quantity"] / total_lot_quantity
        for lot in acquisition_lots:
            lot["quantity"] = round(lot["quantity"] * adjustment_factor)
        
        # Verifica novamente e ajusta o último lote se necessário
        adjusted_total = sum(lot["quantity"] for lot in acquisition_lots)
        if adjusted_total != transaction_data["quantity"]:
            difference = transaction_data["quantity"] - adjusted_total
            acquisition_lots[-1]["quantity"] += difference
    
    # Cria dados CSV para cada lote
    csv_data = []
    
    # Armazena os valores distribuídos para verificação posterior
    distributed_costs = 0
    distributed_proceeds = 0
    distributed_net_proceeds = 0
    distributed_net_proceeds_brl = 0
    
    for i, lot in enumerate(acquisition_lots):
        # Calcula a proporção deste lote em relação ao total
        lot_proportion = lot["quantity"] / transaction_data["quantity"]
        
        # Distribui os custos e valores proporcionalmente
        # Para o último lote, usamos a diferença para garantir precisão total
        if i == len(acquisition_lots) - 1:
            lot_costs = costs - distributed_costs
            lot_proceeds = total_proceeds - distributed_proceeds
            lot_net_proceeds = net_proceeds - distributed_net_proceeds
            lot_net_proceeds_brl = net_proceeds_brl - distributed_net_proceeds_brl
        else:
            lot_costs = costs * lot_proportion
            lot_proceeds = total_proceeds * lot_proportion
            lot_net_proceeds = net_proceeds * lot_proportion
            lot_net_proceeds_brl = net_proceeds_brl * lot_proportion
            
            # Acumula os valores distribuídos
            distributed_costs += lot_costs
            distributed_proceeds += lot_proceeds
            distributed_net_proceeds += lot_net_proceeds
            distributed_net_proceeds_brl += lot_net_proceeds_brl
        
        # Calcula custos de aquisição para este lote
        acquisition_cost_total = lot["quantity"] * lot["cost_basis_per_share"]
        
        # Obtém a taxa de câmbio para a data de aquisição deste lote
        acquisition_date = convert_date_format(lot["acquisition_date"])
        
        # Se temos apenas uma taxa de aquisição, usamos ela para todos os lotes
        if not isinstance(acquisition_rates, list):
            acquisition_rate = acquisition_rates
        else:
            # Se temos múltiplas taxas, usamos a correspondente ao índice do lote
            # Se não tivermos taxas suficientes, usamos a última
            acquisition_rate = acquisition_rates[min(i, len(acquisition_rates)-1)]
        
        acquisition_cost_brl = acquisition_cost_total * acquisition_rate
        
        # Calcula o lucro real para este lote
        lot_profit_usd = lot_net_proceeds - acquisition_cost_total
        lot_profit_brl = lot_net_proceeds_brl - acquisition_cost_brl
        
        # Cria linha CSV para este lote
        csv_row = {
            "Data": transaction_date,
            "Ação": transaction_data["ticker"],
            "Operação": "venda",
            "Quantidade": lot["quantity"],
            "Valor ação (dolar)": format_currency_usd(transaction_data["share_value"]),
            "Total (dolar)": format_currency_usd(lot_proceeds),
            "Custos": format_currency_usd(lot_costs),
            "Operação - custos": format_currency_usd(lot_net_proceeds),
            "Operação - custos (R$)": format_currency_brl(lot_net_proceeds_brl),
            "Câmbio (compra)": format_number_br(transaction_rate),
            "": "",  # Coluna com título vazio
            "Data aquisição": acquisition_date,
            "Custo aquisição": format_currency_usd(lot["cost_basis_per_share"]),
            "Cambio aquisição (venda)": format_number_br(acquisition_rate),
            "Custo aquisição total": format_currency_usd(acquisition_cost_total),
            "Custo aquisição total (R$)": format_currency_brl(acquisition_cost_brl),
            "Lucro (dolar)": format_currency_usd(lot_profit_usd),
            "Lucro (reais)": format_currency_brl(lot_profit_brl)
        }
        
        csv_data.append(csv_row)
    
    # Cria o diretório de saída se não existir
    os.makedirs(output_dir, exist_ok=True)
    
    # Cria o arquivo CSV no diretório de saída
    output_filename = f"{transaction_data['ticker']}_transaction_{transaction_date.replace('/', '-')}.csv"
    output_path = os.path.join(output_dir, output_filename)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = csv_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\nArquivo CSV criado: {output_path}")

    return output_path


def extract_transaction_data_from_pdf(pdf_path):
    """Extrai dados de transação do PDF usando o Claude via Bedrock Converse"""
    try:
        # Lê o arquivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()

        prompt = """Extraia as seguintes informações de transação deste documento da Morgan Stanley:

1. Data da transação (da seção "Fill summary", quando as ações foram realmente vendidas)
2. Símbolo da ação (ticker)
3. Tipo de operação (venda)
4. Quantidade total de ações vendidas
5. Valor por ação em USD (Market Price per Unit)
6. Valor total da transação em USD (Proceeds)
7. Custo de comissão em USD
8. Taxa suplementar de transação em USD
9. Informações de aquisição para cada lote:
   - Data de aquisição
   - Quantidade de ações neste lote
   - Custo base original por ação em USD para este lote

IMPORTANTE: Pode haver múltiplos lotes de aquisição com datas diferentes. Identifique TODOS os lotes e suas respectivas quantidades e custos base.
        
Comece incluindo todos os pensamentos dentro de tags <thinking>, explorando múltiplos ângulos e abordagens.
Divida a solução em etapas claras dentro de tags <step>. Comece com um orçamento de 50 passos, solicitando mais passos para problemas complexos se necessário.
Use tags <count> após cada etapa para mostrar o orçamento restante. Pare ao chegar a 0.
Ajuste continuamente seu raciocínio com base em resultados e reflexões intermediárias, adaptando sua estratégia conforme avança.
Avalie regularmente o progresso usando tags <reflection>. Seja crítico e honesto sobre seu processo de raciocínio.
Atribua uma pontuação de qualidade entre 0.0 e 1.0 usando tags <reward> após cada reflexão. Use isso para guiar sua abordagem:

0.8+: Continue com a abordagem atual
0.5-0.7: Considere ajustes menores 
Abaixo de 0.5: Considere seriamente voltar atrás e tentar uma abordagem diferente

Se estiver em dúvida ou se a pontuação de recompensa for baixa, volte atrás e tente uma abordagem diferente, explicando sua decisão dentro das tags <thinking>.
Para problemas matemáticos, mostre todo o trabalho explicitamente usando LaTeX para notação formal e forneça provas detalhadas.
Explore múltiplas soluções individualmente se possível, comparando abordagens nas reflexões.
Use os pensamentos como rascunho, escrevendo explicitamente todos os cálculos e raciocínios.

Responda entre tags <answer> com um objeto JSON com esta estrutura:
{
    "transaction_date": "DD-MM-YYYY",
    "ticker": "SYMBOL", 
    "operation_type": "venda",
    "quantity": ###,
    "share_value": ###.##,
    "total_value": ###.##,
    "commission": ##.##,
    "supplemental_fee": #.##,
    "acquisition_lots": [
        {
            "acquisition_date": "DD-MM-YYYY",
            "quantity": ###,
            "cost_basis_per_share": ###.##
        },
        {
            "acquisition_date": "DD-MM-YYYY",
            "quantity": ###,
            "cost_basis_per_share": ###.##
        }
    ]
}
        
Conclua com uma reflexão final sobre a solução geral, discutindo eficácia, desafios e soluções. Atribua uma pontuação final de recompensa.        
        """

        # Chama a função invoke_llm do seu módulo
        response = invoke_llm(
            prompt=prompt,
            document_content=pdf_content,
            document_format="pdf",
            temperature=0,
            max_new_tokens=8192,
            verbose=False
        )

        # Extrai o JSON da resposta
        output_text = response.output
        json_match = extract_last_item_from_tagged_list(output_text, "answer")

        if json_match:
            try:
                extracted_data = json.loads(json_match)
                return extracted_data
            except json.JSONDecodeError:
                print("Falha ao parsear JSON da resposta do Claude.")
                print(f"Resposta do Claude: {output_text}")
                sys.exit(1)
        else:
            print("Nenhum JSON encontrado na resposta do Claude.")
            print(f"Resposta do Claude: {output_text}")
            sys.exit(1)

    except Exception as e:
        traceback.print_exc()
        print(f"Erro ao processar o PDF: {e}")
        sys.exit(1)


def process_pdf(pdf_path, output_dir):
    """
    Processa um único arquivo PDF, extraindo dados e gerando o CSV.
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        output_dir: Diretório onde o CSV será salvo
        
    Returns:
        bool: True se o processamento foi bem-sucedido, False caso contrário
    """
    try:
        print("Enviando PDF para LLM...")
        # Extrai os dados do PDF
        transaction_data = extract_transaction_data_from_pdf(pdf_path)
        
        # Exibe os dados extraídos
        display_transaction_data(transaction_data)
        
        # Obtém as taxas de câmbio
        exchange_rates = get_exchange_rates(transaction_data)
        
        # Gera o CSV para este PDF
        create_csv(transaction_data, exchange_rates, output_dir)

        return True
        
    except Exception as e:
        print(f"Erro ao processar {pdf_path}: {e}")
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Extrai dados de transação de PDF da Morgan Stanley')
    parser.add_argument('pdf_paths', nargs='+', help='Caminhos para os arquivos PDF da Morgan Stanley ou diretório contendo PDFs')
    parser.add_argument('-d', '--dir', action='store_true', help='Tratar o argumento como diretório contendo PDFs')
    parser.add_argument('-o', '--output', default='output', help='Diretório de saída para os arquivos CSV (padrão: output)')
    args = parser.parse_args()

    # Obtém a lista de arquivos PDF a serem processados
    pdf_files = get_pdf_files(args.pdf_paths, args.dir)
    
    # Cria o diretório de saída se não existir
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Processando {len(pdf_files)} arquivo(s) PDF...")
    
    # Processa cada arquivo PDF
    successful = 0
    failed = 0
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processando: {os.path.basename(pdf_path)}")
        
        if process_pdf(pdf_path, args.output):
            successful += 1
        else:
            failed += 1
            print("Continuando com o próximo arquivo...")

    print("\nProcessamento concluído!")
    if len(pdf_files) > 1:
        print(f"Total de arquivos: {len(pdf_files)}")
        print(f"Processados com sucesso: {successful}")
        print(f"Falhas: {failed}")
        print(f"Arquivos CSV gerados estão no diretório: {args.output}")


if __name__ == "__main__":
    main()
