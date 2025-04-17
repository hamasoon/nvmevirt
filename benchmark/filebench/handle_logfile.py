import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections import deque

POLICY = ["IMMEDIATE", "FULL_SINGLE", "FULL_HALF", "FULL_ALL", "WATERMARK_NAIVE", "WATERMARK_HIGHLOW"]
BENCHMARK = ["fileserver", "varmail", "webproxy", "webserver"]
MAPPING = ["4k", "16k", "32k"]
MAPPING_SIZE = {
    "4k": 4096,
    "16k": 16384,
    "32k": 32768
}

TIMELINE_PATTERN = re.compile(r'\[\s*([0-9]+\.[0-9]+)\]')
WRITE_SIZE_PATTERN = re.compile(r'Write Size count: (\d+) Sec')
READ_SIZE_PATTERN = re.compile(r'Read Size count: (\d+) Sec')
RMW_WRITE_PATTERN = re.compile(r'RMW write count: (\d+)')
DIRECT_WRITE_PATTERN = re.compile(r'Direct write count: (\d+)')
WRITE_SIZE_CNT_PATTERN = re.compile(r'NVMeVirt:\s*(\d+):\s*(\d+)')
WRITE_HIT_PATTERN = re.compile(r'Write Hit Count: (\d+)')
READ_HIT_PATTERN = re.compile(r'Read Hit Count: (\d+)')

def trim_log_file(path: str, keep_lines: int = 75) -> None:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        last_lines = deque(f, maxlen=keep_lines)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(last_lines)

def traverse_and_trim(directory: str) -> None:
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith('.log'):
                full_path = os.path.join(root, filename)
                try:
                    trim_log_file(full_path)
                    print(f'처리 완료: {full_path}')
                except Exception as e:
                    print(f'오류 발생 ({full_path}): {e}')

class log_data:
    def __init__(self, policy, mapping, benchmark):
        self.policy = policy
        self.mapping = mapping
        self.benchmark = benchmark
        self.runtime = 0
        self.r_total_size = 0
        self.w_total_size = 0
        self.rmw_cnt = 0
        self.direct_cnt = 0
        self.write_size_cnt = {}
        self.read_hit_size = 0
        self.write_hit_size = 0
        
    def read_log_data(self):
        filename = os.path.join(os.path.dirname(__file__), f"output/{self.policy}/{self.mapping}_{self.benchmark}.log")
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        if not os.path.isfile(filepath):
            print(f'유효하지 않은 파일 경로: {filepath}')
            return
        
        with open(filepath, "r") as f:
            lines = f.readlines()
            start_time = TIMELINE_PATTERN.search(lines[0]).group(1)
            end_time = TIMELINE_PATTERN.search(lines[1]).group(1)
            self.runtime = float(end_time) - float(start_time)
            self.w_total_size = int(WRITE_SIZE_PATTERN.search(lines[3]).group(1))
            self.r_total_size = int(READ_SIZE_PATTERN.search(lines[4]).group(1))
            self.rmw_cnt = int(RMW_WRITE_PATTERN.search(lines[5]).group(1))
            self.direct_cnt = int(DIRECT_WRITE_PATTERN.search(lines[6]).group(1))
            self.write_hit_size = int(WRITE_HIT_PATTERN.search(lines[72]).group(1))
            self.read_hit_size = int(READ_HIT_PATTERN.search(lines[73]).group(1))
            
            for line in lines[7:72]:
                match = WRITE_SIZE_CNT_PATTERN.search(line)
                if match:
                    size = int(match.group(1))
                    count = int(match.group(2))
                    self.write_size_cnt[size] = count
                
    def print_log_data(self):
        print(f"정책: {self.policy}, 매핑: {self.mapping}")
        print(f"실행 시간: {self.runtime} 초")
        print(f"쓰기 총 크기: {self.w_total_size} 바이트")
        print(f"읽기 총 크기: {self.r_total_size} 바이트")
        print(f"RMW 개수: {self.rmw_cnt}")
        print(f"Direct 개수: {self.direct_cnt}")
        print(f"쓰기 사이즈 카운트: {self.write_size_cnt}")
        print(f"쓰기 히트 사이즈: {self.write_hit_size}")
        print(f"읽기 히트 사이즈: {self.read_hit_size}")
        
def plot_data(data_type, data):
    if data_type == 'write_per_time':
        return plot_write_per_time(data)
    elif data_type == 'read_per_time':
        return plot_read_per_time(data)
    elif data_type == 'write_hit':
        return plot_write_hit(data)
    elif data_type == 'write_hit_ratio':
        return plot_write_hit_ratio(data)
    elif data_type == 'read_hit':
        return plot_read_hit(data)
    elif data_type == 'RMW_ratio':
        return plot_RMW_ratio(data)
    elif data_type == 'write_size_cnt':
        return plot_write_size_cnt(data)
    
def plot_write_per_time(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].w_total_size / raw_data[policy][mapping].runtime / 1024 / 1024 * 4096
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'Write Size per Time', fontsize=14)
    plt.ylabel(f'MB/Sec', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/write_per_size.png'))
    
def plot_read_per_time(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].r_total_size / raw_data[policy][mapping].runtime / 1024 / 1024 * 4096
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'Read Size per Time', fontsize=14)
    plt.ylabel(f'MB/Sec', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/read_per_size.png'))
    
def plot_write_hit(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].write_hit_size
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'Write Hit Size per Time', fontsize=14)
    plt.ylabel(f'Hit Count', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/write_hit.png'))
    
def plot_write_hit_ratio(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].write_hit_size / (raw_data[policy][mapping].w_total_size * 4096 / MAPPING_SIZE[mapping])
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'Write Hit Ratio', fontsize=14)
    plt.ylabel(f'Ratio', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/write_hit_ratio.png'))
    
def plot_read_hit(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].read_hit_size
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'Read Hit Size per Time', fontsize=14)
    plt.ylabel(f'Hit Count', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/read_hit.png'))
    
def plot_RMW_ratio(raw_data: dict):
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = raw_data[policy][mapping].rmw_cnt / (raw_data[policy][mapping].rmw_cnt + raw_data[policy][mapping].direct_cnt)
    
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    
    plt.clf()
    plt.plot(figsize=(30, 16))
    for i, policy in enumerate(POLICY):
        for k, mapping in enumerate(MAPPING):
            offset = (k - (len(MAPPING) - 1) / 2) * width
            val = data[policy][mapping]
            bars = plt.bar(
                i + offset, 
                val, 
                width, 
                color=color_dict.get(mapping, 'gray'),
                label=mapping.capitalize() if i == 0 else ""
            )
            
    plt.title(f'RMW Ratio per Time', fontsize=14)
    plt.ylabel(f'Ratio', fontsize=12)
    plt.xticks(np.arange(len(POLICY)), POLICY, rotation=45, fontsize=8)
    plt.legend(title="Mapping", loc="lower right", fontsize=10)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/RMW_ratio.png'))
        
def plot_write_size_cnt(raw_data: dict):
    data = raw_data["IMMEDIATE"]["4k"].write_size_cnt
    plt.clf()
    plt.plot(figsize=(30, 16))
    # normal line plot
    plt.plot(data.keys(), data.values(), marker='o')
    plt.title(f'Write Size Count', fontsize=14)
    plt.ylabel(f'Count', fontsize=12)
    plt.xlabel(f'Size', fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), f'plot/write_size_cnt.png'))
    
if __name__ == '__main__':
    benchmark = "fileserver"
    data = {}
    for policy in POLICY:
        data[policy] = {}
        for mapping in MAPPING:
            data[policy][mapping] = log_data(policy, mapping, benchmark)
            data[policy][mapping].read_log_data()
            
    plot_data('write_per_time', data)
    plot_data('read_per_time', data)
    plot_data('write_hit', data)
    plot_data('write_hit_ratio', data)
    plot_data('read_hit', data)
    plot_data('RMW_ratio', data)
    plot_data('write_size_cnt', data)