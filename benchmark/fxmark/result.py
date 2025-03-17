import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

MAPPING = ['4k', '16k', '32k']
POLICY = ['IMMEDIATE', 'FULL_SINGLE', 'FULL_HALF', 'FULL_ALL', 'WATERMARK_NAIVE', 'WATERMARK_HIGHLOW', 'LOCAL', 'ORIGIN']
WORKLOADS = ['MWCL', 'MWCM', 'MWRL', 'MWRM', 'MWUL', 'MWUM', 'MRDL', 'MRDL_bg', 'MRDM', 'MRDM_bg', 'MRPH', 'MRPL', 'MRPM', 'MRPM_bg']
DATA_TYPE = ['ncpu', 'secs', 'works', 'works/sec', 'real.sec', 'user.sec', 'nice.sec', 
                 'sys.sec', 'idle.sec', 'iowait.sec', 'irq.sec', 'softirq.sec', 'steal.sec', 
                 'guest.sec', 'user.util', 'nice.util', 'sys.util', 'idle.util', 'iowait.util', 
                 'irq.util', 'softirq.util', 'steal.util', 'guest.util']
# Data types
# ncpu secs works works/sec real.sec user.sec nice.sec sys.sec idle.sec iowait.sec irq.sec softirq.sec steal.sec guest.sec user.util nice.util sys.util idle.util iowait.util irq.util softirq.util steal.util guest.util

def read_data(workload, policy):
    if policy == 'ORIGIN':
        data = pd.DataFrame(index=['Origin'], columns=DATA_TYPE)
        filename = f'{policy}/{workload}/{workload}_origin.log'
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'r') as f:
            raw_data = f.readlines()
            for line in raw_data:
                if line.startswith('#'):
                    continue
                
                datas = [data.strip() for data in line.split()]
                for i, d in enumerate(datas):
                    data.at['Origin', DATA_TYPE[i]] = float(d)
    else:
        data = pd.DataFrame(index=MAPPING, columns=DATA_TYPE)
        for mapping in MAPPING:
            filename = f'{policy}/{workload}/{workload}_{mapping}.log'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            
            with open(filepath, 'r') as f:
                raw_data = f.readlines()
                for line in raw_data:
                    if line.startswith('#'):
                        continue
                    
                    datas = [data.strip() for data in line.split()]
                    for i, d in enumerate(datas):
                        data.at[mapping, DATA_TYPE[i]] = float(d)
                    
    return data

def plot_data(data, workload='MWCL', target='works/sec'):
    unique_benchmark = POLICY
    origin_val = data['ORIGIN'].loc['Origin', target]
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(24, 14))
    
    for i, bench in enumerate(unique_benchmark):
        if bench == 'ORIGIN':
            val = data[bench].loc['Origin', target]
            plt.bar(i, val, width, color='gray', label="Origin" if i == len(unique_benchmark)-1 else "")
            
        else:
            for k, mapping in enumerate(MAPPING):
                offset = (k - (len(MAPPING) - 1) / 2) * width
                val = data[bench].loc[mapping, target]
                bars = plt.bar(
                    i + offset, 
                    val, 
                    width, 
                    color=color_dict.get(mapping, 'gray'),
                    label=mapping.capitalize() if i == 0 else ""
                )
                
                # 비율 계산 후 소수점 둘째 자리에서 반올림
                ratio = 0.0
                if origin_val != 0:
                    ratio = round((val / origin_val) * 100, 2)
                
                # 텍스트 표시 (회전 + 약간 위로)
                for bar in bars:
                    bar_height = bar.get_height()
                    bar_xcenter = bar.get_x() + bar.get_width()/2
                    plt.text(
                        bar_xcenter, 
                        bar_height - len(f"{ratio}%") * 0.02 * bar_height, 
                        f"{ratio}%", 
                        ha='center', va='bottom', 
                        fontsize=8,       # 조금 작은 폰트
                        rotation=270       # 세로로 표시
                    )
                    
    plt.axhline(origin_val, color='red', linestyle='--', linewidth=1, label="Origin Value")
    plt.title(f'{workload}', fontsize=14)
    plt.ylabel(f'{target}', fontsize=12)
    plt.xticks(np.arange(len(unique_benchmark)), unique_benchmark, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'output/{workload}.png'))
    
if __name__ == '__main__':
    workloads = ['MWCL', 'MWCM', 'MWRL', 'MWRM', 'MWUL', 'MWUM', 'MRDL', 'MRDL_bg', 'MRDM', 'MRDM_bg', 'MRPH', 'MRPL', 'MRPM', 'MRPM_bg']
    
    for workload in workloads:
        data = {}
        for policy in POLICY:
            data[policy] = read_data(workload, policy)
  
        plot_data(data, workload)