import random
import os 

FTL_INSTANCES = 4
PAGE_SIZE = 32768

FILENAME = '/dev/nvme3n1'
IO_ENGINE = 'libaio'
NUMJOBS = 4
IO_DEPTH = 16
SIZE = '4G'
BS = '128K'
UNIT = 4096

def size_parser(size):
    if size[-1] == 'K' or size[-1] == 'k':
        return int(size[:-1]) * 1024
    elif size[-1] == 'M' or size[-1] == 'm':
        return int(size[:-1]) * 1024 * 1024
    elif size[-1] == 'G' or size[-1] == 'g':
        return int(size[:-1]) * 1024 * 1024 * 1024
    else:
        return int(size)

def linear(size, bs=BS):
    result = []
    remaining = 0
    gap = size_parser(bs)
    
    while remaining < size:
        result.append(remaining)
        remaining += gap
        
    return result

def random_access(size, bs=BS):
    testset = linear(size, bs)
    random.shuffle(testset)
    return testset

def round_robin_sequential(size, bs=BS):
    result = []
    tmp = [[] for _ in range(FTL_INSTANCES)]
    lin_data = linear(size, bs)
    
    for d in lin_data:
        tmp[(d // PAGE_SIZE) % FTL_INSTANCES].append(d)
        
    for j in range(len(tmp[0])):
        for i in range(FTL_INSTANCES):
            if j < len(tmp[i]):
                result.append(tmp[i][j])
        
    return result

def round_robin_random(size, bs=BS):
    result = []
    tmp = [[] for _ in range(FTL_INSTANCES)]
    lin_data = linear(size, bs)
    
    for d in lin_data:
        tmp[(d // PAGE_SIZE) % FTL_INSTANCES].append(d)
        
    for i in range(FTL_INSTANCES):
        random.shuffle(tmp[i])
        
    for j in range(len(tmp[0])):
        for i in range(FTL_INSTANCES):
            if j < len(tmp[i]):
                result.append(tmp[i][j])
        
    return result

def round_robin_per_pages(size, bs=BS):
    result = []
    tmp = [[] for _ in range(FTL_INSTANCES)]
    lin_data = linear(size, bs)
    
    for d in lin_data:
        tmp[(d // PAGE_SIZE) % FTL_INSTANCES].append(d)
        
    for i in range(FTL_INSTANCES):
        random.shuffle(tmp[i])
        
    for j in range(len(tmp[0])):
        for i in range(FTL_INSTANCES):
            if j < len(tmp[i]): 
                result.append(tmp[i][j])
    
    return result

def save_testset(testset):
    filename = os.path.join(os.path.dirname(__file__), 'testset.txt')
    with open(filename, 'w') as f:
        for t in testset:
            f.write(f'{t}\n')

def run_test(testtype, bs=BS):
    cnt = size_parser(SIZE)
    testset = testtype(cnt, bs)
    save_testset(testset)
    
    print('Compile test.c')
    test_filename = os.path.join(os.path.dirname(__file__), 'test')
    test_c_filename = os.path.join(os.path.dirname(__file__), 'test.c')
    os.system(f'gcc -Wall -O2 -I/usr/include -o {test_filename} {test_c_filename} -L/usr/lib/x86_64-linux-gnu -laio -luring -lpthread')
    
    # run test
    print('Run test')
    print(f'Arguments: filename={FILENAME}, io_engine={IO_ENGINE}, numjobs={NUMJOBS}, io_depth={IO_DEPTH}, size={SIZE}, bs={bs}')
    os.system(f'sudo {test_filename} -f {FILENAME} -m {IO_ENGINE} -j {NUMJOBS} -q {IO_DEPTH} -t {SIZE} -b {bs}')

if __name__ == '__main__':
    run_test(round_robin_sequential, bs='4K')
    run_test(round_robin_sequential, bs='8K')
    run_test(round_robin_sequential, bs='16K')
    # run_test(round_robin_sequential, bs='32K')
    # run_test(round_robin, bs='64K')
    # run_test(round_robin, bs='128K')