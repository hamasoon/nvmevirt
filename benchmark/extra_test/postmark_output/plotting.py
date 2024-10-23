import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

if __name__ == '__main__':
    columns = ['4K', '16K', '32K']
    data_4k_read = [360.60, 486.85, 541.40]
    data_4k_write = [357.12, 480.75, 533.69]
    data_4k_total = [x + y for x, y in zip(data_4k_read, data_4k_write)]
    data_16k_read = [364.24, 500.28, 525.13]
    data_16k_write = [360.74, 494.24, 517.65]
    data_16k_total = [x + y for x, y in zip(data_16k_read, data_16k_write)]
    data_32k_read = [351.21, 460.22, 520.95]
    data_32k_write = [347.83, 454.46, 513.53]
    data_32k_total = [x + y for x, y in zip(data_32k_read, data_32k_write)]
    
    data_4k = pd.DataFrame([data_4k_read, data_4k_write, data_4k_total], columns=columns, index=['Read', 'Write', 'Total'])
    data_16k = pd.DataFrame([data_16k_read, data_16k_write, data_16k_total], columns=columns, index=['Read', 'Write', 'Total'])
    data_32k = pd.DataFrame([data_32k_read, data_32k_write, data_32k_total], columns=columns, index=['Read', 'Write', 'Total'])
    
    x = np.arange(len(columns))
    w = 0.2
    plt.figure(figsize=(10, 6))
    plt.bar(x - w, data_4k.loc['Total'], width=w, label='4K', align='center', color='white', edgecolor='black')
    plt.bar(x, data_16k.loc['Total'], width=w, label='16K', align='center', color='white', edgecolor='black', hatch='/')
    plt.bar(x + w, data_32k.loc['Total'], width=w, label='32K', align='center', color='gray', edgecolor='black')
    
    plt.xlabel('I/O Block Size (KB)')
    plt.ylabel('IOPS (ops/sec)')
    plt.legend()
    plt.xticks(x, columns)
    plt.title('Postmark Benchmark Results')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'postmark.png'))