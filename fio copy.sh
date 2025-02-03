#!/bin/bash
RW=("write")
MAPPING_SIZE=("4k" "16k" "32k" "origin")
BS=("4k" "8k" "16k" "32k" "64k" "128k" "256k")
SYNC=("sync" "async")
RAND=("rand" "seq")
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
    for rw in "${RW[@]}"; do
        for bs in "${BS[@]}"; do
            for sync in "${SYNC[@]}"; do
                for rand in "${RAND[@]}"; do
                    sudo insmod ./nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
                    if [ "$rw" == "read" ]; then
                        sudo fio --name=fill_ssd --ioengine=psync --iodepth=1 --rw=write --bs=32k --size=8G --numjobs=1 \
	--filename=/dev/nvme3n1 --direct=1 --norandommap
                    fi
                    # sudo fio --name=test --ioengine=sync --iodepth=1 --rw=randwrite --bs=4k --size=4G --numjobs=1 --filename=/dev/nvme3n1 --direct=1 --group_reporting
                    sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches '
                    sudo sync
                    sleep 1

                    workload="fio/${rand}${rw}.fio"
                    echo "Running $workload-$bs-$sync"

                    if [ "$sync" == "sync" ]; then
                        sudo DEV="/dev/${DEV}" JOB=1 DEPTH=1 \
                            fio "$workload" --bs=${bs} --output-format=json --ioengine=psync --size=12G \
                                --output="output/${map}/${rand}${rw}-${sync}-${bs}.json"
                    else
                        sudo DEV="/dev/${DEV}" JOB="$JOBS" DEPTH="$DEPTH" \
                            fio "$workload" --bs=${bs} --output-format=json --ioengine=io_uring --size=3G \
                                --output="output/${map}/${rand}${rw}-${sync}-${bs}.json"
                    fi
                    sudo dmesg > "output/${map}/${rand}${rw}-${sync}-${bs}.log"
                    sudo rmmod nvmev
                done
            done
        done
    done
done