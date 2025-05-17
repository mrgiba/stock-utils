import requests
from datetime import datetime, timedelta
import json

def format_date_for_api(date_str):
    """
    Converte uma data no formato DD/MM/YYYY para o formato da API do Banco Central (MM-DD-YYYY)
    """
    if not date_str:
        return None
    
    try:
        # Converte de DD/MM/YYYY para objeto datetime
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        # Formata para MM-DD-YYYY
        return date_obj.strftime("%m-%d-%Y")
    except ValueError:
        print(f"Erro ao converter data: {date_str}")
        return None

def get_exchange_rate_from_bcb(date_str, operation_type="venda"):
    """
    Obtém a taxa de câmbio do Banco Central do Brasil para uma data específica
    
    Args:
        date_str: Data no formato DD/MM/YYYY
        operation_type: Tipo de operação ("venda" ou "compra")
            - Para venda de ações (recebimento de USD): usar taxa de compra do dólar
            - Para compra de ações (pagamento em USD): usar taxa de venda do dólar
        
    Returns:
        float: Taxa de câmbio (USD para BRL)
    """
    api_date = format_date_for_api(date_str)
    if not api_date:
        return None
    
    # A API do BCB requer datas no formato MM-DD-YYYY
    url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{api_date}'&$format=json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Levanta exceção para erros HTTP
        
        data = response.json()
        
        # Verifica se há valores retornados
        if data and 'value' in data and len(data['value']) > 0:
            # Para venda de ações (recebimento de USD): usar taxa de compra do dólar
            # Para compra de ações (pagamento em USD): usar taxa de venda do dólar
            if operation_type.lower() == "venda":
                rate = float(data['value'][0]['cotacaoCompra'])
                rate_type = "compra"
            else:  # compra
                rate = float(data['value'][0]['cotacaoVenda'])
                rate_type = "venda"
                
            return rate
        else:
            # Se não houver dados para a data específica, tenta o dia útil anterior
            print(f"Nenhuma cotação encontrada para {date_str}. Tentando dia anterior...")
            return get_previous_business_day_rate(date_str, operation_type)
    
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a API do Banco Central: {e}")
        return None

def get_previous_business_day_rate(date_str, operation_type="venda", max_attempts=5):
    """
    Tenta obter a taxa de câmbio do dia útil anterior
    
    Args:
        date_str: Data no formato DD/MM/YYYY
        operation_type: Tipo de operação ("venda" ou "compra")
        max_attempts: Número máximo de dias anteriores a tentar
        
    Returns:
        float: Taxa de câmbio (USD para BRL)
    """
    date_obj = datetime.strptime(date_str, "%d/%m/%Y")
    
    for _ in range(max_attempts):
        # Subtrai um dia
        date_obj = date_obj - timedelta(days=1)
        previous_date = date_obj.strftime("%d/%m/%Y")
        
        # Tenta obter a taxa para o dia anterior
        api_date = format_date_for_api(previous_date)
        url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{api_date}'&$format=json"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and 'value' in data and len(data['value']) > 0:
                print(f"Usando cotação do dia {previous_date}")
                
                if operation_type.lower() == "venda":
                    rate = float(data['value'][0]['cotacaoCompra'])
                else:  # compra
                    rate = float(data['value'][0]['cotacaoVenda'])
                    
                return rate
        
        except requests.exceptions.RequestException:
            continue
    
    print(f"Não foi possível encontrar cotação para {date_str} ou dias anteriores.")
    return None

def get_exchange_rates_auto(transaction_date, acquisition_date):
    """
    Obtém automaticamente as taxas de câmbio para as datas de transação e aquisição
    
    Args:
        transaction_date: Data da transação no formato DD/MM/YYYY
        acquisition_date: Data da aquisição no formato DD/MM/YYYY
        
    Returns:
        tuple: (taxa_compra_atual, taxa_compra_aquisicao)
    """
    print("\nBuscando taxas de câmbio do Banco Central...")
    
    # Para venda de ações (data da transação): usar taxa de compra do dólar
    print(f"Buscando taxa para data da venda ({transaction_date})...")
    transaction_rate = get_exchange_rate_from_bcb(transaction_date, operation_type="venda")
    if transaction_rate:
        print(f"Taxa de câmbio na data da venda ({transaction_date}): {transaction_rate:.4f}")
    else:
        print("Não foi possível obter a taxa de câmbio para a data da venda.")
        transaction_rate = float(input("Por favor, forneça a taxa de COMPRA do dólar (USD para BRL): ").replace(',', '.'))
    
    # Para compra de ações (data da aquisição): usar taxa de venda do dólar
    print(f"Buscando taxa para data da aquisição ({acquisition_date})...")
    acquisition_rate = get_exchange_rate_from_bcb(acquisition_date, operation_type="compra")
    if acquisition_rate:
        print(f"Taxa de câmbio na data da aquisição ({acquisition_date}): {acquisition_rate:.4f}")
    else:
        print("Não foi possível obter a taxa de câmbio na data de aquisição.")
        acquisition_rate = float(input("Por favor, forneça a taxa de VENDA do dólar (USD para BRL): ").replace(',', '.'))
    
    return transaction_rate, acquisition_rate

def get_exchange_rates_interactive(transaction_date, acquisition_date):
    """
    Obtém as taxas de câmbio automaticamente ou manualmente, conforme escolha do usuário
    Por padrão, busca automaticamente do Banco Central
    
    Args:
        transaction_date: Data da transação no formato DD/MM/YYYY (pode ser None)
        acquisition_date: Data da aquisição no formato DD/MM/YYYY (pode ser None)
        
    Returns:
        tuple: (taxa_compra_atual, taxa_compra_aquisicao)
    """
    transaction_rate = None
    acquisition_rate = None
    
    try:
        if transaction_date:
            print(f"Buscando taxa para data da venda ({transaction_date})...")
            transaction_rate = get_exchange_rate_from_bcb(transaction_date, operation_type="venda")
            if transaction_rate:
                print(f"Taxa de câmbio na data da venda ({transaction_date}): {transaction_rate:.4f}")
            else:
                print("Não foi possível obter a taxa de câmbio para a data da venda.")
                transaction_rate = float(input("Por favor, forneça a taxa de COMPRA do dólar (USD para BRL): ").replace(',', '.'))
        
        if acquisition_date:
            print(f"Buscando taxa para data da aquisição ({acquisition_date})...")
            acquisition_rate = get_exchange_rate_from_bcb(acquisition_date, operation_type="compra")
            if acquisition_rate:
                print(f"Taxa de câmbio na data da aquisição ({acquisition_date}): {acquisition_rate:.4f}")
            else:
                print("Não foi possível obter a taxa de câmbio na data de aquisição.")
                acquisition_rate = float(input("Por favor, forneça a taxa de VENDA do dólar (USD para BRL): ").replace(',', '.'))
    
    except KeyboardInterrupt:
        print("\n\nBusca automática cancelada.")
        if transaction_date and not transaction_rate:
            transaction_rate = float(input("Taxa de COMPRA do dólar na data da venda (USD para BRL): ").replace(',', '.'))
        if acquisition_date and not acquisition_rate:
            acquisition_rate = float(input("Taxa de VENDA do dólar na data da aquisição (USD para BRL): ").replace(',', '.'))
    
    # Se alguma das datas não foi fornecida, retorna None para essa taxa
    return (transaction_rate, acquisition_rate)
