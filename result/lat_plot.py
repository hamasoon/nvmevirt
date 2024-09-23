import matplotlib.pyplot as plt
import numpy as np
import sys

def read_file(file_name):
    with open(file_name, 'r') as f:
        lines = f.readlines()
    return lines

def parse(lines):
    read_lat = []
    buffer_lat = []
    write_lat = []
    total_lat = []
    for line in lines:
        if 'read_lat' in line:
            read_lat.append(int(line.split(',')[0].split('=')[1]))
            buffer_lat.append(int(line.split(',')[1].split('=')[1]))
            write_lat.append(int(line.split(',')[2].split('=')[1]))
            total_lat.append(read_lat[-1] + buffer_lat[-1] + write_lat[-1])
    return read_lat, buffer_lat, write_lat, total_lat

def plot(read_lat, buffer_lat, write_lat, total_lat, file_name):
    x = np.arange(0, len(read_lat), 1)
    plt.figure(figsize=(10, 5))
    plt.plot(x, read_lat, label='read')
    plt.plot(x, buffer_lat, label='buffer')
    plt.plot(x, write_lat, label='write')
    plt.plot(x, total_lat, label='total')
    plt.legend()
    plt.xlabel('Operations')
    plt.ylabel('Latency (ns)')
    plt.title('Latency')
    plt.savefig(f'{file_name}.png')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python3 lat_plot.py <file_name>')
        sys.exit(1)
    file_name = sys.argv[1]
    lines = read_file(file_name)
    read_lat, buffer_lat, write_lat, total_lat = parse(lines)
    plot(read_lat, buffer_lat, write_lat, total_lat, file_name)