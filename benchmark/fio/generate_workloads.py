import os

def workloads(seq, job_type, sync, block_size, size, runtime, mix_read=70):
    if seq != 'seq' and seq != 'rand':
        raise ValueError('seq must be either "seq" or "rand"')

    if job_type != 'read' and job_type != 'write' and job_type != 'rw':
        raise ValueError('job_type must be either "read", "write", or "rw"')
    
    if sync != 'sync' and sync != 'async':
        raise ValueError('sync must be either "sync" or "async"')

    if job_type == 'rw':
        file_name = f'{seq}-{job_type}-{sync}-{block_size}-{mix_read}'
    else:
        file_name = f'{seq}-{job_type}-{sync}-{block_size}'
    file_path = os.path.join(os.path.dirname(__file__), f'workloads/{file_name}.fio')
    file = open(file_path, 'w')
    file.write('[global]\n')
    file.write(f'size={size}\n')
    file.write('direct=1\n')
    file.write('time_based\n')
    file.write(f'runtime={runtime}\n')
    file.write('\n')
    if sync == 'sync':
        file.write('ioengine=sync\n')
    else:
        file.write('ioengine=libaio\n')
    file.write('numjobs=${JOBS}\n')
    file.write('iodepth=${DEPTH}\n')
    file.write('group_reporting\n')
    file.write('\n')
    file.write(f'[{file_name}]\n')
    file.write('filename=/dev/nvme3n1\n')
    if seq == 'seq':
        file.write(f'rw={job_type}\n')
    else:
        file.write(f'rw=rand{job_type}\n')
        file.write('random_distribution=random\n')
        
    if job_type == 'rw':
        file.write(f'rwmixread={mix_read}\n')
    file.write(f'bs={block_size}\n')
    file.close()
    
def clear_workloads():
    file_path = os.path.join(os.path.dirname(__file__), 'workloads')
    for file in os.listdir(file_path):
        os.remove(os.path.join(file_path, file))

if __name__ == '__main__':
    seq_list = ['seq', 'rand']
    job_type_list = ['read']
    sync_list = ['sync']
    block_size_list = ['4k', '8k', '16k', '32k', '64k', '128k']
    size = '127G'
    runtime = 60
    
    clear_workloads()
        
    for seq in seq_list:
        for job_type in job_type_list:
            for sync in sync_list:
                for block_size in block_size_list:
                    workloads(seq, job_type, sync, block_size, size, runtime)