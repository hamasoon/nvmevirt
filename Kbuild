# Select one of the targets to build
#CONFIG_NVMEVIRT_NVM := y
CONFIG_NVMEVIRT_SSD := y
#CONFIG_NVMEVIRT_ZNS := y
#CONFIG_NVMEVIRT_KV := y

# Mapping Size
# MAPPING_4KB 0
# MAPPING_16KB 1
# MAPPING_32KB 2

# Buffer Flush Timing Policy
# IMMEDIATE 0
# FULL 1
# WATERMARK_NAIVE 5
# WATERMARK_HIGHLOW 6
# WATERMARK_ONDEMAND 7

# Buffer Flush Target Policy
# FIFO 0
# FIFO_GREEDY 1

# Buffer Flush Amount Policy */
#SINGLE 0
#DOUBLE 1
#BUFFER_QUATER 2
#BUFFER_HALF 3
#BUFFER_ALL 4

obj-m   := nvmev.o
nvmev-objs := main.o pci.o admin.o io.o dma.o
ccflags-y += -Wno-unused-variable -Wno-unused-function

ccflags-$(CONFIG_NVMEVIRT_NVM) += -DBASE_SSD=INTEL_OPTANE
nvmev-$(CONFIG_NVMEVIRT_NVM) += simple_ftl.o

ccflags-$(CONFIG_NVMEVIRT_SSD) += -DBASE_SSD=SAMSUNG_970PRO -DFLUSH_TARGET_POLICY=FIFO -DFLUSH_TIMING_POLICY=WATERMARK_HIGHLOW -DFLUSH_AMOUNT_POLICY=BUFFER_ALL -DMAPPING_SIZE=MAPPING_4KB
nvmev-$(CONFIG_NVMEVIRT_SSD) += ssd.o conv_ftl.o pqueue/pqueue.o channel_model.o

ccflags-$(CONFIG_NVMEVIRT_ZNS) += -DBASE_SSD=WD_ZN540
#ccflags-$(CONFIG_NVMEVIRT_ZNS) += -DBASE_SSD=ZNS_PROTOTYPE
ccflags-$(CONFIG_NVMEVIRT_ZNS) += -Wno-implicit-fallthrough
nvmev-$(CONFIG_NVMEVIRT_ZNS) += ssd.o zns_ftl.o zns_read_write.o zns_mgmt_send.o zns_mgmt_recv.o channel_model.o

ccflags-$(CONFIG_NVMEVIRT_KV) += -DBASE_SSD=KV_PROTOTYPE
nvmev-$(CONFIG_NVMEVIRT_KV) += kv_ftl.o append_only.o bitmap.o
