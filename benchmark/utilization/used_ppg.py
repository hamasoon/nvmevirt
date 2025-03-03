import os
import re
import matplotlib.pyplot as plt
import matplotlib.cm as cm


# 2025-02-27T12:20:55.677380+09:00 hamasoon-Legion-Slim-5-16IRH8 kernel: message repeated 261 times: [ NVMeVirt: allocate fail - used_ppgs: 1, flushing_ppgs: 31, free_ppgs: 0]
# get repeated times and used_ppgs
PATTERN1 = re.compile(r'message repeated (\d+) times: \[ NVMeVirt: allocate fail - used_ppgs: (\d+), flushing_ppgs: \d+, free_ppgs: \d+\]')

# 2025-02-27T12:20:55.677381+09:00 hamasoon-Legion-Slim-5-16IRH8 kernel: NVMeVirt: allocate fail - used_ppgs: 0, flushing_ppgs: 32, free_ppgs: 0
PATTERN2 = re.compile(r'NVMeVirt: allocate fail - used_ppgs: (\d+), flushing_ppgs: \d+, free_ppgs: \d+')

FILENAME = 'used_ppg.log'

def read_data(filename):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    data = {'0': 0, '1': 0, '2': 0, '3': 0}
    
    with open(filepath, 'r') as f:
        for line in f:
            match = PATTERN1.search(line)
            if match:
                repeated, used_ppgs = map(int, match.groups())
                data[str(used_ppgs)] += repeated
            else:
                match = PATTERN2.search(line)
                if match:
                    used_ppgs = int(match.group(1))
                    data[str(used_ppgs)] += 1
                    
    plt.figure(figsize=(10, 6))
    cmap = plt.get_cmap('Set1')
    colors = [cmap(i / len(data)) for i in range(len(data))]
    plt.bar(data.keys(), data.values(), color=colors)
    plt.xlabel('Used PPGs')
    plt.ylabel('Count')
    plt.title('Used PPGs Distribution When Allocation Fails')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'used_ppg.png'))
    
if __name__ == '__main__':
    read_data(FILENAME)