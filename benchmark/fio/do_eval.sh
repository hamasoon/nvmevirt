#!/bin/bash
if [ -z "$DEV" ]; then
    DEV="nvme3n1"
fi
JOBS=4
DEPTH=32

# Create the output directory if it doesn't exist
mkdir -p output

# Run all workloads in workloads directory
for workload in workloads/*; do
    # Strip the directory and file suffix to use only the base name for output
    workload_name=$(basename "$workload" .fio)
    echo "Running $workload"
    sudo DEV="/dev/${DEV}" JOBS=${JOBS} DEPTH=${DEPTH} \
        fio "$workload" --output-format=json --output="output/${workload_name}.json"
done
