import os
import re
import pandas as pd
import matplotlib.pyplot as plt

def read_timeline_data(type, workload):
    path = os.path.join(os.path.dirname(__file__), 'output/timeline/' + type + '_' + workload + '.txt')
    data = pd.DataFrame(columns=['Time', 'Throughput'], dtype=float)
    
    pattern = r"(\d+ sec): \d+ operations; ([\d.]+) current ops/sec;"
    
    with open(path, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                time = int(match.group(1).split(' ')[0])
                throughput = float(match.group(2))
                data = pd.concat([data, pd.DataFrame([[time, throughput]], columns=['Time', 'Throughput'])], ignore_index=True)
                
    return data

def read_data(type):
    path = os.path.join(os.path.dirname(__file__), 'output/' + type + '_result.txt')
    workloads = ['A', 'B', 'C', 'D', 'E', 'F']
    data = pd.DataFrame(columns=workloads, index=['Throughput', 'Read Lat', 'Insert Lat', 'Update Lat', 'Scan Lat', 'RMW Lat'], dtype=float)
    
    idx = 0
    workload = workloads[0]
    
    with open(path, 'r') as f:
        for line in f:
            if line == '\n':
                idx += 1
                workload = workloads[idx]
            
            words = [word.strip() for word in line.split(' ')]
            if len(words) < 2:
                continue
            
            ops = words[0][1:-2]
            data_type = words[1].split('(')[0]
            value = float(words[2])
            
            if ops == 'OVERALL' and data_type == 'Throughput':
                data.loc['Throughput', workload] = float(words[2])
            elif ops == 'READ' and data_type == 'AverageLatency':
                data.loc['Read Lat', workload] = float(words[2])
            elif ops == 'INSERT' and data_type == 'AverageLatency':
                data.loc['Insert Lat', workload] = float(words[2])
            elif ops == 'UPDATE' and data_type == 'AverageLatency':
                data.loc['Update Lat', workload] = float(words[2])
            elif ops == 'SCAN' and data_type == 'AverageLatency':
                data.loc['Scan Lat', workload] = float(words[2])
            elif ops == 'READ-MODIFY-WRITE' and data_type == 'AverageLatency':
                data.loc['RMW Lat', workload] = float(words[2])
                
    return data

def plot_data(data1, data2, data3):
    workloads = ['A', 'B', 'C', 'D', 'E', 'F']
    labels = ['4K', '16K', '32K']
    
    for workload in workloads:
        plt.clf()
        
        plt.figure(figsize=(9, 6))
        data = []
        data = [data1.loc['Throughput', workload], data2.loc['Throughput', workload], data3.loc['Throughput', workload]]
        bar = plt.bar(labels, data, alpha=0.7, color=['white', 'white', 'gray'], edgecolor='black')
        bar[0].set_label('4K')
        bar[1].set_label('16K')
        bar[2].set_label('32K')
        bar[1].set_hatch('/')
        
        plt.xlabel('Block Size (Byte)')
        plt.ylabel('Throughput (ops/sec)')
        plt.title(f'Workload {workload}')
        plt.savefig(os.path.join(os.path.dirname(__file__), f'output/workload{workload}.png'))

def plot_timeline_data():
    workloads = ['A', 'B', 'C', 'D', 'E', 'F']
    labels = ['4K', '16K', '32K']
    
    for workload in workloads:
        plt.clf()
        
        df1 = read_timeline_data('4k', workload)
        df2 = read_timeline_data('16k', workload)
        df3 = read_timeline_data('32k', workload)
        # 4개의 subplot 생성
        fig, axs = plt.subplots(2, 2, figsize=(10, 8))

        # 첫 번째 subplot - 데이터 1
        axs[0, 0].plot(df1['Time'], df1['Throughput'])
        axs[0, 0].set_title('4K')
        axs[0, 0].set_xlabel('Time(s)')
        axs[0, 0].set_ylabel('Throughput(ops/sec)')
        axs[0, 0].set_ylim(0, max(df1['Throughput']) * 1.1)

        # 두 번째 subplot - 데이터 2
        axs[0, 1].plot(df2['Time'], df2['Throughput'], color='orange')
        axs[0, 1].set_title('16K')
        axs[0, 1].set_xlabel('Time(s)')
        axs[0, 1].set_ylabel('Throughput(ops/sec)')
        axs[0, 1].set_ylim(0, max(df2['Throughput']) * 1.1)

        # 세 번째 subplot - 데이터 3
        axs[1, 0].plot(df3['Time'], df3['Throughput'], color='green')
        axs[1, 0].set_title('32K')
        axs[1, 0].set_xlabel('Time(s)')
        axs[1, 0].set_ylabel('Throughput(ops/sec)')
        axs[1, 0].set_ylim(0, max(df3['Throughput']) * 1.1)

        # 네 번째 subplot - 데이터 1, 2, 3 합쳐서
        axs[1, 1].plot(df1['Time'], df1['Throughput'], label='4K')
        axs[1, 1].plot(df2['Time'], df2['Throughput'], label='16K')
        axs[1, 1].plot(df3['Time'], df3['Throughput'], label='32K')
        axs[1, 1].set_title('Compare')
        axs[1, 1].set_xlabel('Time(s)')
        axs[1, 1].set_ylabel('Throughput(ops/sec)')
        axs[1, 1].set_ylim(0, max(max(df1['Throughput']), max(df2['Throughput']), max(df3['Throughput'])) * 1.1)
        axs[1, 1].legend()
        
        plt.suptitle(f'Workload {workload}')
        plt.tight_layout(pad=2.0)
        
        plt.savefig(os.path.join(os.path.dirname(__file__), f'output/timeline_workload{workload}.png'))
            
if __name__ == '__main__':
    data1 = read_data('4k')
    data2 = read_data('16k')
    data3 = read_data('32k')
    
    plot_data(data1, data2, data3)
    plot_timeline_data()