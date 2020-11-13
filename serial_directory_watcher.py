import os
import sys
import time
from skimage.io.collection import alphanumeric_key
from napari.qt import thread_worker
from glob import glob
from dask import delayed
import dask.array as da
from tifffile import imread


def sort_files_by_channels(files, channels):
    file_channels = {}
    for channel in channels:
        _files = sorted(
            glob(os.path.join(files, "*{0}*".format(channel))), key=alphanumeric_key
        )
        if len(_files):
            file_channels[channel] = _files
    return file_channels


def create_init_chunk(init_file_dict, lut_dict, affine_mat):
    init_chunk = {}
    for channel, files in init_file_dict.items():
        init_chunk[channel] = {
            "image": files,
            "affine": affine_mat,
            "lut": lut_dict[channel],
        }
    return init_chunk


@thread_worker
def watch_dir(kwargs={}):
    path = kwargs.get("monitor_dir", "~")
    affine_mat = kwargs.get("affine", None)
    available_channels = kwargs.get("channel_divider", ["488nm", "560nm"])
    delay_between_frames = int(kwargs.get("delay_between_frames", 10))
    color_maps = ["bop purple", "bop orange", "bop blue", "green", "blue"]

    channel_lut = {}
    for index, channel in enumerate(available_channels):
        channel_lut[channel] = color_maps[index % len(color_maps)]

    processed_files = {}
    last_file = {}
    flush_timer = None

    if not processed_files:
        for channel in available_channels:
            processed_files[channel] = set()

    initial_files = sort_files_by_channels(path, available_channels)

    print()
    if initial_files:
        yield {
            "init": True,
            "data": create_init_chunk(initial_files, channel_lut, affine_mat),
        }
        for channel, files in initial_files.items():
            processed_files[channel].update(files)

    while True:
        files_to_process = {}

        if not files_to_process:
            for channel in available_channels:
                files_to_process[channel] = []

        current_files = sort_files_by_channels(path, available_channels)

        if flush_timer:
            # check if the timer has passed the delay_between_frames
            if (time.perf_counter() - flush_timer) > delay_between_frames:
                for channel in available_channels:
                    if last_file.get(channel, None):
                        if channel in last_file[channel]:
                            # reset the flush timer
                            flush_timer = None
                            yield {
                                "init": False,
                                "image": delayed(imread)(last_file[channel]),
                                "channel": channel,
                                "affine": affine_mat,
                                "lut": channel_lut[channel],
                            }
                            processed_files[channel].update(set(last_file[channel]))
                            last_file[channel] = None

        if len(current_files):
            for channel in available_channels:
                if len(current_files.get(channel, [])):
                    last_file[channel] = sorted(
                        current_files[channel], key=alphanumeric_key
                    )[-1]
                    current_files[channel].remove(last_file[channel])
                    files_to_process[channel] = list(
                        set(current_files[channel]) - set(processed_files[channel])
                    )

        # yield all the files so far process to use it with dask.map_blocks.
        for channel in available_channels:
            for p in sorted(files_to_process.get(channel, []), key=alphanumeric_key):
                # update the flush timer
                flush_timer = time.perf_counter()
                yield {
                    "init": False,
                    "image": delayed(imread)(p),
                    "channel": channel,
                    "affine": affine_mat,
                    "lut": channel_lut[channel],
                }
                processed_files[channel].add(p)
            else:
                yield {}
        else:
            yield {}

        time.sleep(0.1)
