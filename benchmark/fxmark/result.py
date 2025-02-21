import os
import pandas as pd
import matplotlib.pyplot as plt

# Data types
# ncpu secs works works/sec real.sec user.sec nice.sec sys.sec idle.sec iowait.sec irq.sec softirq.sec steal.sec guest.sec user.util nice.util sys.util idle.util iowait.util irq.util softirq.util steal.util guest.util

def read_data(workload):
    block_size = ['4k', '16k', '32k', 'origin']
    data_type = ['ncpu', 'secs', 'works', 'works/sec', 'real.sec', 'user.sec', 'nice.sec', 
                 'sys.sec', 'idle.sec', 'iowait.sec', 'irq.sec', 'softirq.sec', 'steal.sec', 
                 'guest.sec', 'user.util', 'nice.util', 'sys.util', 'idle.util', 'iowait.util', 
                 'irq.util', 'softirq.util', 'steal.util', 'guest.util']
    
    data = pd.DataFrame(index=block_size, columns=data_type)
    
    for bs in block_size:
        filename = f'{workload}/{workload}_{bs}.log'
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'r') as f:
            raw_data = f.readlines()
            for line in raw_data:
                if line.startswith('#'):
                    continue
                
                datas = [data.strip() for data in line.split()]
                for i, d in enumerate(datas):
                    data.at[bs, data_type[i]] = d
                    
    return data

def plot_data(data, workload):
    block_size = ['4k', '16k', '32k', 'origin']
    # data_type = ['works/sec', 'user.util', 'sys.util', 'iowait.util', 'real.sec']
    data_type = ['works/sec']
    
    for dt in data_type:
        plt.clf()
        plt.figure(figsize=(10, 6))
        plt.title(f'{workload} - {dt}')
        plt.xlabel('Block Size (Byte)')
        plt.ylabel('Throughput (Kops/sec)')
        
        values = []
        ratio = []
        for bs in block_size:
            values.append(float(data.at[bs, dt]) / 1000)
            ratio.append(format(float(data.at[bs, dt]) / float(data.at['origin', dt]) * 100, '.2f') + '%')
        
        bar = plt.bar(block_size, values, alpha=0.7, color=['white', 'white', 'gray', 'gray'], edgecolor='black')
        bar[0].set_label('4K')
        bar[1].set_label('16K')
        bar[2].set_label('32K')
        bar[3].set_label('Origin')
        bar[1].set_hatch('/')
        bar[3].set_hatch('/')
        
        idx = 0
        for rect in bar:
            height = rect.get_height()
            plt.text(rect.get_x()+rect.get_width()/2.0, height, ratio[idx], ha = 'center',va='bottom',size=10)
            idx += 1
                
        plt.legend()
        if dt == 'works/sec':
            plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{workload}_works.sec.png'))
        else:
            plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{workload}_{dt}.png'))
    
if __name__ == '__main__':
    workloads = ['MWCL', 'MWCM', 'MWRL', 'MWRM', 'MWUL', 'MWUM', 'MRDL', 'MRDL_bg', 'MRDM', 'MRDM_bg', 'MRPH', 'MRPL', 'MRPM', 'MRPM_bg']
    
    for workload in workloads:
        data = read_data(workload)
        plot_data(data, workload)