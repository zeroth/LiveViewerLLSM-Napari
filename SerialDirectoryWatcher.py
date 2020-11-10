import os
import sys
import time
from napari.qt.threading import WorkerBase
from skimage.io.collection import alphanumeric_key
from dask import delayed
import dask.array as da
from tifffile import imread
from qtpy.QtCore import Signal, Slot
from napari.qt.threading import WorkerBase, WorkerBaseSignals
from typing import Type
from napari.qt import thread_worker
import logging
logging.getLogger("tifffile").setLevel(logging.ERROR)

def sort_files_by_channels(files, channels):
    file_channels = {}
    for channel in channels:
        file_channels[channel] = []

    for channel in channels:
        for fileName in files:
            if channel in fileName:
                file_channels[channel].append(fileName)
    return file_channels

@thread_worker
def watch_dir(kwargs={}):
    print(kwargs)
    path = kwargs.get("monitor_dir", "~")
    affine_mat = kwargs.get("affine", None)
    channel_divider = kwargs.get("channel_divider", ["488nm", "560nm"])
    flush_delay = int(kwargs.get("delay_between_frames", 10))
    processed_files = {}
    flush_timer = None
    last_file = {}
    while True:
        files_to_process = {}

        if not processed_files:
            for channel in channel_divider:
                processed_files[channel] = set()
        
        if not files_to_process:
            for channel in channel_divider:
                
                files_to_process[channel] = []

        # Get the all files in the directory at this time
        current_files = set(os.listdir(path))
        # print("current_files 1", current_files)
        # channel separate
        current_files = sort_files_by_channels(current_files, channel_divider)
        # print("current_files 2", current_files)


        if flush_timer:
            if (time.perf_counter() - flush_timer) > flush_delay:
                for channel in channel_divider:
                    if last_file.get(channel, None):
                        if channel in last_file[channel]:
                            # reset the flush timer
                            flush_timer = None
                            yield {
                                "image": os.path.join(path, last_file[channel]), #delayed(imread)(os.path.join(path, last_file[channel])),
                                "channel": channel,
                                "affine": affine_mat
                            }
                            processed_files[channel].update(set(last_file[channel]))
                            last_file = {}
        # print("current_files ",current_files)
        if len(current_files):
            # print("here")
            for channel in channel_divider:
                if len(current_files[channel]):
                    # print("Channel ", channel)
                    # print("files ", current_files[channel])
                    last_file[channel] = sorted(current_files[channel], key=alphanumeric_key)[-1]
                    current_files[channel].remove(last_file[channel])
                    # print("current_files[channel] ", current_files[channel])
                    files_to_process[channel] = list(set(current_files[channel]) - set(processed_files[channel]))
                    # print("files_to_process[channel] ", files_to_process[channel])

        # yield every file to process as a dask.delayed function object.
        # print("Ready to emit ", files_to_process)
        for channel in channel_divider:
            for p in sorted(files_to_process[channel], key=alphanumeric_key):
                    # reset the flush timer
                    # print(channel, p)
                    flush_timer = time.perf_counter()

                    yield  {
                        "image":os.path.join(path, p), #delayed(imread)(os.path.join(path, p)),
                        "channel": channel,
                        "affine": affine_mat
                    }
                    processed_files[channel].add(p)
            else:
                yield {}
        else:
            yield {}

        # add the files which we have yield to the processed list.
        # processed_files.update(files_to_process)
        time.sleep(0.1)