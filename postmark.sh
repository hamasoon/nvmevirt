MAPPING_SIZE=("4k" "16k" "32k")
BS=("4k" "16k" "32k")
DEV="nvme3n1"

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    make unload
fi

mkdir -p postmark_output

for map in "${MAPPING_SIZE[@]}"; do
    mkdir -p "postmark_output/${map}"
    for bs in "${BS[@]}"; do
        sudo insmod ./nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
        sudo mkfs.ext4 -F /dev/nvme3n1
        sudo mount /dev/nvme3n1 /mnt/nvme
        sudo chown layfort:layfort /mnt/nvme
        sudo postmark benchmark/postmark/${bs}.conf > "postmark_output/${map}_${bs}.txt"
        sudo rmmod nvmev
    done
done
