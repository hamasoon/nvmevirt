#!/bin/bash
# MAPPING_SIZE=("4k" "16k" "32k")
# BS=("4k" "8k" "16k" "32k" "64k")
# SYNC=("sync" "async")
# RAND=("seq" "rand")
MAPPING_SIZE=("4k" "16k" "32k")
BS=("128k")
SYNC=("async")
RAND=("seq")
JOBS=4
DEPTH=32
DEV="nvme3n1"

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi
    
mkdir -p output/timeline

for map in "${MAPPING_SIZE[@]}"; do
    mkdir -p "output/timeline/${map}"
    for bs in "${BS[@]}"; do
        for sync in "${SYNC[@]}"; do
            for rand in "${RAND[@]}"; do
                workload="fio/${rand}write_timeline.fio"
                workload_name=$(basename "$workload" .fio)
                echo "Running $workload-$bs-$sync"
                sudo insmod ./nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
                sudo DEV="/dev/${DEV}" JOBS=${JOBS} DEPTH=${DEPTH} \
                    fio "$workload" --bs=${bs} --eta-newline=1
                sudo rmmod nvmev
            done
        done
    done
done
