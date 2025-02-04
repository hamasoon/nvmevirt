CC = gcc
CFLAGS = -Wall -O2 -I/usr/include
LDFLAGS = -L/usr/lib/x86_64-linux-gnu
LIBS = -laio -lpthread

all: test

test: test.c
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS) $(LIBS)

run:
	sudo ./test --threads 4 --iodepth 16 --bs 4k --size 4G --file /dev/nvme2n1

clean:
	rm -f test
