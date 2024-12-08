#!/bin/bash
MAPPING_SIZE=("4k")
BS=("16k" "32k" "64k")
SYNC=("sync" "async")
RAND=("rand")
JOBS=4
DEPTH=32
DEV="nvme3n1"

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi

mkdir -p output

for map in "${MAPPING_SIZE[@]}"; do
    mkdir -p "output/${map}"
    for bs in "${BS[@]}"; do
        for sync in "${SYNC[@]}"; do
            for rand in "${RAND[@]}"; do
                workload="fio/${rand}write.fio"
                workload_name=$(basename "$workload" .fio)
                echo "Running $workload-$bs-$sync"
                sudo insmod ./nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
                sudo DEV="/dev/${DEV}" JOBS=${JOBS} DEPTH=${DEPTH} \
                    fio "$workload" --bs=${bs} \
                        --output-format=json --output="output/${map}/${rand}-write-${sync}-${bs}.json"
                sudo rmmod nvmev
            done
        done
    done
done
