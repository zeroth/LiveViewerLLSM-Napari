from enum import Enum

import numpy as np
from napari import Viewer, gui_qt
from napari.layers import Image
from numpy import savetxt
from magicgui import magicgui
from skimage.filters import threshold_otsu

from sklearn import preprocessing

preprocessing.normalize

is_normalized = True
def otsu(image):
    # Set total number of bins in the histogram
    bins_num = 256

    # out image has lots of "0" due to deskew this is a small hack to find the actual min of the image
    sorted_img = np.sort(np.unique(image.flatten()))
    img_min = sorted_img[0] #if sorted_img[0]> 0 else sorted_img[1]

    # Get the image histogram
    hist, bin_edges = np.histogram(image, bins=bins_num, range=(img_min, np.max(image)))

    # Get normalized histogram if it is required
    if is_normalized:
        hist = np.divide(hist.ravel(), hist.max())

    # Calculate centers of bins
    bin_mids = (bin_edges[:-1] + bin_edges[1:]) / 2.

    # Iterate over all thresholds (indices) and get the probabilities w1(t), w2(t)
    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]

    # Get the class means mu0(t)
    mean1 = np.cumsum(hist * bin_mids) / weight1
    # Get the class means mu1(t)
    mean2 = (np.cumsum((hist * bin_mids)[::-1]) / weight2[::-1])[::-1]

    inter_class_variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2

    # Maximize the inter_class_variance function val
    index_of_max_val = np.argmax(inter_class_variance)

    threshold = bin_mids[:-1][index_of_max_val]
    # print("Otsu's algorithm implementation thresholding result: ", threshold)
    return threshold

with gui_qt():
    # create a viewer and add a couple image layers
    viewer = Viewer()
    # Set total number of bins in the histogram
    bins_num = 256

    # use the magic decorator!  This takes a function, and generates a widget instance
    # using the function signature.
    @magicgui(call_button="execute")
    def image_arithmetic() -> Image:

        img = np.asarray(viewer.active_layer.data, dtype=np.float)
        thresh = otsu(img)
        # print("thresh :", thresh)
        data = img[img >= thresh]
        avg = np.mean(data)
        result = (data - avg)/avg
        n_img =  np.asarray(img,dtype=np.float)
        n_img[n_img < thresh] = 0
        n_img[n_img >= thresh] = result
        #savetxt(viewer.active_layer.name+'_data.csv', data, delimiter=',')
        return result
        # return operation.value(layerA.data, layerB.data)

    # add our new magicgui widget to the viewer
    viewer.window.add_dock_widget(image_arithmetic.Gui())
