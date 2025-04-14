#!/bin/bash
#"IMMEDIATE" 
# POLICY=("IMMEDIATE" "FULL_SINGLE" "FULL_HALF" "FULL_ALL" "WATERMARK_NAIVE" "WATERMARK_HIGHLOW")
# MAPPING_SIZE=("4k" "16k" "32k")
# WORKLOAD=("fileserver" "webserver" "varmail" "webproxy")

POLICY=("FULL_ALL")
MAPPING_SIZE=("16k")
WORKLOAD=("webproxy")

echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi

mkdir -p output

for policy in "${POLICY[@]}"; do
    echo "Running $policy"
    mkdir -p output/$policy
    for map in "${MAPPING_SIZE[@]}"; do
        for workload in "${WORKLOAD[@]}"; do
            echo "Running $workload-$map"
            sudo insmod ../../device_files/${policy}/nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
            sudo mkfs.ext4 -F /dev/nvme3n1
            sudo mount /dev/nvme3n1 /mnt/nvme
            sudo chown layfort:layfort /mnt/nvme
            sudo filebench -f ${workload}.f > "output/${policy}/${map}_${workload}.txt"
            sudo umount /mnt/nvme
            sudo rmmod nvmev
            sudo dmesg > "output/${policy}/${map}_${workload}.log"
        done
    done
done