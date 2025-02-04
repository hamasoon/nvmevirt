import random
import os 

FTL_INSTANCES = 4
PAGE_SIZE = 32768
SIZE = '4G'
BS = '4K'

def size_parser(size):
    if size[-1] == 'K' or size[-1] == 'k':
        return int(size[:-1]) * 1024
    elif size[-1] == 'M' or size[-1] == 'm':
        return int(size[:-1]) * 1024 * 1024
    elif size[-1] == 'G' or size[-1] == 'g':
        return int(size[:-1]) * 1024 * 1024 * 1024
    else:
        return int(size)

def linear(cnt):
    return [i for i in range(cnt * FTL_INSTANCES)]

def round_robin(cnt):
    result = []
    testset = [[] for _ in range(FTL_INSTANCES)]
    bpp = PAGE_SIZE // size_parser(BS)
    gap = bpp * FTL_INSTANCES
    
    for j in range(FTL_INSTANCES):
        for i in range(cnt):
            testset[j].append(i % bpp + gap * (i // bpp) + j * bpp)
        
        random.shuffle(testset[j])
    
    for i in range(cnt):
        for j in range(FTL_INSTANCES):
            result.append(testset[j][i])
    
    return result

def round_robin_per_pages(cnt):
    result = []
    testset = [[] for _ in range(FTL_INSTANCES)]
    random.shuffle(page_num)
    bpp = PAGE_SIZE // size_parser(BS)
    gap = bpp * FTL_INSTANCES
    page_num = [i for i in range(cnt // bpp)]
    
    for j in range(FTL_INSTANCES):
        for i in page_num:
            tmp = []
            for i in range(bpp):
                tmp.append(i % bpp + gap * (i // bpp) + j * bpp)
            testset[j] += random.shuffle(tmp)
    
    for i in range(cnt // bpp):
        for j in range(FTL_INSTANCES):
            for k in range(bpp):
                result.append(testset[j][i])
    
    return result

def save_testset(testset):
    filename = os.path.join(os.path.dirname(__file__), 'testset.txt')
    with open(filename, 'w') as f:
        for t in testset:
            f.write(f'{t}\n')

if __name__ == '__main__':
    cnt = size_parser(SIZE) // size_parser(BS) // FTL_INSTANCES
    testset = linear(cnt)
    save_testset(testset)