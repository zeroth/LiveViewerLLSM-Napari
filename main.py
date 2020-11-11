import os
import sys
import time
import numpy as np
import napari
from skimage.io.collection import alphanumeric_key
import dask.array as da
from tifffile import imread
from magicgui import magicgui
from pathlib import Path
from SerialDirectoryWatcher import watch_dir

# disable tifffile warnings
import logging

logging.getLogger("tifffile").setLevel(logging.ERROR)


def read_one_timepoint(fname_array, block_id):
    # block_id will be something like (t, 0, 0, 0)
    file_num = block_id[0]
    filename = fname_array[file_num]
    single_timepoint = imread(filename)
    reshaped_to_chunk_shape = single_timepoint[np.newaxis, :, :, :]
    # return the chunk that map_blocks expects
    return reshaped_to_chunk_shape


def delayed_multi_imread(fname_array, image_shape, image_dtype):
    nt = fname_array.shape[0]
    nz, ny, nx = image_shape
    image = da.map_blocks(
        read_one_timepoint,
        fname_array,
        # shape of one chunk = (1, nz, ny, nx)
        # all chunks together: ((1, 1, 1, 1, ...), )
        chunks=((1,) * nt, (nz,), (ny,), (nx,)),
        dtype=image_dtype,
    )
    return image


worker = None


with napari.gui_qt():
    viewer = napari.Viewer(ndisplay=3)

    channel_layers = {}

    def append(data):

        all_filenames = np.asarray(data.get("image", []))
        if len(all_filenames) == 0:
            return
        affine_mat = data.get("affine", None)
        channel = data.get("channel", None)
        lut = data.get("lut", "bop purple")

        if (channel in channel_layers) and viewer.layers:
            # layer is present, append to its data
            layer = channel_layers[channel]

            if len(all_filenames) == layer.data.shape[0]:
                return

            image_shape = layer.data.shape[1:]
            image_dtype = layer.data.dtype

            layer.data = delayed_multi_imread(all_filenames, image_shape, image_dtype)
            layer.affine = affine_mat
        else:
            # first run, no layer added yet
            image0 = imread(all_filenames[0])
            image_dtype = image0.dtype
            image_shape = image0.shape
            image = delayed_multi_imread(all_filenames, image_shape, image_dtype)
            channel_layers[channel] = viewer.add_image(
                image,
                affine=affine_mat,
                name=channel,
                rendering="mip",
                blending="additive",
                colormap=lut,
            )

        if len(viewer.layers):
            viewer.dims.set_point(0, 0)

        # if viewer.dims.point[0] >= layer.data.shape[0] - 2:
        #     viewer.dims.set_point(0, layer.data.shape[0] - 1)

    @magicgui(
        dx={"decimals": 4},
        dy={"decimals": 4},
        dz={"decimals": 4},
        angle={"decimals": 4},
        monitor_dir={"mode": "D"},
        layout="form",
        call_button="Start/Update"
    )
    def deskew_settings(
        angle: float = 31.8,
        dx: float = 0.104,
        dy: float = 0.104,
        dz: float = 0.4,
        delay_between_frames: int = 10,
        channel_divider: str = "488nm, 560nm",
        monitor_dir=Path("~")
    ):

        dz_tan = np.tan(np.deg2rad(90 - angle))
        dz_sin = np.sin(np.deg2rad(angle)) * dz
        shear = np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0, 0.0],
                [0.0, dz_tan, 0.0, 1.0, 0.0],
                [0, 0.0, 0.0, 0.0, 1.0],
            ]
        )

        scale = np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, dz_sin, 0.0, 0.0, 0.0],
                [0.0, 0.0, dy, 0.0, 0.0],
                [0.0, 0.0, 0.0, dx, 0.0],
                [0.0, 0.0, 0.0, 0.0, 1.0],
            ]
        )

        global_affine = shear @ scale
        channel_divider_list = [i.strip() for i in channel_divider.split(",")]
        return {
            "monitor_dir": monitor_dir,
            "affine": global_affine,
            "delay_between_frames": delay_between_frames,
            "channel_divider": channel_divider_list,
        }

    deskew_settings_widget = deskew_settings.Gui()

    def start_monitoring(args):
        global worker
        if not worker:
            print("started")
            worker = watch_dir(args)
            worker.yielded.connect(append)
            worker.start()
        else:
            print("re-started")
            worker.quit()
            del worker

            viewer.layers.select_all()
            viewer.layers.remove_selected()
            channel_layers.clear()
            worker = watch_dir(args)
            worker.yielded.connect(append)
            worker.start()

    deskew_settings_widget.called.connect(start_monitoring)
    viewer.window.add_dock_widget(
        deskew_settings_widget, name="Start Live Deskew", area="right"
    )
