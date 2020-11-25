from qtpy.QtCore import QDateTime, Qt, Signal, Slot
from qtpy.QtGui import QPainter
from glob import glob
import os
from skimage.io.collection import alphanumeric_key
from qtpy.QtWidgets import (QVBoxLayout, QFormLayout, 
                            QLineEdit, QSizePolicy,
                            QSpinBox, QPushButton,
                            QTableView, QWidget)

from qtpy.QtCharts import QtCharts

from .deskew_widget import DeskewWidget
from tifffile import imread
import numpy as np


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


class LLSMWidget(QWidget):

    start_deskew = Signal(dict)

    def __init__(self):
        QWidget.__init__(self)

        self.series = {}
        self.axis_x = None
        self.axis_y = None
        self.config = None
        # Creating QChart
        self.chart = QtCharts.QChart()
        self.chart.setAnimationOptions(QtCharts.QChart.AllAnimations)
        # Creating QChartView
        self.chart_view = QtCharts.QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        # self.add_series("Magnitude (Column 1)", [0, 1])

        self.deskew_widget = DeskewWidget()
        self.deskew_widget.start_clicked.connect(self.emit_signal)

        # QWidget Layout
        self.main_layout = QVBoxLayout()
        size = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Top Layout
        self.main_layout.addWidget(self.deskew_widget)

        # Bottom Layout
#        size.setHorizontalStretch(4)
        self.chart_view.setSizePolicy(size)
        self.main_layout.addWidget(self.chart_view)

        self.main_layout.addWidget(QPushButton("Deskew"))
        self.main_layout.addWidget(QPushButton("Deskew & Decon"))
        self.main_layout.addWidget(QPushButton(
            "Bleach Correct & Deskew & Decon"))

        # Set the layout to the QWidget
        self.setLayout(self.main_layout)

    def emit_signal(self, data):
        self.config = data
        self.start_deskew.emit(data)

    @Slot()
    def create_chart(self):
        path = self.kwargs.get("monitor_dir", "~")
        available_channels = self.kwargs.get("channel_divider", ["*"])
        # channel_lut = {}
        # for index, channel in enumerate(available_channels):
        #     channel_lut[channel] = color_maps[index % len(color_maps)]

        processed_files = {}

        if not processed_files:
            for channel in available_channels:
                processed_files[channel] = set()

        initial_files = sort_files_by_channels(path, available_channels)

        ## all files
        for channel, _files in initial_files.items():
            for _file in _files:
                _max = np.amax(imread(_file))
                self.add_to_chart({'channel': channel, 'max': _max})
        
        for channel, _series in self.series.items():
            if _series not in self.chart.series():
                print("adding series ", channel)
                self.chart.addSeries(_series)

        # Setting X-axis
        if not self.axis_x and not self.axis_y:
            self.axis_x = QtCharts.QValueAxis()
            # self.axis_x.setTickCount(1)
            self.axis_x.setTitleText("Time")
            self.chart.addAxis(self.axis_x, Qt.AlignBottom)

            self.axis_y = QtCharts.QValueAxis()
            # self.axis_y.setTickCount(1)
            self.axis_y.setTitleText("Max Intensity")
            self.chart.addAxis(self.axis_y, Qt.AlignLeft)

            # attach to only one series
            for _channel, _series in self.series.items():
                _series.attachAxis(self.axis_x)
                _series.attachAxis(self.axis_y)
                break

    @Slot(dict)
    def update_bleach_chart(self, data):

        if not data:
            return

        is_finish = data.get("finish", False)

        if not is_finish:
            return
        
        monito_dir = self.config['monitor_dir']
        channel_divider_list = [i.strip() for i in self.config['channel_divider'].split(",")]
        initial_files = sort_files_by_channels(monito_dir, channel_divider_list)

        ## all files
        for channel, _files in initial_files.items():
            for _file in _files:
                _max = np.mean(imread(_file))
                self.add_to_chart({'channel': channel, 'max': _max})

        for channel, _series in self.series.items():
            if _series not in self.chart.series():
                print("adding series ", channel)
                self.chart.addSeries(_series)

        for channel, _series in self.series.items():
            if _series not in self.chart.series():
                print("adding series ", channel)
                self.chart.addSeries(_series)

        # Setting X-axis
        if not self.axis_x and not self.axis_y:
            self.axis_x = QtCharts.QValueAxis()
            # self.axis_x.setTickCount(1)
            self.axis_x.setTitleText("Time")
            self.chart.addAxis(self.axis_x, Qt.AlignBottom)

            self.axis_y = QtCharts.QValueAxis()
            # self.axis_y.setTickCount(1)
            self.axis_y.setTitleText("Max Intensity")
            self.chart.addAxis(self.axis_y, Qt.AlignLeft)

            # attach to only one series
            for _channel, _series in self.series.items():
                _series.attachAxis(self.axis_x)
                _series.attachAxis(self.axis_y)
                break
    
    def add_to_chart(self, data):
        print("add_to_chart", data)
        channel = data['channel']
        _max = data['max']
        if not self.series.get(channel):
            print("creating series", channel)
            self.series[channel] = QtCharts.QLineSeries()
            self.series[channel].setName(channel)

        self.series[channel].append(self.series[channel].count(), _max)
        self.chart.update()

        if self.series[channel] in self.chart.series():
            self.chart.removeSeries(self.series[channel])
            self.chart.addSeries(self.series[channel])
