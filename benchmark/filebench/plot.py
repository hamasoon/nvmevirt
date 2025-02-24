import os
import pandas as pd
import matplotlib.pyplot as plt

def get_operations(workload):
    if workload == 'fileserver':
        return ['statfile', 'deletefile', 'closefile', 'readfile', 
                'openfile', 'appendfilerand', 'wrtfile', 'createfile']
    elif workload == 'varmail':
        return ['fsyncfile', 'deletefile', 'closefile', 'readfile', 
                'openfile', 'appendfilerand', 'createfile']
    elif workload == 'webserver':
        return ['readfile', 'openfile', 'closefile', 'appendlog']
    elif workload == 'webproxy':
        return ['closefile', 'readfile', 'openfile', 'appendfilerand']
        

def read_data(bs, workloads):
    filepath = os.path.join(os.path.dirname(__file__), 'output/' + bs + '_' + workloads + '.txt')
    data_type = ['ops/sec', 'bw', 'lat']
    ops = get_operations(workloads) + ['total']
    result = pd.DataFrame(columns=ops, index=data_type)
    
    with open(filepath, 'r') as f:
        data = f.readlines()
        data = [d.strip() for d in data]
        for line in data:
            word = [w.strip() for w in line.split()]
            if word[1] == 'IO':
                result.at['ops/sec', 'total'] = float(word[5])
                result.at['bw', 'total'] = float(word[9][:-4])
                result.at['lat', 'total'] = float(word[10][:-5])
            
            for op in ops:
                if op in word[0]:
                    result.at['ops/sec', op] = float(word[2][:-5])
                    result.at['bw', op] = float(word[3][:-4])
                    result.at['lat', op] = float(word[4][:-5])
            
    return result

def plot_summary(data1, data2, data3, data4, workload):
    data_type = ['ops/sec', 'bw', 'lat']
    label = ['Ops/sec', 'Bandwidth (MB/s)', 'Latency (ms)']
    
    for t, l in zip(data_type, label):
        values = [data1.loc[t, 'total'], data2.loc[t, 'total'], data3.loc[t, 'total'], data4.loc[t, 'total']]
        ratio = [format(values[i] / values[3] * 100, '.2f') + '%' for i in range(4)]
        plt.clf()
        plt.figure(figsize=(9, 6))
        bar = plt.bar(['4K', '16K', '32K', 'Origin'], values, alpha=0.7, color=['white', 'white', 'gray', 'gray'], edgecolor='black')
        bar[0].set_label('4K')
        bar[1].set_label('16K')
        bar[2].set_label('32K')
        bar[3].set_label('Origin')
        bar[1].set_hatch('/')
        bar[3].set_hatch('/')
        
        idx = 0
        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x() + rect.get_width()/2.0, height, f'{ratio[idx]}', ha='center', va='bottom')
            idx += 1
        
        plt.xlabel('Block Size (Byte)')
        plt.ylabel(l)
        plt.title(workload + ' - ' + l)
        
        if t == 'ops/sec':
            plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{workload}_ops.sec.png'))
        else:
            plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{workload}_{t}.png'))
        
def plot_ops(data1, data2, data3):
    data_type = ['ops/sec', 'bw', 'lat']
    label = ['Ops/sec', 'Bandwidth (MB/s)', 'Latency (ms)']
    
    for t, l in zip(data_type, label):
        values = [data1.loc[t], data2.loc[t], data3.loc[t]]
            
if __name__ == '__main__':
    workloads = ['varmail', 'webserver', 'webproxy', 'fileserver']

    for w in workloads:
        data_4k = read_data('4k', w)
        data_16k = read_data('16k', w)
        data_32k = read_data('32k', w)
        data_origin = read_data('origin', w)
        plot_summary(data_4k, data_16k, data_32k, data_origin, w)