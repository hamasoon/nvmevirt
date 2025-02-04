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
	sudo echo 2 > /sys/block/$(DEV)/queue/
	
run:
	sudo python3 test.py

.PHONY: all clean