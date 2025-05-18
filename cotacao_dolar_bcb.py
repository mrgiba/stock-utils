#!/usr/bin/env python3
"""
Script para baixar cotações do dólar do Banco Central do Brasil (BCB)
através da API Olinda.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import argparse

def obter_cotacao_data(data):
    """
    Obtém a cotação do dólar para uma data específica.
    
    Args:
        data (str): Data no formato DD/MM/AAAA
    
    Returns:
        dict: Dicionário com as informações de cotação ou None se não houver cotação
    """
    try:
        # Converter a data para o formato esperado pela API (MM-DD-AAAA)
        data_obj = datetime.strptime(data, "%d/%m/%Y")
        data_api = data_obj.strftime("%m-%d-%Y")
        
        # URL da API do BCB
        url = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{data_api}'&$format=json"
        
        # Fazer a requisição
        response = requests.get(url)
        response.raise_for_status()  # Lança exceção para erros HTTP
        
        # Converter resposta para JSON
        dados = response.json()
        
        # Verificar se há valores retornados
        if not dados["value"]:
            print(f"Não há cotação disponível para {data} (possivelmente um feriado ou fim de semana)")
            return None
        
        # Extrair os dados de cotação
        cotacao = dados["value"][0]
        
        # Adicionar a data formatada para exibição
        cotacao["data"] = data
        
        return cotacao
    
    except requests.exceptions.RequestException as e:
        print(f"Erro ao fazer requisição: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"Erro ao processar dados: {e}")
        return None

def obter_cotacoes_periodo(data_inicio, data_fim):
    """
    Obtém cotações para um período de datas.
    
    Args:
        data_inicio (str): Data inicial no formato DD/MM/AAAA
        data_fim (str): Data final no formato DD/MM/AAAA
    
    Returns:
        list: Lista de cotações para o período
    """
    data_inicio_obj = datetime.strptime(data_inicio, "%d/%m/%Y")
    data_fim_obj = datetime.strptime(data_fim, "%d/%m/%Y")
    
    if data_fim_obj < data_inicio_obj:
        print("Erro: Data final deve ser maior ou igual à data inicial")
        return []
    
    cotacoes = []
    data_atual = data_inicio_obj
    
    while data_atual <= data_fim_obj:
        data_str = data_atual.strftime("%d/%m/%Y")
        print(f"Consultando cotação para {data_str}...")
        
        cotacao = obter_cotacao_data(data_str)
        if cotacao:
            cotacoes.append(cotacao)
        
        # Avançar para o próximo dia
        data_atual += timedelta(days=1)
    
    return cotacoes

def salvar_csv(cotacoes, arquivo_saida):
    """
    Salva as cotações em um arquivo CSV.
    
    Args:
        cotacoes (list): Lista de cotações
        arquivo_saida (str): Nome do arquivo de saída
    """
    if not cotacoes:
        print("Não há cotações para salvar")
        return
    
    # Criar DataFrame
    df = pd.DataFrame(cotacoes)
    
    # Reordenar e renomear colunas
    colunas = {
        'data': 'Data',
        'cotacaoCompra': 'Compra',
        'cotacaoVenda': 'Venda',
        'dataHoraCotacao': 'DataHoraCotacao'
    }
    
    df = df[colunas.keys()].rename(columns=colunas)
    
    # Salvar como CSV
    df.to_csv(arquivo_saida, index=False)
    print(f"Cotações salvas em {arquivo_saida}")

def exibir_cotacoes(cotacoes):
    """
    Exibe as cotações formatadas no stdout.
    
    Args:
        cotacoes (list): Lista de cotações
    """
    if not cotacoes:
        print("Não há cotações para exibir")
        return
    
    print("\n{:<12} {:<10} {:<10}".format("Data", "Compra", "Venda"))
    print("-" * 35)
    
    for cotacao in cotacoes:
        print("{:<12} R$ {:<8.4f} R$ {:<8.4f}".format(
            cotacao['data'],
            cotacao['cotacaoCompra'],
            cotacao['cotacaoVenda']
        ))

def main():
    parser = argparse.ArgumentParser(description='Consulta cotações do dólar no Banco Central do Brasil')
    
    # Grupo mutuamente exclusivo para data única ou período
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument('-d', '--data', help='Data específica no formato DD/MM/AAAA')
    grupo.add_argument('-p', '--periodo', nargs=2, metavar=('INICIO', 'FIM'), 
                      help='Período de datas no formato DD/MM/AAAA DD/MM/AAAA')
    
    parser.add_argument('-o', '--output', help='Arquivo de saída CSV (opcional)')
    parser.add_argument('--quiet', action='store_true', help='Não exibir resultados na tela')
    
    args = parser.parse_args()
    
    cotacoes = []
    
    if args.data:
        cotacao = obter_cotacao_data(args.data)
        if cotacao:
            cotacoes = [cotacao]
            if not args.quiet:
                print(f"\nCotação para {args.data}:")
                print(f"Compra: R$ {cotacao['cotacaoCompra']:.4f}")
                print(f"Venda: R$ {cotacao['cotacaoVenda']:.4f}")
    
    elif args.periodo:
        data_inicio, data_fim = args.periodo
        cotacoes = obter_cotacoes_periodo(data_inicio, data_fim)
        
        if cotacoes and not args.quiet:
            print(f"\nForam encontradas {len(cotacoes)} cotações no período")
            exibir_cotacoes(cotacoes)
    
    if cotacoes and args.output:
        salvar_csv(cotacoes, args.output)

if __name__ == "__main__":
    main()
