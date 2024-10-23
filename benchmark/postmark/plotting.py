import os
import matplotlib.pyplot as plt

if __name__ == '__main__':
    labels = ['4K', '16K', '32K']
    read_throughput = [100.71, 90.04, 80.07]
    write_throughput = [101.08, 90.36, 80.36]  

    bar = plt.bar(labels, read_throughput, alpha=0.7, color=['white', 'white', 'gray'], edgecolor='black')
    bar[1].set_hatch('/')
    
    plt.xlabel('Block Size (Byte)')
    plt.ylabel('Read Bandwidth (MB/s)')
    plt.title('Read Operation')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'read_bw.png'))
    
    plt.clf()
    bar = plt.bar(labels, write_throughput, alpha=0.7, color=['white', 'white', 'gray'], edgecolor='black')
    bar[1].set_hatch('/')
    
    plt.xlabel('Block Size (Byte)')
    plt.ylabel('Write Bandwidth (MB/s)')
    plt.title('Write Operation')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'write_bw.png'))