CONF_DIR="bench.cfg"
POLICY=("IMMEDIATE" "FULL_SINGLE" "FULL_HALF" "FULL_ALL" "WATERMARK_NAIVE" "WATERMARK_HIGHLOW")
MAPPING_SIZE=("4k" "16k" "32k")

if lsmod | grep -q "^nvmev"; then
    sudo rmmod nvmev
fi

mkdir -p output

for policy in "${POLICY[@]}"; do
    mkdir -p output/$policy
    for map in "${MAPPING_SIZE[@]}"; do
        echo "Running $policy-$map"
        sudo insmod ../../device_files/${policy}/nvmev_${map}.ko memmap_start=48G memmap_size=16G cpus=10,11,12,13
        sudo mkfs.ext4 -F /dev/nvme3n1
        sudo mount /dev/nvme3n1 /mnt/nvme
        sudo postmark ${CONF_DIR} > "output/${policy}/${map}.txt"
        sudo umount /mnt/nvme
        sudo rmmod nvmev
        sudo dmesg > "output/${policy}/${map}.log"
    done
done