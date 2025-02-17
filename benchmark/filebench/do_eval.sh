#!/bin/bash
MAPPING_SIZE=("4k" "16k" "32k" "origin")
WORKLOAD=("fileserver" "webserver" "varmail" "webproxy")

echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi

mkdir -p output

for map in "${MAPPING_SIZE[@]}"; do
    for workload in "${WORKLOAD[@]}"; do
        echo "Running $workload-$map"
        sudo insmod ../../nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
        sudo mkfs.ext4 -F /dev/nvme3n1
        sudo mount /dev/nvme3n1 /mnt/nvme
        sudo chown layfort:layfort /mnt/nvme
        sudo filebench -f ${workload}.f > "output/${map}_${workload}.txt"
        sudo umount /mnt/nvme
        sudo rmmod nvmev
    done
done