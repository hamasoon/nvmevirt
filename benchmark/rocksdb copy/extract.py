import re
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# BENCHMARK 리스트와 MAPPING 리스트 정의 (Origin은 별도)
POLICY = [
    "IMMEDIATE", "FULL_SINGLE", "FULL_HALF", "FULL_ALL", "WATERMARK_NAIVE", "WATERMARK_HIGHLOW"
]
MAPPING = ["4k", "16k", "32k"]

# readwhilewriting :     740.842 micros/op 43168 ops/sec 600.857 seconds 25937968 operations;   31.5 MB/s (513205 of 811999 found)
PATTERN = r'(\d+(?:\.\d+)?)\s+micros/op\s+(\d+(?:\.\d+)?)\s+ops/sec\s+(\d+(?:\.\d+)?)\s+seconds\s+(\d+(?:\.\d+)?)\s+operations;\s+(\d+(?:\.\d+)?)\s+MB/s\s+\((\d+(?:\.\d+)?)\s+of\s+(\d+(?:\.\d+)?)\s+found\)'

def read_data():
    data = pd.DataFrame(columns=POLICY, index=MAPPING)
    
    for policy in POLICY:
        for mapping in MAPPING:
            filename = f"{policy}/{mapping}.txt"
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, "r") as f:
                lines = f.readlines()
                for line in lines:
                    match = re.search(PATTERN, line)
                    if match:
                        data.at[mapping, policy] = float(match.group(2))
                        break
                    
    return data

def read_origin_data():
    data = 10000
    
    filename = f"origin.log"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "r") as f:
        lines = f.readlines()
        for line in lines:
            match = re.search(PATTERN, line)
            if match:
                data = float(match.group(2))
                break
            
    return data


def plot_data():
    unique_benchmark = POLICY
    data = read_data()
    origin_val = read_origin_data()
    
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
    plt.title(f'RocksDB Benchmark Result', fontsize=14)
    plt.ylabel(f'ops/sec', fontsize=12)
    plt.xticks(np.arange(len(unique_benchmark)), unique_benchmark, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'result.png'))
    
    
if __name__ == "__main__":
    plot_data()