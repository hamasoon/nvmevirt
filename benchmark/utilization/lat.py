import os
import re
import numpy as np
import matplotlib.pyplot as plt

TOTAL_RUNTIME = [1853000, 1866000, 1894000, 1940000, 1902000]
BS = ['4k', '8k', '16k', '32k', '64k']

# Feb 27 01:19:31 layfort-MS-7D75 kernel: [ 2250.655848] NVMeVirt: Write Wait Time: 35210
PATTERN = re.compile(r'NVMeVirt: Write Wait Time: (\d+)')

def parse_log():
    data = {}
    
    for bs in BS:
        temp = []
        filename = f'lat_{bs}.txt'
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'r') as f:
            for line in f:
                match = PATTERN.search(line)
                if match:
                    temp.append(int(match.group(1)))
                    
        data[bs] = np.array(temp)
    
    return data

if __name__ == '__main__':
    data = parse_log()
    
    for bs, runtime in zip(BS, TOTAL_RUNTIME):
        print(f'statistics for {bs}:')
        print(f'mean: {np.mean(data[bs])}')
        print(f'median: {np.median(data[bs])}')
        print(f'std: {np.std(data[bs])}')
        print(f'total: {len(data[bs])}')
        print(f'ratio: {len(data[bs]) / runtime}')
        print()
        