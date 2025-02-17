import os
import pandas as pd
import matplotlib.pyplot as plt
import math

def read_data():
    bs = ['4k', '16k', '32k']
    data_tye = ['ops/sec', 'bw', 'avt_lat', 'P50', 'P75', 'P99', 'P99.9', 'P99.99']
    result = pd.DataFrame(columns=bs, index=data_tye)
    
    for b in bs:
        filepath = os.path.join(os.path.dirname(__file__), 'output/' + b + '.txt')
    
        with open(filepath, 'r') as f:
            data = f.readlines()
            data = [d.strip() for d in data]
            for line in data:
                word = [w.strip() for w in line.split()]
                
                if word[0] == 'fillrandom':
                    result.at['ops/sec', b] = float(word[4])
                    result.at['bw', b] = float(word[10])
                elif word[0] == 'Count:':
                    result.at['avt_lat', b] = float(word[3])
                elif word[0] == 'Percentiles:':
                    result.at['P50', b] = float(word[2])
                    result.at['P75', b] = float(word[4])
                    result.at['P99', b] = float(word[6])
                    result.at['P99.9', b] = float(word[8])
                    result.at['P99.99', b] = float(word[10])
            
    return result

def plot_data(data):
    bs = ['4k', '16k', '32k']
    data_type = ['ops/sec', 'bw', 'avt_lat', 'P50', 'P75', 'P99', 'P99.9', 'P99.99']
    labels = ['Ops/sec', 'Bandwidth (MB/s)', 'Average Latency (ms)', 'P50 Latency (ms)', 'P75 Latency (ms)', 'P99 Latency (ms)', 'P99.9 Latency (ms)', 'P99.99 Latency (ms)']
    
    for type, label in zip(data_type, labels):
        plt.clf()
        
        plt.figure(figsize=(9, 6))
        
        values = []
        values = [data.loc[type, '4k'], data.loc[type, '16k'], data.loc[type, '32k']]
        bar = plt.bar(bs, values, alpha=0.7, color=['white', 'white', 'gray'], edgecolor='black')
        bar[0].set_label('4K')
        bar[1].set_label('16K')
        bar[2].set_label('32K')
        bar[1].set_hatch('/')
        
        plt.xlabel('Block Size (Byte)')
        plt.ylabel(label)
        plt.title(label)
        if type == 'ops/sec':
            plt.savefig(os.path.join(os.path.dirname(__file__), f'output/ops.sec.png'))
        else:
            plt.savefig(os.path.join(os.path.dirname(__file__), f'output/{type}.png'))
        
        
if __name__ == '__main__':
    data = read_data()
    data.to_csv(os.path.join(os.path.dirname(__file__), 'output/data.csv'))
    plot_data(data)