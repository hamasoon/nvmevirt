import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PATTERN = (
    r'IO Summary:\s+'         # "IO Summary:" 다음 공백을 매칭한다이다.
    r'(\d+)\s+ops\s+'         # 첫 번째 그룹: ops 값 (정수)을 캡처한다이다.
    r'(\d+(?:\.\d+)?)\s+ops/s\s+'  # 두 번째 그룹: ops/s 값 (소수점 포함)을 캡처한다이다.
    r'(\d+\/\d+)\s+rd/wr\s+'   # 세 번째 그룹: rd/wr 값 (숫자/숫자 형식)을 캡처한다이다.
    r'(\d+(?:\.\d+)?)mb/s\s+'  # 네 번째 그룹: mb/s 값 (소수점 포함)을 캡처한다이다.
    r'(\d+(?:\.\d+)?)ms/op'    # 다섯 번째 그룹: ms/op 값 (소수점 포함)을 캡처한다이다.
)
POLICY = ["IMMEDIATE", "FULL_SINGLE", "FULL_HALF", "FULL_ALL", "WATERMARK_NAIVE", "WATERMARK_HIGHLOW"]
MAPPING = ["4k", "16k", "32k"]

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
        

def read_data(workloads):
    ret = pd.DataFrame(columns=POLICY, index=MAPPING)
    
    for policy in POLICY:
        for mapping in MAPPING:
            filename = f"output/{policy}/{mapping}_{workloads}.txt"
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    match = re.search(PATTERN, line)
                    if match:
                        ops    = float(match.group(1))
                        ops_s  = float(match.group(2))
                        rd_wr  = match.group(3)
                        mb_s   = float(match.group(4))
                        ms_op  = float(match.group(5))
                        
                        ret.loc[mapping, policy] = ops_s
                        break
            
    return ret

def read_origin_data(workload):
    filename = f"output/origin_{workload}.txt"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            match = re.search(PATTERN, line)
            if match:
                ops    = float(match.group(1))
                ops_s  = float(match.group(2))
                rd_wr  = match.group(3)
                mb_s   = float(match.group(4))
                ms_op  = float(match.group(5))
                
                return ops_s

def plot_summary(workload):
    data = read_data(workload)
    
    unique_benchmark = POLICY
    origin_val = read_origin_data(workload)
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    
    for i, bench in enumerate(unique_benchmark):
        if bench == 'ORIGIN':
            val = origin_val
            plt.bar(i, val, width, color='gray', label="Origin" if i == len(unique_benchmark)-1 else "")
            
        else:
            for k, mapping in enumerate(MAPPING):
                offset = (k - (len(MAPPING) - 1) / 2) * width
                val = data.loc[mapping, bench]
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
    plt.ylabel(f'ops/sec', fontsize=12)
    plt.xticks(np.arange(len(unique_benchmark)), unique_benchmark, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{workload}.png'))
        
def plot_ops(data1, data2, data3):
    data_type = ['ops/sec', 'bw', 'lat']
    label = ['Ops/sec', 'Bandwidth (MB/s)', 'Latency (ms)']
    
    for t, l in zip(data_type, label):
        values = [data1.loc[t], data2.loc[t], data3.loc[t]]
            
if __name__ == '__main__':
    workloads = ['varmail', 'webserver', 'webproxy', 'fileserver']

    for w in workloads:
        plot_summary(w)