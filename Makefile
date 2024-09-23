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
	memmap_size=16G \
	cpus=10,11,12,13

unload:
	sudo rmmod nvmev

mount:
	sudo mkfs -t ext4 /dev/nvme3n4
	sudo mount /dev/nvme3n4 /test_tmp

fio_line:
	sudo fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=write --bs=16k --size=32k --numjobs=1 \
	--filename=/dev/nvme3n1 --direct=1 --group_reporting --norandommap

fio_single:
	sudo fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=write --bs=4k --size=8M --numjobs=1 \
	--filename=/dev/nvme3n1 --direct=1 --group_reporting --norandommap

fio:
	./fio.sh