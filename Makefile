KERNELDIR := /lib/modules/$(shell uname -r)/build
PWD       := $(shell pwd)
INSTALL_MOD_PATH :=

include Makefile.local

default:
		$(MAKE) -C $(KERNELDIR) M=$(PWD) modules

install:
		$(MAKE) INSTALL_MOD_PATH="$(INSTALL_MOD_PATH)" -C $(KERNELDIR) modules_install

.PHONY: clean
clean:
	   $(MAKE) -C $(KERNELDIR) M=$(PWD) clean
	   rm -f cscope.out tags nvmev.S

.PHONY: cscope
cscope:
		cscope -b -R
		ctags *.[ch]

.PHONY: tags
tags: cscope

.PHONY: format
format:
	clang-format -i *.[ch]

.PHONY: dis
dis:
	objdump -d -S nvmev.ko > nvmev.S

load:
	sudo insmod ./nvmev.ko \
	memmap_start=48G \
	memmap_size=2G \
	cpus=10,11,12,13

unload:
	sudo rmmod nvmev

mount:
	sudo mkfs.ext4 -F /dev/nvme3n1
	sudo mount /dev/nvme3n1 /mnt/nvme
	sudo chown layfort:layfort /mnt/nvme

umount:
	sudo umount /mnt/nvme

fio_line:
	sudo fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=write --bs=4k --size=32k --numjobs=1 \
	--filename=/dev/nvme3n1 --direct=1 --group_reporting --norandommap

fio_single_write:
	sudo fio --name=test --ioengine=sync --iodepth=1 --rw=randwrite --bs=8k --size=2G --numjobs=1 \
	--filename=/dev/nvme3n1 --direct=1 --group_reporting

fio_single_read:
	sudo fio --name=test --ioengine=libaio --iodepth=32 --rw=read --bs=8k --size=14G --numjobs=4 \
	--filename=/dev/nvme3n1 --direct=1 --group_reporting

fio:
	./fio.sh
