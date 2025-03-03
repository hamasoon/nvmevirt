import os
import json
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

SIZE = ['4k', '8k', '16k', '32k', '64k', '128k', '256k']
TYPE = ['IMMEDIATE', 'FULL', 'FULL_QUATER', 'FULL_HALF', 'HALF', 'HALF_STATIC_FIFO', 'HALF_WATERMARK_FIFO', 'HALF_WATERMARK_LRU', 'HALF_WATERMARK_FIFOPLUS', 'HALF_WATERMARK_LRUPLUS']

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
        
        
def compare_tpyes_all(mapping, rw, random, sync, target_data):
    data = pd.DataFrame()
    
    # JSON 파일에서 데이터를 읽어와 data DataFrame에 저장한다.
    for t in TYPE:
        for sz in SIZE:
            if mapping == 'origin':
                filename = mapping + '/' + random + rw + '-' + sync + '-' + sz + '.json'
            else:
                filename = t + '/' + mapping + '/' + random + rw + '-' + sync + '-' + sz + '.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'r') as f:
                raw_data = json.loads(f.read())
                if target_data == 'lat_ns':
                    data.at[t, sz] = float(raw_data['jobs'][0][rw]['lat_ns']['mean']) / 1000
                elif target_data == 'bw':
                    data.at[sz, t] = float(raw_data['jobs'][0][rw]['bw']) / 1000
                    
    for sz in SIZE:
        filename = 'origin' + '/' + random + rw + '-' + sync + '-' + sz + '.json'
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'r') as f:
            raw_data = json.loads(f.read())
            if target_data == 'lat_ns':
                data.at[t, sz] = float(raw_data['jobs'][0][rw]['lat_ns']['mean']) / 1000
            elif target_data == 'bw':
                data.at[sz, 'origin'] = float(raw_data['jobs'][0][rw]['bw']) / 1000

    data.plot(kind='line', marker='o', figsize=(9, 6))
    plt.xlabel('Block Size (Byte)')
    plt.ylabel('BW (MB/s)')
    plt.ylim(0, data.max().max() + 100)
    plt.title(f'{random}-{rw}-{sync}')
    plt.legend(title='Policies')
    plt.savefig(os.path.join(os.path.dirname(__file__), 'compare/' + random + '-' + rw + '-' + sync + '.png'))
        
def compare_types(mapping, rw, random, sync, target_data):
    data = pd.DataFrame()
    
    for t in TYPE:
        for sz in SIZE:
            if mapping == 'origin':
                filename = mapping + '/' + random + rw + '-' + sync + '-' + sz + '.json'
            else:
                filename = t + '/' + mapping + '/' + random + rw + '-' + sync + '-' + sz + '.json'
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'r') as f:
                raw_data = json.loads(f.read())
                if target_data == 'lat_ns':
                    data.at[t, sz] = float(raw_data['jobs'][0][rw]['lat_ns']['mean']) / 1000
                elif target_data == 'bw':
                    data.at[sz, t] = float(raw_data['jobs'][0][rw]['bw']) / 1000

    # 학술적인 디자인을 위해 serif 폰트를 사용하고, seaborn의 whitegrid 스타일을 적용한다.
    plt.rc('text', usetex=False)  # LaTeX 사용 시 True로 변경 가능하다.
    plt.rc('font', family='serif', size=12)
    
    if 'seaborn-whitegrid' in plt.style.available:
        plt.style.use('seaborn-whitegrid')
    else:
        plt.style.use('default')
    
    fig, ax = plt.subplots(figsize=(9, 8))
    
    # '4k'에 해당하는 데이터를 선택하여 바 차트를 그린다.
    plot_data = data.loc['4k']
    
    # 학술 분야에서 명확한 색상 구분을 위해 'tab10' 팔레트를 사용한다.
    colors = sns.color_palette("tab10", len(plot_data))
    bars = ax.bar(plot_data.index, plot_data.values, color=colors, edgecolor='black')
    
    # 각 막대 위에 값을 표기한다.
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha='center', va='bottom',
                    fontsize=10)
    
    # x축 레이블을 대각선(45도)으로 회전시켜 겹침을 방지한다.
    plt.xticks(rotation=45)
    
    # 축 레이블과 제목을 설정하고, 적절한 여백과 글씨 크기를 조정한다.
    ax.set_xlabel('Block Size (Byte)', fontsize=14, labelpad=10)
    ax.set_ylabel('BW (MB/s)', fontsize=14, labelpad=10)
    ax.set_title(f'{random}-{rw}-{sync}', fontsize=16, fontweight='bold', pad=15)
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    # 요소들이 겹치지 않도록 레이아웃을 조정한다.
    plt.tight_layout()
    
    # PNG 형식으로 저장하며, dpi를 300으로 설정하여 고해상도를 유지한다.
    save_path = os.path.join(os.path.dirname(__file__), 'compare', f'{random}-{rw}-{sync}.png')
    plt.savefig(save_path, dpi=300)
    plt.close()
        
if __name__ == '__main__':
    compare_types('32k', 'write', 'rand', 'async', 'bw')
    # dict = {}
    
    # origin_data = read_data('', 'origin', 'bw')
    
    # for t in type:    
    #     data1 = read_data(t, '4k', 'bw')
    #     data2 = read_data(t, '16k', 'bw')
    #     data3 = read_data(t, '32k', 'bw')
        
    #     random = ['rand', 'seq']
    #     rw = ['write']
    #     sync = ['async', 'sync']
        
    #     for r in random:
    #         for rw_type in rw:
    #             for s in sync:
    #                 plot_data(data1, data2, data3, origin_data, t, r, rw_type, s, 'Block Size(Byte)', 'BW (MB/s)', 'line')
    
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
    