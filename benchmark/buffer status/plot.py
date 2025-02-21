import os
import re
import matplotlib.pyplot as plt

# [ 2560.183149] NVMeVirt: Buffer State Free ppgs: 11, Flushing ppgs: 21, Used ppgs: 0
PATTERN = r"NVMeVirt: Buffer State Free ppgs: (\d+), Flushing ppgs: (\d+), Used ppgs: (\d+)"

# [ 2336.353506] NVMeVirt: Buffer Status: Free 1, Flushing 25, Used 6
PATTERN2 = r"NVMeVirt: Buffer Status: Free (\d+), Flushing (\d+), Used (\d+)"

def read_data(filename):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    data_local = []
    data_global = []
    
    with open(filepath, 'r') as f:
        for line in f:
            match = re.search(PATTERN, line)
            if match:
                free, flushing, used = int(match.group(1)), int(match.group(2)), int(match.group(3))
                data_local.append(free / (free + flushing + used) * 100) 
            else:
                match = re.search(PATTERN2, line)
                if match:
                    free, flushing, used = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    data_global.append(free / (free + flushing + used) * 100)
                    
    return data_local, data_global

def plot_data(data_local, data_global):
    plt.clf()
    plt.figure(figsize=(10, 6))
    
    plt.plot(data_local, label='Local', marker='o')
    plt.plot(data_global, label='Global', marker='x')
    plt.legend()
    plt.title('Buffer Status')
    plt.xlabel('Time (s)')
    plt.ylabel('Free (%)')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'plot.png'))
    
    
if __name__ == '__main__':
    data_local, _ = read_data('local.txt')
    _, data_global = read_data('global.txt')
    plot_data(data_local, data_global)