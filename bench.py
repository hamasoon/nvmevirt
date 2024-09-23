import os
import time
import string
import random

def generate_nasty_dirname(length=255):
    """Generate a directory name with special characters and a long length."""
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))

def benchmark_create_delete(directory_path, iterations=100):
    create_times = []
    delete_times = []

    for i in range(iterations):
        # Generate a nasty directory name
        nasty_dir = generate_nasty_dirname()
        full_path = os.path.join(directory_path, nasty_dir)

        # Benchmark directory creation
        start_time = time.time()
        os.makedirs(full_path)
        create_times.append(time.time() - start_time)

        # Benchmark directory deletion
        start_time = time.time()
        os.rmdir(full_path)
        delete_times.append(time.time() - start_time)

    # Report average times
    avg_create_time = sum(create_times) / iterations
    avg_delete_time = sum(delete_times) / iterations

    print(f"Average time to create directory: {avg_create_time:.6f} seconds")
    print(f"Average time to delete directory: {avg_delete_time:.6f} seconds")

if __name__ == "__main__":
    # Set your target directory path here
    target_path = "/test_tmp"
    
    # Run the benchmark
    benchmark_create_delete(target_path)
