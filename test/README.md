# Benchmark Program for specific I/O patterns

## Pre-requisites

### Install `libaio` library

```bash
$ sudo apt-get install libaio-dev
```

### Install `fio` benchmark tool

```bash
$ sudo apt-get install fio
```

## Running the Benchmark

### Set your device's merge option off

```bash
$ sudo bash -c 'echo 2 > /sys/block/${DEV}/queue/nomerges'
```

### Set parameters for the benchmark

```python
# Parameters
FILENAME = '/dev/nvme2n1'
IO_ENGINE = 'libaio'
NUMJOBS = 4
IO_DEPTH = 16
SIZE = '4G'
BS = '4K'
```

### Run the benchmark

```bash
$ sudo test.py
```