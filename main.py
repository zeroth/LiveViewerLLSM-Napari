import os
import sys
import time
import numpy as np
from skimage.io.collection import alphanumeric_key
from dask import delayed
import dask.array as da
from tifffile import imread
import napari
from magicgui import magicgui
from pathlib import Path
# from SerialDirectoryWatcher import SerialDirectoryWatcher
import logging
logging.getLogger("tifffile").setLevel(logging.ERROR)

from SerialDirectoryWatcher import watch_dir
worker = None

with napari.gui_qt():
    viewer = napari.Viewer(ndisplay=3)
    
    channel_layers = {}
    def append(data):
        delayed_image = data.get("image", None)
        affine_mat = data.get("affine", None)
        channel = data.get("channel", None)

        if delayed_image is None:
            return

        if (channel in channel_layers) and viewer.layers:
            # layer is present, append to its data
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

            channel_layers[channel] = viewer.add_image(image, affine=affine_mat, name=channel, rendering='attenuated_mip')
            # layer = viewer.add_image(image, scale=scale, shear=shear, rendering='attenuated_mip')

        if len(viewer.layers):
            viewer.dims.set_point(0, 0)
        # if viewer.dims.point[0] >= layer.data.shape[0] - 2:
        #     viewer.dims.set_point(0, layer.data.shape[0] - 1)


    @magicgui ( dx= {"decimals":4 }, dy= {"decimals":4 }, dz= {"decimals":4 },
                angle= {"decimals":4 }, layout="form", monitor_dir={"mode":"D"},
                # running = { "disabled": True },
                call_button="Start/Update" )
    def deskew_settings(angle: float = 31.8, dx: float = 0.104, 
                        dy: float = 0.104, dz: float= 0.4, 
                        time_point_divider: str = "T_", 
                        channel_divider: str = "488nm, 560nm", monitor_dir=Path("~"),
                        # running: bool = False
                        ):
        
        dz_tan = np.tan(np.deg2rad(90-angle))
        dz_sin = np.sin(np.deg2rad(angle))* dz
        shear = np.array([
                [ 1.,      0.,  0.,  0., 0.],
                [ 0.,      1.,  0.,  0., 0.],
                [ 0.,      0.,  1.,  0., 0.],
                [ 0.,  dz_tan,  0.,  1., 0.],
                [ 0,       0.,  0.,  0., 1.]])

        scale = np.array([
                [ 1., 0.,     0.,   0.,  0.],
                [ 0., dz_sin, 0.,   0.,  0.],
                [ 0., 0.,     dy,   0.,  0.],
                [ 0., 0.,     0.,   dx,  0.],
                [ 0., 0.,     0.,   0.,  1.]])

        global_affine =shear @ scale
        channel_divider_list = [ i.strip() for i in channel_divider.split(",")]
        return {"monitor_dir": monitor_dir, "affine": global_affine, 
                "time_point_divider": time_point_divider, 
                "channel_divider": channel_divider_list }
    
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
            # worker.stop()
            del worker
            
            viewer.layers.select_all()
            viewer.layers.remove_selected()
            channel_layers.clear()
            worker = watch_dir(args)
            worker.yielded.connect(append)
            worker.start()
        
    
    deskew_settings_widget.called.connect(start_monitoring)
    viewer.window.add_dock_widget(deskew_settings_widget, 
                                name="Start Live Deskew", area='right')
    

    
        