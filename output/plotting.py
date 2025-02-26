import os
import json
import matplotlib.pyplot as plt
import pandas as pd
    
def read_data(type, mapping, target_data):
    random = ['rand', 'seq']
    rw = ['write']
    sync = ['async', 'sync']
    size = ['4k', '8k', '16k', '32k', '64k', '128k', '256k']
    index = []
    
    for r in random:
        for rw_type in rw:
            for s in sync:
                index.append(f'{r}-{rw_type}-{s}')
                
    data = pd.DataFrame(columns=index, index=size)
   
    for r in random:
        for rw_type in rw:
            for s in sync:
                for sz in size:
                    data.at[sz, f'{r}-{rw_type}-{s}'] = 0
                    if mapping == 'origin':
                        filename = mapping + '/' + r + rw_type + '-' + s + '-' + sz + '.json'
                    else:
                        filename = type + '/' + mapping + '/' + r + rw_type + '-' + s + '-' + sz + '.json'
                    filepath = os.path.join(os.path.dirname(__file__), filename)
                    with open(filepath, 'r') as f:
                        raw_data = json.loads(f.read())
                        if target_data == 'lat_ns':
                            data.at[sz, f'{r}-{rw_type}-{s}'] = float(raw_data['jobs'][0][rw_type]['lat_ns']['mean']) / 1000
                        elif target_data == 'bw':
                            data.at[sz, f'{r}-{rw_type}-{s}'] = float(raw_data['jobs'][0][rw_type]['bw']) / 1000
                        # data[r][rw_type][s][sz] = raw_data['jobs'][target_data]
                        
    return data

def read_mix_data(type):
    size = ['4k', '8k', '16k', '32k', '64k', '128k', '256k']
    mix_ratio = [0, 10, 30, 50, 70, 90, 100]
    read_bw = pd.DataFrame(index=mix_ratio, columns=size)
    write_bw = pd.DataFrame(index=mix_ratio, columns=size)
    ops = pd.DataFrame(index=mix_ratio, columns=size)
    
    for mix in mix_ratio:
        for sz in size:
            filename = f'{type}_mix/rand-rw-async-{sz}-{mix}.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'r') as f:
                raw_data = json.loads(f.read())
                if raw_data['jobs'][0]['read']['bw'] == 0:
                    read_bw.at[mix, sz] = 0
                else:
                    read_bw.at[mix, sz] = float(raw_data['jobs'][0]['read']['bw']) / 1000
                if raw_data['jobs'][0]['write']['bw'] == 0:
                    write_bw.at[mix, sz] = 0
                else:
                    write_bw.at[mix, sz] = float(raw_data['jobs'][0]['write']['bw']) / 1000
                ops.at[mix, sz] = raw_data['jobs'][0]['write']['iops'] + raw_data['jobs'][0]['read']['iops']
    

    return read_bw, write_bw, ops

def plot_single(data, random='rand', rw_type='read', sync='sync', x_label='Block Size(Byte)', y_label='BW (MB/s)'):
    size = ['4K', '8K', '16K', '32K', '64K', '128K', '256K', '512K', '1M']
    data_type = f'{random}-{rw_type}-{sync}'
    
    plt.figure(figsize=(9, 6))
    plt.plot(size, data[data_type], marker='o')
    plt.xticks(size)
    plt.ylim(0, data[data_type].max() + 100)
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(f'{random}-{rw_type}-{sync}')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'plot/' + random + '-' + rw_type + '-' + sync + '.png'))

def plot_data(data1, data2, data3, data4, type, random='rand', rw_type='read', sync='sync', x_label='Block Size(Byte)', y_label='BW (MB/s)', plot_type='line'):
    size = ['4K', '8K', '16K', '32K', '64K', '128K', '256K']
    data_type = f'{random}-{rw_type}-{sync}'

    plt.figure(figsize=(9, 6))

    if plot_type == 'line':
        plt.plot(size, data1[data_type], label='4K', marker='o')
        plt.plot(size, data2[data_type], label='16K', marker='x')
        plt.plot(size, data3[data_type], label='32K', marker='s')
        plt.plot(size, data4[data_type], label='Origin', marker='d')
        plt.ylim(0, max(data1[data_type].max(), data2[data_type].max(), data3[data_type].max(), data4[data_type].max()) + 100)
    elif plot_type == 'bar':
        w = 0.2
        x = range(len(size))
        plt.bar([i - 1.5 * w for i in x], data1[data_type], width=w, label='4K', align='center')
        plt.bar([i - 0.5 * w for i in x], data2[data_type], width=w, label='16K', align='center')
        plt.bar([i + 0.5 * w for i in x], data3[data_type], width=w, label='32K', align='center')
        plt.bar([i + 1.5 * w for i in x], data4[data_type], width=w, label='Origin', align='center')
        plt.xticks(x, size)
    
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(f'{random}-{rw_type}-{sync}')
    plt.legend(title='Mapping Size')
                
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'plot/' + type)):
        os.mkdir(os.path.join(os.path.dirname(__file__), 'plot/' + type))
    plt.savefig(os.path.join(os.path.dirname(__file__), 'plot/' + type + '/' + random + '-' + rw_type + '-' + sync + '.png'))
    plt.clf()
    plt.close()
    
def plot_mix_data(data1, data2, data3, type):
    for sz in data1.columns:
        plt.clf()
        plt.figure(figsize=(9, 6))
        plt.plot(data1.index, data1[sz], label='4K', marker='o')
        plt.plot(data2.index, data2[sz], label='16K', marker='x')
        plt.plot(data3.index, data3[sz], label='32K', marker='s')
        plt.xlabel('Read Ratio (%)')
        plt.ylabel(f'{type}')
        plt.title(f'{sz} Block Size')
        plt.legend()
        plt.savefig(os.path.join(os.path.dirname(__file__), 'plot/mix/' + sz + '.png'))
        
if __name__ == '__main__':
    type = ['IMMEDIATE', 'FULL', 'FULL_QUATER', 'FULL_HALF', 'HALF', 'HALF_STATIC_FIFO', 'HALF_WATERMARK_FIFO', 'HALF_WATERMARK_LRU', 'HALF_WATERMARK_FIFOPLUS', 'HALF_WATERMARK_LRUPLUS']
    dict = {}
    
    origin_data = read_data('', 'origin', 'bw')
    
    for t in type:    
        data1 = read_data(t, '4k', 'bw')
        data2 = read_data(t, '16k', 'bw')
        data3 = read_data(t, '32k', 'bw')
        
        random = ['rand', 'seq']
        rw = ['write']
        sync = ['async', 'sync']
        
        for r in random:
            for rw_type in rw:
                for s in sync:
                    plot_data(data1, data2, data3, origin_data, t, r, rw_type, s, 'Block Size(Byte)', 'BW (MB/s)', 'line')
    
    # data = read_data('origin', 'bw')
    
    # random = ['rand', 'seq']
    # rw = ['read', 'write']
    # sync = ['sync', 'async']
    
    # for r in random:
    #     for rw_type in rw:
    #         for s in sync:
    #             plot_single(data, r, rw_type, s)
    
    # read_4k, write_4k, ops_4k = read_mix_data('4k')
    # read_16k, write_16k, ops_16k = read_mix_data('16k')
    # read_32k, write_32k, ops_32k = read_mix_data('32k')
    # bw_4k = read_4k + write_4k
    # bw_16k = read_16k + write_16k
    # bw_32k = read_32k + write_32k
    # plot_mix_data(ops_4k, ops_16k, ops_32k, 'IOPS (ops/sec)')
    # plot_mix_data(bw_4k, bw_16k, bw_32k, 'BW (MB/s)')
    