import os
import re
import pandas as pd
import matplotlib.pyplot as plt

PATTERN = r"(\d+ sec): \d+ operations; ([\d.]+) current ops/sec;"
WORKLOADS = ['a', 'b', 'c', 'd', 'e', 'f']
LABELS = ['4K', '16K', '32K', 'Origin']

def read_data(mapping):
    data = pd.DataFrame(columns=WORKLOADS, index=['Throughput', 'Read Lat', 'Insert Lat', 'Update Lat', 'Scan Lat', 'RMW Lat'], dtype=float)
    timeline = {workload: pd.DataFrame(columns=['Time', 'Throughput']) for workload in WORKLOADS}
    
    for workload in WORKLOADS:
        path = os.path.join(os.path.dirname(__file__), 'output/' + mapping + f'/workload{workload}.txt')
        with open(path, 'r') as f:
            for line in f:
                match = re.search(PATTERN, line)
                if match:
                    time = int(match.group(1).split(' ')[0])
                    throughput = float(match.group(2))
                    timeline[workload] = pd.concat([timeline[workload], pd.DataFrame([[time, throughput]], columns=['Time', 'Throughput'])], ignore_index=True)
                else:
                    words = [word.strip() for word in line.split(' ')]
                    if len(words) < 2:
                        continue
                    
                    ops = words[0][1:-2]
                    data_type = words[1].split('(')[0]
                    
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
                
    return data, timeline

def plot_data(df1, df2, df3, df4):
    for workload in WORKLOADS:
        plt.clf()
        
        plt.figure(figsize=(9, 6))
        data = []
        data = [df1.loc['Throughput', workload], df2.loc['Throughput', workload], df3.loc['Throughput', workload], df4.loc['Throughput', workload]]
        bar = plt.bar(LABELS, data, alpha=0.7, color=['white', 'white', 'gray', 'gray'], edgecolor='black')
        bar[0].set_label('4K')
        bar[1].set_label('16K')
        bar[2].set_label('32K')
        bar[3].set_label('Origin')
        bar[1].set_hatch('/')
        bar[3].set_hatch('/')
        
        plt.xlabel('Block Size (Byte)')
        plt.ylabel('Throughput (ops/sec)')
        plt.title(f'Workload {workload} Throughput')
        plt.savefig(os.path.join(os.path.dirname(__file__), f'output/plot/workload{workload.capitalize()}.png'))

def plot_timeline_data(df1, df2, df3, df4):
    for workload in WORKLOADS:
        plt.clf()

        # 네 번째 subplot - 데이터 1, 2, 3 합쳐서
        plt.plot(df1[workload]['Time'], df1[workload]['Throughput'], label='4K')
        plt.plot(df2[workload]['Time'], df2[workload]['Throughput'], label='16K')
        plt.plot(df3[workload]['Time'], df3[workload]['Throughput'], label='32K')
        plt.plot(df4[workload]['Time'], df4[workload]['Throughput'], label='Origin')
        plt.xlabel('Time(s)')
        plt.ylabel('Throughput(ops/sec)')
        plt.ylim(0, max(max(df1[workload]['Throughput']), max(df2[workload]['Throughput']), max(df3[workload]['Throughput']), max(df4[workload]['Throughput'])) * 1.1)
        plt.legend()
        plt.title(f'Workload {workload} Throughput Timeline')
        
        plt.tight_layout(pad=2.0)
        
        plt.savefig(os.path.join(os.path.dirname(__file__), f'output/plot/timeline_workload{workload.capitalize()}.png'))
            
if __name__ == '__main__':
    data1, timeline1 = read_data('4k')
    data2, timeline2 = read_data('16k')
    data3, timeline3 = read_data('32k')
    data4, timeline4 = read_data('origin')
    
    plot_data(data1, data2, data3, data4)
    plot_timeline_data(timeline1, timeline2, timeline3, timeline4)