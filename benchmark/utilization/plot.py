import os
import re
import matplotlib.pyplot as plt

# Feb 20 02:03:56 layfort-MS-7D75 kernel: [14438.886104] NVMeVirt: Buffer State Free secs: 832, Total secs: 2048 Utilized Ratio: 59%
PATTERN = re.compile(r'NVMeVirt: Buffer State Free secs: (\d+), Total secs: (\d+) Utilized Ratio: (\d+)%')

# [ 2362.046847] NVMeVirt: Buffer Utilization Ratio: 90%
PATTERN2 = re.compile(r'Buffer Utilization Ratio: (\d+)%')

def read_data(filename):
    data = []
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open (filepath, 'r') as f:
        for line in f:
            match = PATTERN.search(line)
            if match:
                _, _, ratio = map(int, match.groups())
                data.append(ratio)
    return data

def read_data2(filename):
    data = []
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open (filepath, 'r') as f:
        for line in f:
            match = PATTERN2.search(line)
            if match:
                ratio = int(match.group(1))
                data.append(ratio)
    return data

def plot(data, data2):
    plt.figure(figsize=(10, 6))
    plt.plot(data, label='Local Buffer')
    plt.plot(data2, label='Global Buffer')
    plt.xlabel('Time')
    plt.ylabel('Utilization Ratio (%)')
    plt.title('NVMeVirt Utilization Ratio')
    plt.legend()
    plt.savefig(os.path.join(os.path.dirname(__file__), 'utilization.png'))
    
if __name__ == '__main__':
    data = read_data('data.txt')
    data2 = read_data2('data2.txt')
    plot(data, data2)