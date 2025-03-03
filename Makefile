KERNELDIR := /lib/modules/$(shell uname -r)/build
PWD       := $(shell pwd)
INSTALL_MOD_PATH :=

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

4k:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules
	mv nvmev.ko nvmev_4k.ko

16k:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules
	mv nvmev.ko nvmev_16k.ko

32k:
	$(MAKE) -C $(KERNELDIR) M=$(PWD) modules
	mv nvmev.ko nvmev_32k.ko

include Makefile.local

# Immediately remove 