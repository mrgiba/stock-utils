#!/usr/bin/env python3
"""
Script para converter dados de arquivos CSV para o formato XLSX
compatível com importação no Bastter System.

Formato do Bastter System:
1ª coluna: ticker
2ª coluna: data
3ª coluna: quantidade (positiva para compra, negativa para venda)
4ª coluna: total + custos (para compra) / total - custos (para venda)
5ª coluna: 0,00 (para compra) / total sem descontar custos (para venda)
"""

import pandas as pd
import re
import os
import csv
import argparse
from datetime import datetime

def convert_to_float(value):
    """Converte valores monetários em formato brasileiro para float."""
    if isinstance(value, str):
        # Remove aspas, símbolo de moeda e espaços
        value = value.replace('"', '').replace('R$', '').strip()
        
        # Trata o formato brasileiro (ponto como separador de milhar e vírgula como decimal)
        if '.' in value and ',' in value:
            value = value.replace('.', '')
        value = value.replace(',', '.')
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def process_csv_to_bastter_format(input_file, output_file, filter_year=None):
    """
    Processa o arquivo CSV e converte para o formato do Bastter System.
    
    Args:
        input_file: Caminho para o arquivo CSV de entrada
        output_file: Caminho para salvar o arquivo XLSX de saída
        filter_year: Ano para filtrar as transações (opcional)
    """
    # Lista para armazenar todos os dados processados
    all_data = []
    
    # Ler o arquivo CSV diretamente
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Dividir o conteúdo por ticker
    ticker_sections = re.split(r'\n,+\n', content)
    
    for section in ticker_sections:
        if not section.strip():
            continue
        
        lines = section.strip().split('\n')
        
        # Extrair o ticker da primeira linha
        ticker = lines[0].split(',')[0].strip()
        if not ticker or ticker == "Data":
            continue
        
        # Encontrar o cabeçalho
        header_index = -1
        for i, line in enumerate(lines):
            if "Data,Corretora,Tipo,Qtd,Preço,Total,Preço + Taxas,Total + Taxas" in line:
                header_index = i
                break
        
        if header_index == -1:
            continue
        
        # Processar as transações
        for i in range(header_index + 1, len(lines)):
            line = lines[i]
            if not line.strip():
                continue
            
            # Usar o módulo csv para lidar corretamente com campos entre aspas
            fields = next(csv.reader([line]))
            if len(fields) < 8:
                continue
            
            # Extrair dados
            date_str = fields[0].strip()
            if not date_str:
                continue
            
            # Verificar se a data está no formato esperado e filtrar por ano se necessário
            try:
                transaction_date = datetime.strptime(date_str, "%d/%m/%Y")
                if filter_year and transaction_date.year != filter_year:
                    continue
            except ValueError:
                # Se a data não estiver no formato esperado, tenta continuar mesmo assim
                pass
                
            transaction_type = fields[2].strip()  # C para compra, V para venda
            quantity = fields[3].strip()
            total = fields[5].strip()  # Total sem taxas
            total_with_taxes = fields[7].strip()  # Total com taxas
            
            # Converter valores
            try:
                quantity = int(quantity)
                total_value = convert_to_float(total)
                total_with_taxes_value = convert_to_float(total_with_taxes)
                
                # Ajustar quantidade (negativa para venda)
                if transaction_type == 'V':
                    quantity = -quantity
                
                # Calcular valores conforme regras do Bastter System
                if transaction_type == 'C':  # Compra
                    col4_value = total_with_taxes_value  # Total + custos
                    col5_value = 0.0  # Para compra é sempre 0,00
                else:  # Venda
                    col4_value = total_with_taxes_value  # Total - custos (já está calculado no total_with_taxes)
                    col5_value = total_value  # Total sem descontar custos
                
                # Adicionar à lista de dados
                all_data.append({
                    'Ticker': ticker,
                    'Data': date_str,
                    'Quantidade': quantity,
                    'Valor': col4_value,
                    'Valor2': col5_value
                })
                
            except (ValueError, TypeError) as e:
                print(f"Erro ao processar linha: {line}. Erro: {e}")
    
    # Criar DataFrame
    df = pd.DataFrame(all_data)
    
    # Ordenar por ticker e data
    df = df.sort_values(['Ticker', 'Data'])
    
    # Formatar valores monetários sem símbolo de moeda
    df['Valor'] = df['Valor'].round(2)
    df['Valor2'] = df['Valor2'].round(2)
    
    # Salvar como XLSX sem incluir o cabeçalho
    df.to_excel(output_file, index=False, sheet_name='Importação Bastter', header=False)
    
    print(f"Arquivo convertido com sucesso: {output_file}")
    print(f"Total de {len(df)} transações processadas.")

def main():
    parser = argparse.ArgumentParser(description='Converte dados de transações para o formato do Bastter System')
    parser.add_argument('-i', '--input', default='transacoes.csv', help='Arquivo CSV de entrada')
    parser.add_argument('-o', '--output', default='bastter_import.xlsx', help='Arquivo XLSX de saída (padrão: bastter_import.xlsx)')
    parser.add_argument('-y', '--year', type=int, help='Filtrar transações por ano específico')
    
    args = parser.parse_args()
    
    # Verificar se o arquivo de entrada existe
    if not os.path.exists(args.input):
        print(f"Erro: Arquivo {args.input} não encontrado.")
        exit(1)
    
    process_csv_to_bastter_format(args.input, args.output, args.year)

if __name__ == "__main__":
    main()
