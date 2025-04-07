import os
import json
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

MAPPING = ['4k', '16k', '32k']
SIZE = ['4k', '8k', '16k', '32k', '64k', '128k', '256k']
POLICY = ['IMMEDIATE', 'FULL_SINGLE', 'FULL_HALF', 'FULL_ALL', 'WATERMARK_NAIVE', 'WATERMARK_HIGHLOW']
RANDOM = ['rand', 'seq']
RW = ['write', 'rw']
SYNC = ['async', 'sync']
    
def read_data(policy, random, rw, sync):
    r_data = pd.DataFrame(index=SIZE, columns=MAPPING)
    w_data = pd.DataFrame(index=SIZE, columns=MAPPING)
    
    for map in MAPPING:
        for sz in SIZE:
            filename = f'{policy}/{map}/{random}{rw}-{sync}-{sz}.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'r') as f:
                raw_data = json.loads(f.read())
                r_data.at[sz, map] = float(raw_data['jobs'][0]['read']['bw']) / 1000
                w_data.at[sz, map] = float(raw_data['jobs'][0]['write']['bw']) / 1000
                
    return r_data, w_data

def plot_data(policy, random, rw, sync):
    plt.clf()
    r_data, w_data = read_data(policy, random, rw, sync)
    
    if rw == 'rw':
        tmp = r_data + w_data
        tmp.plot(kind='bar', label='Read+Write')
    elif rw == 'write':
        w_data.plot(kind='bar', label='Write')
    elif rw == 'read':
        r_data.plot(kind='bar', label='Read')
    
    plt.xlabel('Size')
    plt.ylabel('Bandwidth (MB/s)')
    plt.title(f'{policy}-{random}-{rw}-{sync}')
    plt.legend()
    plt.savefig(f'output/{policy}-{random}-{rw}-{sync}.png')
    plt.close()
        
if __name__ == '__main__':
    for policy in POLICY:
        for random in RANDOM:
            for rw in RW:
                for sync in SYNC:
                    plot_data(policy, random, rw, sync)
                    
    