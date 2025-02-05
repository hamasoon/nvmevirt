CC = gcc
CFLAGS = -Wall -O2 -I/usr/include
LDFLAGS = -L/usr/lib/x86_64-linux-gnu
LIBS = -laio -luring -lpthread
TARGET = test
DEV = nvme2n1

all: $(TARGET)

$(TARGET): $(TARGET).c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS) $(LIBS)

clean:
	rm -f test

nonmerge:
	sudo bash -c 'echo 2 > /sys/block/nvme3n1/queue/nomerges'
	
run:
	sudo python3 test.py

.PHONY: all clean