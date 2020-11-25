import os
import sys
import time
import numpy as np
import napari
from skimage.io.collection import alphanumeric_key
import dask.array as da
from dask import delayed
from tifffile import imread
from magicgui import magicgui
from pathlib import Path
from serial_directory_watcher import watch_dir
from serial_directory_watcher_2 import SerailDirectoryWatcher, SerailDirectoryWatcherSignal
from ui.main_widget import LLSMWidget

# disable tifffile warnings
import logging

logging.getLogger("tifffile").setLevel(logging.ERROR)


def get_affine(
    angle: float = 31.8,
    dx: float = 0.104,
    dy: float = 0.104,
    dz: float = 0.4,
    already_deskew: bool = False,
):
    """
    This function returns the affine matrix based on the LLSM configuration.

    Parameters
    -----------
    angle: LSSM acqusition in degree, defaults = 31.8.
    dx: X pixel size, default = 0.104.
    dy: Y pixel size, default = 0.104.
    dz: Z step size, default = 0.4.
    already_deskew: if True this function will not calculate shear, default = False
    """
    dz_tan = np.tan(np.deg2rad(90 - angle))
    dz_sin = np.sin(np.deg2rad(angle)) * dz
    shear = np.eye(5)
    if not already_deskew:
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

    return shear @ scale


# Dask array helper function
def read_one_timepoint(fname_array, block_id):
    # block_id will be something like (t, 0, 0, 0)
    
    file_num = block_id[0]
    filename = fname_array[file_num]
    print("read_one_timepoint: ", filename)
    single_timepoint = imread(filename)
    reshaped_to_chunk_shape = single_timepoint[np.newaxis, :, :, :]
    # return the chunk that map_blocks expects
    return reshaped_to_chunk_shape


# Dask array helper function
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
    # main napari loop
    viewer = napari.Viewer(ndisplay=3)

    channel_layers = {}

    def append(data):
        # function which appends data sent by serial_directory_watcher to napari
        if not data:
            return

        is_init = data.get("init", False)

        if is_init:
            init_data = data.get("data", {})
            for channel, _data in init_data.items():
                _files = _data.get("image", [])
                _affine_mat = _data.get("affine", None)
                _lut = _data.get("lut", "bop purple")

                image0 = imread(_files[0])
                image_dtype = image0.dtype
                image_shape = image0.shape
                image = delayed_multi_imread(
                    np.asarray(_files), image_shape, image_dtype
                )

                channel_layers[channel] = viewer.add_image(
                    image,
                    affine=_affine_mat,
                    name=channel,
                    rendering="mip",
                    blending="additive",
                    colormap=_lut,
                )

        delayed_image = data.get("image", None)
        affine_mat = data.get("affine", None)
        channel = data.get("channel", None)
        lut = data.get("lut", "bop purple")

        if delayed_image is None:
            return

        delayed_image = delayed(imread)(delayed_image)
        if (channel in channel_layers) and viewer.layers:
            layer = channel_layers[channel]

            image_shape = layer.data.shape[1:]
            image_dtype = layer.data.dtype
            image = da.from_delayed(
                delayed_image, shape=image_shape, dtype=image_dtype,
            ).reshape((1,) + image_shape)
            layer.data = da.concatenate((layer.data, image), axis=0)

            layer.affine = affine_mat
        else:
            # first run, no layer added yet
            image = delayed_image.compute()
            image = da.from_delayed(
                delayed_image, shape=image.shape, dtype=image.dtype,
            ).reshape((1,) + image.shape)

            channel_layers[channel] = viewer.add_image(
                image,
                name=channel,
                affine=affine_mat,
                rendering="mip",
                blending="additive",
                colormap=lut,
            )

        if viewer.dims.point[0] >= channel_layers[channel].data.shape[0] - 2:
            viewer.dims.set_point(0, channel_layers[channel].data.shape[0] - 1)

    deskew_settings_widget = LLSMWidget()

    # function to start the monitoring
    def start_monitoring(args):
        global worker
        global deskew_settings_widget

        angle = args['angle']
        dx = args['dx']
        dy = args['dy']
        dz = args['dz']
        already_deskew = args['already_deskewed']
        delay_between_frames = args['delay_between_frames']
        channel_divider_list = [i.strip() for i in args['channel_divider'].split(",")]
        monitor_dir = args['monitor_dir']

        global_affine = get_affine( 
            angle=angle, dx=dx, dy=dy, dz=dz, already_deskew=already_deskew)

        
        deskew_config =  {
            "monitor_dir": monitor_dir,
            "affine": global_affine,
            "delay_between_frames": delay_between_frames,
            "channel_divider": channel_divider_list,
        }

        if not worker:
            print("started")
            worker = watch_dir(deskew_config)
            # worker = SerailDirectoryWatcher(kwargs=deskew_config)
            worker.yielded.connect(append)
            worker.yielded.connect(deskew_settings_widget.update_bleach_chart)
            worker.start()
            # worker.finished.connect(worker.deleteLater)
        else:
            print("re-started")
            worker.quit()
            del worker

            viewer.layers.select_all()
            viewer.layers.remove_selected()
            channel_layers.clear()
            worker = watch_dir(deskew_config)
            # worker = SerailDirectoryWatcher(kwargs=deskew_config)
            worker.yielded.connect(append)
            worker.yielded.connect(deskew_settings_widget.update_bleach_chart)
            worker.start()
            # worker.finished.connect(worker.deleteLater)

    # viewer.window.qt_viewer

    deskew_settings_widget.start_deskew.connect(start_monitoring)
    viewer.window.add_dock_widget(
        deskew_settings_widget, name="Start Live Deskew", area="right"
    )


#####################################
# magicgui function which creates the dock widget
# @magicgui(
#     dx={"decimals": 4},
#     dy={"decimals": 4},
#     dz={"decimals": 4},
#     angle={"decimals": 4},
#     monitor_dir={"mode": "D"},
#     layout="form",
#     call_button="Start/Update",
# )
# def deskew_settings(
#     angle: float = 31.8,
#     dx: float = 0.104,
#     dy: float = 0.104,
#     dz: float = 0.4,
#     already_deskew: bool = False,
#     delay_between_frames: int = 10,
#     channel_divider: str = "488nm, 560nm",
#     monitor_dir=Path("~"),
# ):

#     global_affine = get_affine(
#         angle=angle, dx=dx, dy=dy, dz=dz, already_deskew=already_deskew
#     )

#     channel_divider_list = [i.strip() for i in channel_divider.split(",")]
#     return {
#         "monitor_dir": monitor_dir,
#         "affine": global_affine,
#         "delay_between_frames": delay_between_frames,
#         "channel_divider": channel_divider_list,
#     }