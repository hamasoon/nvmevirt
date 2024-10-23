import os
import re
import pandas as pd
import matplotlib.pyplot as plt

# Load data
def read_data(bs, mapping_size):
    pattern = r"w=(\d+\.\d+|\d+)\s*MiB/s.*\[eta\s*(\d+)m:(\d+)s\]"
    data = pd.DataFrame(columns=['bw', 'time'])
    
    filename = f'{mapping_size}/seq-write-async-{bs}.log'
    filepath = os.path.join(os.path.dirname(__file__), f'{filename}')
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return data
    
    with open(filepath, 'r') as file:
        lines = [line.strip() for line in file.readlines()]
        for line in lines:
            match = re.search(pattern, line)
            if match:
                bw = float(match.group(1))  # 'MiB/s' 부분 제거 후 정수 변환
                eta_m = int(match.group(2))  # 분
                eta_s = int(match.group(3))  # 초
                time = 300 - (eta_m * 60 + eta_s)  # 총 시간 계산
                data.loc[len(data)] = [bw, time]
            else:
                print(f'No match found in line: {line}')
                
    return data

def plot_data(data1, data2, data3, bs):
    plt.figure(figsize=(10, 6))
    plt.plot(data1['time'], data1['bw'], label='4K')
    plt.plot(data2['time'], data2['bw'], label='16K')
    plt.plot(data3['time'], data3['bw'], label='32K')
    
    plt.xlabel('Time (s)')
    plt.ylabel('Bandwidth (MiB/s)')
    plt.title('GC effect on write performance')
    plt.legend()
    
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/{bs}.png'))
    
if __name__ == '__main__':
    bs = ['4k', '8k', '16k', '32k', '64k', '128k']
    for b in bs:
        data1 = read_data(b, '4k')
        data2 = read_data(b, '16k')
        data3 = read_data(b, '32k')
        plot_data(data1, data2, data3, b)