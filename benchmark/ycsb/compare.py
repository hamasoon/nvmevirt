import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PATTERN = r"(\d+ sec): \d+ operations; ([\d.]+) current ops/sec;"
WORKLOADS = ['a', 'b', 'c', 'd', 'e', 'f']
BENCHMARK = [
    "IMMEDIATE", "FULL_SINGLE", "FULL_HALF", "FULL_ALL", "WATERMARK_NAIVE", "WATERMARK_HIGHLOW", "LOCAL"
]
MAPPING = ["4k", "16k", "32k"]

def read_data(mapping, workload, benchmark):
    data = pd.Series(index=['Throughput', 'Read Lat', 'Insert Lat', 'Update Lat', 'Scan Lat', 'RMW Lat'])
    timeline = pd.DataFrame(columns=['Time', 'Throughput'])

    if benchmark != 'origin':
        path = os.path.join(os.path.dirname(__file__), f'output/{benchmark}/{mapping}/workload{workload}.txt')
    else:
        path = os.path.join(os.path.dirname(__file__), f'output/{benchmark}/workload{workload}.txt')
    
    with open(path, 'r') as f:
        for line in f:
            match = re.search(PATTERN, line)
            if match:
                time = int(match.group(1).split(' ')[0])
                throughput = float(match.group(2)) / 1000
                timeline = pd.concat([timeline, pd.DataFrame([[time, throughput]], columns=['Time', 'Throughput'])], ignore_index=True)
            else:
                words = [word.strip() for word in line.split(' ')]
                if len(words) < 2:
                    continue
                
                ops = words[0][1:-2]
                data_type = words[1].split('(')[0]
                
                if ops == 'OVERALL' and data_type == 'Throughput':
                    data.loc['Throughput'] = float(words[2]) / 1000
                elif ops == 'READ' and data_type == 'AverageLatency':
                    data.loc['Read Lat'] = float(words[2]) / 1000
                elif ops == 'INSERT' and data_type == 'AverageLatency':
                    data.loc['Insert Lat'] = float(words[2]) / 1000
                elif ops == 'UPDATE' and data_type == 'AverageLatency':
                    data.loc['Update Lat'] = float(words[2]) / 1000
                elif ops == 'SCAN' and data_type == 'AverageLatency':
                    data.loc['Scan Lat'] = float(words[2]) / 1000
                elif ops == 'READ-MODIFY-WRITE' and data_type == 'AverageLatency':
                    data.loc['RMW Lat'] = float(words[2]) / 1000
                
    return data, timeline

def plot_data(data: pd.DataFrame, target):
    print(data)
    
    unique_benchmark = BENCHMARK + ['origin']
    origin_val = data.loc['origin', target]
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.plot(figsize=(24, 14))
    
    for i, bench in enumerate(unique_benchmark):
        if bench == 'origin':
            val = data.loc[bench, target]
            plt.bar(i, val, width, color='gray', label="Origin" if i == len(unique_benchmark)-1 else "")
            
        else:
            for k, mapping in enumerate(MAPPING):
                offset = (k - (len(MAPPING) - 1) / 2) * width
                val = data.loc[f'{bench}_{mapping}', target] 
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
    plt.title(f'{target}', fontsize=14)
    plt.ylabel('Raw Value', fontsize=12)
    plt.xticks(np.arange(len(unique_benchmark)), unique_benchmark, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'output/{target}.png'))

def plot_timeline_data(df1, df2, df3, df4):
    for workload in WORKLOADS:
        plt.clf()

        # 네 번째 subplot - 데이터 1, 2, 3 합쳐서
        plt.plot(df1[workload]['Time'], df1[workload]['Throughput'], label='4K')
        plt.plot(df2[workload]['Time'], df2[workload]['Throughput'], label='16K')
        plt.plot(df3[workload]['Time'], df3[workload]['Throughput'], label='32K')
        plt.plot(df4[workload]['Time'], df4[workload]['Throughput'], label='Origin')
        plt.xlabel('Time(s)')
        plt.ylabel('Throughput(Kops/sec)')
        plt.ylim(0, max(max(df1[workload]['Throughput']), max(df2[workload]['Throughput']), max(df3[workload]['Throughput']), max(df4[workload]['Throughput'])) * 1.1)
        plt.legend()
        plt.title(f'Workload {workload.capitalize()} Throughput Timeline')
        
        plt.tight_layout(pad=2.0)
        
        plt.savefig(os.path.join(os.path.dirname(__file__), f'output/plot/timeline_workload{workload}.png'))
            
if __name__ == '__main__':
    data = pd.DataFrame(columns=['Throughput', 'Read Lat', 'Insert Lat', 'Update Lat', 'Scan Lat', 'RMW Lat'])
    
    for benchmark in BENCHMARK:
        for mapping in MAPPING:
            tmp, _ = read_data(mapping, 'a', benchmark)
            data.loc[f'{benchmark}_{mapping}', :] = tmp
            
    data.loc['origin', :] = read_data('origin', 'a', 'origin')[0]
    
    plot_data(data, 'Throughput')