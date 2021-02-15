from qtpy.QtCore import QDateTime, Qt, Signal
from qtpy.QtGui import QPainter

from qtpy.QtWidgets import (QHBoxLayout, QFormLayout, QLineEdit,
                                QSizePolicy, QSpinBox, QCheckBox, QDoubleSpinBox,
                                QTableView, QPushButton, QWidget)

# from table_model import CustomTableModel
from qtpy.QtCharts import QtCharts

from .file_type_widget import FileTypeDialog, FilesTypeDialog, DirectoryTypeDialog
import json
import os


def get_config(file_name: str = "config.json"):
    file_path = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), file_name)
    config = None
    with open(file_path, 'r') as f:
        raw = "".join(f.readlines())
        config = json.loads(raw)

    return config


class DeskewWidget(QWidget):
    start_clicked = Signal(dict)

    def __init__(self):
        QWidget.__init__(self)
        # QWidget Layout
        self.main_layout = QFormLayout()
        self.child_widget = {
            #"name" : [w, "name of the method"]
        }

        config = get_config()

        for k, v in config.items():
            w = QDoubleSpinBox()
            if v["dtype"] in ['float', 'int', 'double']:
                if v.get("range"):
                    w.setRange(v["range"][0], v["range"][1])
                else:
                    w.setRange(0, 100)
                w.setDecimals(4)
                w.setValue(v["default"])
                self.child_widget[k]= [w, "value"]

            elif v["dtype"] in ["bool"]:
                w = QCheckBox()
                w.setChecked(v["default"])
                self.child_widget[k]= [w, "isChecked"]

            elif v["dtype"] in ["file"]:
                w = FileTypeDialog()
                w.setValue(v["default"])
                self.child_widget[k]= [w, "value"]

            elif v["dtype"] in ["files"]:
                w = FilesTypeDialog()
                w.setValue(v["default"])
                self.child_widget[k]= [w, "value"]

            elif v["dtype"] in ["dir"]:
                w = DirectoryTypeDialog()
                w.set_path(v["default"])
                self.child_widget[k]= [w, "get_path"]
            else:
                w = QLineEdit()
                w.setText(v["default"])
                self.child_widget[k]= [w, "text"]
            self.main_layout.addRow(k, w)
            

        self.btn = QPushButton("start")
        self.btn.clicked.connect(self.button_click)

        self.main_layout.addWidget(self.btn)

        # Set the layout to the QWidget
        self.setLayout(self.main_layout)
    
    def button_click(self):
        data= {}
        for k, v in self.child_widget.items():
            data[k] = getattr(v[0], v[1])()
        self.start_clicked.emit(data)
