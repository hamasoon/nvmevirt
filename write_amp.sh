#!/bin/bash
MAPPING_SIZE=("4k" "16k" "32k")
BS=("4k" "8k" "16k" "32k" "64k")

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi

mkdir -p write_amp_output

for map in "${MAPPING_SIZE[@]}"; do
    for bs in "${BS[@]}"; do
        echo "Running write_amp-$map-$bs"
        sudo insmod nvmev_${map}.ko memmap_start=48G memmap_size=2G cpus=10,11,12,13
        sudo fio --name=test --ioengine=sync --iodepth=1 --rw=randwrite --bs=${bs} --size=4G --numjobs=1 --filename=/dev/nvme3n1 --direct=1 --group_reporting
        sudo dmesg > "write_amp_output/${map}_${bs}.txt"
        sudo rmmod nvmev
    done
done