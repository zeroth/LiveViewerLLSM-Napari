import os
import sys
import time
from skimage.io.collection import alphanumeric_key
from napari.qt import thread_worker


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

    while True:
        files_to_process = {}

        if not processed_files:
            for channel in available_channels:
                processed_files[channel] = set()

        if not files_to_process:
            for channel in available_channels:
                files_to_process[channel] = []

        current_files = set(os.listdir(path))
        current_files = sort_files_by_channels(current_files, available_channels)

        if flush_timer:
            # check if the timer has passed the delay_between_frames
            if (time.perf_counter() - flush_timer) > delay_between_frames:
                for channel in available_channels:
                    if last_file.get(channel, None):
                        if channel in last_file[channel]:
                            # reset the flush timer
                            processed_files[channel].update(set([last_file[channel]]))
                            flush_timer = None
                            files = [
                                os.path.join(path, fileName)
                                for fileName in processed_files[channel]
                            ]
                            files = sorted(files, key=alphanumeric_key)

                            yield {
                                "image": files,
                                "channel": channel,
                                "affine": affine_mat,
                                "lut": channel_lut[channel],
                            }
                            last_file[channel] = None

        if len(current_files):
            for channel in available_channels:
                if len(current_files[channel]):
                    last_file[channel] = sorted(
                        current_files[channel], key=alphanumeric_key
                    )[-1]
                    current_files[channel].remove(last_file[channel])
                    files_to_process[channel] = list(
                        set(current_files[channel]) - set(processed_files[channel])
                    )

        # yield all the files so far process to use it with dask.map_blocks.
        for channel in available_channels:
            files_to_display = files_to_process[channel]
            if len(files_to_display):
                # update flush timer
                flush_timer = time.perf_counter()
                processed_files[channel].update(files_to_display)
                files = [
                    os.path.join(path, fileName)
                    for fileName in processed_files[channel]
                ]
                files = sorted(files, key=alphanumeric_key)
                yield {
                    "image": files,
                    "channel": channel,
                    "affine": affine_mat,
                    "lut": channel_lut[channel],
                }
            else:
                yield {}
        else:
            yield {}

        time.sleep(0.1)
