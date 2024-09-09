import json
import matplotlib.pyplot as plt
import numpy as np

def plot(filename):
    # Load JSON output from fio
    with open(f'{filename}.json') as f:
        fio_data = json.load(f)

    # Initialize lists to store bandwidths
    read_bw = []
    write_bw = []
    jobs = []

    # Loop through each job and extract read/write bandwidth
    for job in fio_data['jobs']:
        job_name = job['jobname']
        read_bandwidth = job['read']['bw'] / 1000  # Read bandwidth (in KB/s)
        write_bandwidth = job['write']['bw'] / 1000  # Write bandwidth (in KB/s)
        
        # Append data to lists
        jobs.append(job_name)
        read_bw.append(read_bandwidth)
        write_bw.append(write_bandwidth)

    # Convert jobs to a numpy array for better control over bar positions
    x = np.arange(len(jobs))  # the label locations

    # Define width of the bars
    width = 0.35

    # Plotting
    plt.figure(figsize=(15, 6))

    # Plot the read and write bandwidth bars with an offset for alignment
    bar1 = plt.bar(x - width/2, read_bw, width, label='Read Bandwidth (MB/s)')
    bar2 = plt.bar(x + width/2, write_bw, width, label='Write Bandwidth (MB/s)')

    for bar in bar1:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, height, f'{int(height)}', ha='center', va='bottom')

    for bar in bar2:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, height, f'{int(height)}', ha='center', va='bottom')

    # Add labels and title
    plt.xlabel('Job Groups')
    plt.ylabel('Bandwidth (MB/s)')
    plt.ylim(0, 8000)
    plt.title('Read and Write Bandwidth per Job Group')
    plt.xticks(x, jobs)  # Set the x-ticks to be the job names
    plt.legend()

    # Show the plot
    plt.tight_layout()
    plt.savefig(f'{filename}.png')

if __name__ == '__main__':
    plot('4k')
    plot('16k')
