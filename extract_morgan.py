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
    """Formata moeda em USD"""
    return f"${amount:.2f}"


def format_currency_brl(amount):
    """Formata moeda em BRL"""
    return f"R$ {amount:.2f}"


def create_csv(transaction_data, exchange_rates):
    """Cria arquivo CSV com dados da transação"""
    transaction_rate, acquisition_rate = exchange_rates

    # Calcula valores derivados
    costs = transaction_data["commission"] + transaction_data["supplemental_fee"]
    total_proceeds = transaction_data["total_value"]
    net_proceeds = total_proceeds - costs
    net_proceeds_brl = net_proceeds * transaction_rate  # Taxa de compra para venda de ações

    acquisition_cost_total = transaction_data["quantity"] * transaction_data["cost_basis_per_share"]
    acquisition_cost_brl = acquisition_cost_total * acquisition_rate  # Taxa de venda para compra de ações

    # Formata datas
    transaction_date = convert_date_format(transaction_data["transaction_date"])
    acquisition_date = convert_date_format(transaction_data["acquisition_date"])

    # Cria dados CSV
    csv_data = [
        {
            "Data": transaction_date,
            "Ação": transaction_data["ticker"],
            "Operação": "venda",
            "Quantidade": transaction_data["quantity"],
            "Valor ação (dolar)": format_currency_usd(transaction_data["share_value"]),
            "Total (dolar)": format_currency_usd(total_proceeds),
            "Custos": format_currency_usd(costs),
            "Operação - custos": format_currency_usd(net_proceeds),
            "Operação - custos (R$)": format_currency_brl(net_proceeds_brl),
            "Câmbio (compra)": transaction_rate,
            "Data aquisição": acquisition_date,
            "Custo aquisição": format_currency_usd(transaction_data["cost_basis_per_share"]),
            "Cambio aquisição (venda)": acquisition_rate,
            "Custo aquisição total": format_currency_usd(acquisition_cost_total),
            "Custo aquisição total (R$)": format_currency_brl(acquisition_cost_brl),
            "Lucro (dolar)": "$0.00",
            "Lucro (reais)": "R$ 0.00"
        }
    ]

    output_file = f"{transaction_data['ticker']}_transaction_{transaction_date.replace('/', '-')}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = csv_data[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"\nArquivo CSV criado: {output_file}")
    return output_file


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
4. Quantidade de ações vendidas
5. Valor por ação em USD (Market Price per Unit)
6. Valor total da transação em USD (Proceeds)
7. Custo de comissão em USD
8. Taxa suplementar de transação em USD
9. Data de aquisição das ações
10. Custo base original por ação em USD
        
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
    "acquisition_date": "DD-MM-YYYY",
    "cost_basis_per_share": ###.##
}
        
Conclua com uma reflexão final sobre a solução geral, discutindo eficácia, desafios e soluções. Atribua uma pontuação final de recompensa.        
        """

        # Chama a função invoke_llm do seu módulo
        response = invoke_llm(
            prompt=prompt,
            document_content=pdf_content,
            document_format="pdf",
            temperature=0,
            max_new_tokens=4096,
            verbose=True
        )

        # Extrai o JSON da resposta
        output_text = response.output
        json_match = extract_last_item_from_tagged_list(output_text, "answer")

        # json_match = re.search(r'({.*})', output_text, re.DOTALL)

        if json_match:
            try:
                # extracted_data = json.loads(json_match.group(1))
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


def main():
    parser = argparse.ArgumentParser(description='Extrai dados de transação de PDF da Morgan Stanley')
    parser.add_argument('pdf_path', help='Caminho para o arquivo PDF da Morgan Stanley')
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Erro: O arquivo PDF '{args.pdf_path}' não existe.")
        sys.exit(1)

    print("Enviando PDF para Claude via Bedrock Converse...")
    transaction_data = extract_transaction_data_from_pdf(args.pdf_path)

    print("\nDados de Transação Extraídos:")
    print(f"Data: {convert_date_format(transaction_data['transaction_date'])}")
    print(f"Ação: {transaction_data['ticker']}")
    print(f"Quantidade: {transaction_data['quantity']}")
    print(f"Preço por Ação: ${transaction_data['share_value']}")
    print(f"Valor Total: ${transaction_data['total_value']}")
    print(f"Comissão: ${transaction_data['commission']}")
    print(f"Taxa Suplementar: ${transaction_data['supplemental_fee']}")
    print(f"Data de Aquisição: {convert_date_format(transaction_data['acquisition_date'])}")
    print(f"Custo de Aquisição: ${transaction_data['cost_basis_per_share']}")

    # Formata as datas para o formato DD/MM/YYYY para uso na API do Banco Central
    transaction_date = convert_date_format(transaction_data['transaction_date'])
    acquisition_date = convert_date_format(transaction_data['acquisition_date'])

    # Obtém as taxas de câmbio automaticamente ou manualmente
    exchange_rates = get_exchange_rates_interactive(transaction_date, acquisition_date)

    output_file = create_csv(transaction_data, exchange_rates)

    print("\nConcluído! Os dados da transação foram extraídos e salvos.")


if __name__ == "__main__":
    main()
