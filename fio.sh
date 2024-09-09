#!/bin/bash

# Check if the nvmev module is loaded
if lsmod | grep -q "^nvmev"; then
    echo "nvmev module is loaded. Running fio test."
    
    # Run fio command
    sudo fio test.fio --output=result/test.json --output-format=json
else
    echo "nvmev module is not loaded."
fi
