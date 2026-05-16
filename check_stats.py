import pandas as pd
df = pd.read_csv('auditoria_movimentacoes.csv', sep=';')
print(f'Total: {len(df)}')

saidas = df[df['Tipo_Movimento'] == 'Saída']
print(f'Saidas: {len(saidas)}')
print(f'Soma saidas: R$ {saidas["Valor_Saida"].sum():.2f}')

print(f'\nFev/2025 (2025-02):')
fev25 = df[df['Mes_Ano'] == '2025-02']
saidas25 = fev25[fev25['Tipo_Movimento'] == 'Saída']
print(f'  Saidas: {len(saidas25)}')
print(f'  Soma: R$ {saidas25["Valor_Saida"].sum():.2f}')
print(f'  Top saidas:')
print(saidas25[['Data', 'Descricao', 'Valor_Saida']].head(10).to_string())

print(f'\nFev/2026 (2026-02):')
fev26 = df[df['Mes_Ano'] == '2026-02']
saidas26 = fev26[fev26['Tipo_Movimento'] == 'Saída']
print(f'  Saidas: {len(saidas26)}')
print(f'  Soma: R$ {saidas26["Valor_Saida"].sum():.2f}')
print(f'  Top saidas:')
print(saidas26[['Data', 'Descricao', 'Valor_Saida']].head(10).to_string())

print(f'\nAHAVA em Fev/2025:')
ahava = fev25[fev25['Descricao'].str.contains('AHAVA', na=False, case=False)]
print(f'  Count: {len(ahava)}')
print(f'  Soma: R$ {ahava["Valor_Saida"].sum():.2f}')
