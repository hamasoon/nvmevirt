CC = gcc
CFLAGS = -Wall -O2 -I/usr/include
LDFLAGS = -L/usr/lib/x86_64-linux-gnu
LIBS = -laio -luring -lpthread
TARGET_LIBAIO = test_libaio
TARGET_URING = test_uring
DEV = nvme2n1

all: $(TARGET_LIBAIO) $(TARGET_URING)

$(TARGET_LIBAIO): test_libaio.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS) $(LIBS)
	
$(TARGET_URING): test_uring.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS) $(LIBS)

clean:
	rm -f test_libaio test_uring

nonmerge:
	sudo echo 2 > /sys/block/$(DEV)/queue/nomerges

.PHONY: all clean