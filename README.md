# LiveViewerLLSM-Napari
LiveViewerLLSM is the simple live viewer for Lattice Light-sheet data using Napari visualiser.
It monitors the acquisition directory and applies the shear and scales to the volumes flowing in, and this helps us visualise the data without going throw the deskew process.

<img
src="docs/assets/images/napari_live_llsm.gif"
raw=true
alt="LLSM live deskew"
/>
# Install

Download this repository

You can clone this repository
```
git clone https://github.com/zeroth/LiveViewerLLSM-Napari.git
```
Or download the zip [here](https://github.com/zeroth/LiveViewerLLSM-Napari/archive/main.zip)

```
cd LiveViewerLLSM-Napari
pip install -r requirements.txt
python main.py
```


