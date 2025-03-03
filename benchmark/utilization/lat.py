import os
import re
import numpy as np
import matplotlib.pyplot as plt

BS = ['16k', '32k']

# Feb 27 01:19:31 layfort-MS-7D75 kernel: [ 2250.655848] NVMeVirt: Write Wait Time: 35210[ 6429.587973] NVMeVirt: Write Latency:
PATTERN = re.compile(r'NVMeVirt: Write Latency: (\d+)')

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
    
    for bs in BS:
        print(f'statistics for {bs}:')
        print(f'mean: {np.mean(data[bs])}')
        print(f'median: {np.median(data[bs])}')
        print(f'std: {np.std(data[bs])}')
        print(f'total: {np.sum(data[bs])}')
        print(f'count: {len(data[bs])}')
        print()
        