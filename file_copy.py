import os
import sys
import time
from glob import glob
from shutil import copy

source_dir = sys.argv[1]
dest_dir = sys.argv[2]

channels = ["488nm", "560nm"]
source_files = []

for channel in channels:
    source_files.append(glob(os.path.join(source_dir, "*{}*.tif".format(channel))))

total = len(source_files[0])
# for i, channel in enumerate(channels):
current_index = 0
for j in range(total):
    print("Time point ", j)
    for k in range(len(channels)):
        copy(source_files[k][j], dest_dir)
        time.sleep(1)