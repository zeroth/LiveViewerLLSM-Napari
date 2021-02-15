import os
import sys
import time
from skimage.io.collection import alphanumeric_key
from napari.qt.threading import WorkerBase, WorkerBaseSignals
from glob import glob
import dask.array as da
from typing import Type
from qtpy.QtCore import Signal


def sort_files_by_channels(dir_path, channels: list):
    """
    dir_path: the monitoring directory which we want to scan for files
    channels: identifier list on which we want to divide the files in dir_path
    """
    file_channels = {}
    for channel in channels:
        _files = sorted(
            glob(os.path.join(dir_path, "*{0}*".format(channel))), key=alphanumeric_key
        )
        if len(_files):
            file_channels[channel] = _files
    return file_channels


def create_init_chunk(init_file_dict, lut_dict, affine_mat):
    # simple helper function to create the initial chuck we want to display
    init_chunk = {}
    for channel, files in init_file_dict.items():
        init_chunk[channel] = {
            "image": files,
            "affine": affine_mat,
            "lut": lut_dict[channel],
        }
    return init_chunk

class SerailDirectoryWatcherSignal(WorkerBaseSignals):
    finished_acq = Signal()
    yielded = Signal(object)

class SerailDirectoryWatcher(WorkerBase):
    def __init__(self, 
    SignalsClass: Type[WorkerBaseSignals] = SerailDirectoryWatcherSignal,
    kwargs={}):
        super().__init__(SignalsClass=SignalsClass)
        self.kwargs = kwargs

    def __getattr__(self, name):
        # the Signal object is actually a class attribute
        print(name)
        attr = getattr(self.signals.__class__, name, None)
        if isinstance(attr, Signal):
            # but what we need to connect to is the instantiated signal
            # (which is of type `SignalInstance` in PySide and
            # `pyqtBoundSignal` in PyQt)
            return getattr(self.signals, name)
        return super().__getattr__(name)
        
    def work(self):
        """
        The thread which monitors the directory for changes

        Parameters
        ----------
        kwargs['monitor_dir'] : directory to monitor
        kwargs["affine"] : affine matrix to associate with each file
        kwargs["channel_divider"]: list of channel identifies to separate the file on
        kwargs["delay_between_frames"]: Generally the acquisition delay between two-time points
        mainly used for determining if the last file in the dir has completely written.

        """
        path = self.kwargs.get("monitor_dir", "~")
        affine_mat = self.kwargs.get("affine", None)
        available_channels = self.kwargs.get("channel_divider", ["*"])
        delay_between_frames = int(self.kwargs.get("delay_between_frames", 10))
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

        if initial_files:
            self.yielded.emit( {
                "init": True,
                "data": create_init_chunk(initial_files, channel_lut, affine_mat),
            })
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
                # if yes then last file has completely written, send it.
                if (time.perf_counter() - flush_timer) > delay_between_frames:
                    for channel in available_channels:
                        if last_file.get(channel, None):
                            if channel in last_file[channel]:
                                # reset the flush timer
                                flush_timer = None
                                self.yielded.emit( {
                                    "init": False,
                                    "image": last_file[channel],
                                    "channel": channel,
                                    "affine": affine_mat,
                                    "lut": channel_lut[channel],
                                })
                                processed_files[channel].update(set(last_file[channel]))
                                last_file[channel] = None
                                self.finished_acq.emit()

            # Get the currect files from the direct
            # detemine which we want to process
            # remove the last one
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

            # yield one file at a time from `files_to_process`
            for channel in available_channels:
                for p in sorted(files_to_process.get(channel, []), key=alphanumeric_key):
                    # update the flush timer
                    flush_timer = time.perf_counter()
                    self.yielded.emit({
                        "init": False,
                        "image": p,
                        "channel": channel,
                        "affine": affine_mat,
                        "lut": channel_lut[channel],
                    })
                    processed_files[channel].add(p)
                else:
                    self.yielded.emit({})
            else:
                self.yielded.emit({})

            # breathe
            time.sleep(delay_between_frames/2)
