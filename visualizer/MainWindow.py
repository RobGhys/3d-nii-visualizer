import math
import time
import os

import PyQt5.QtWidgets as QtWidgets
import PyQt5.QtCore as Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkUtils import *
from config import *


class MainWindow(QtWidgets.QMainWindow, QtWidgets.QApplication):
    def __init__(self, app):
        self.app = app
        QtWidgets.QMainWindow.__init__(self, None)

        # base setup
        self.renderer, self.frame, self.vtk_widget, self.interactor, self.render_window = self.setup()
        self.brain = setup_brain(self.renderer, self.app.BRAIN_FILE)
        # setup brain projection and slicer
        self.brain_image_prop = setup_projection(self.brain, self.renderer)
        self.brain_slicer_props = setup_slicer(self.renderer, self.brain)  # causing issues with rotation
        self.slicer_widgets = []

        # brain pickers
        self.brain_threshold_sp = self.create_new_picker(self.brain.scalar_range[1], self.brain.scalar_range[0], 5.0,
                                                         sum(self.brain.scalar_range) / 2, self.brain_threshold_vc)
        self.brain_opacity_sp = self.create_new_picker(1.0, 0.0, 0.1, BRAIN_OPACITY, self.brain_opacity_vc)
        self.brain_smoothness_sp = self.create_new_picker(1000, 100, 100, BRAIN_SMOOTHNESS, self.brain_smoothness_vc)
        self.brain_lut_sp = self.create_new_picker(3.0, 0.0, 0.1, 2.0, self.lut_value_changed)
        self.brain_projection_cb = self.add_brain_projection()
        self.brain_slicer_cb = self.add_brain_slicer()

        # create grid for all widgets
        self.grid = QtWidgets.QGridLayout()

        # add each widget
        self.add_vtk_window_widget()
        self.add_brain_settings_widget()
        self.add_views_widget()

        #  set layout and show
        self.render_window.Render()
        self.setWindowTitle(APPLICATION_TITLE)
        self.frame.setLayout(self.grid)
        self.setCentralWidget(self.frame)
        self.set_axial_view()
        self.interactor.Initialize()
        self.show()

    @staticmethod
    def setup():
        """
        Create and setup the base vtk and Qt objects for the application
        """
        renderer = vtk.vtkRenderer()
        frame = QtWidgets.QFrame()
        vtk_widget = QVTKRenderWindowInteractor()
        interactor = vtk_widget.GetRenderWindow().GetInteractor()
        render_window = vtk_widget.GetRenderWindow()

        frame.setAutoFillBackground(True)
        vtk_widget.GetRenderWindow().AddRenderer(renderer)
        render_window.AddRenderer(renderer)
        interactor.SetRenderWindow(render_window)
        interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        # required to enable overlapping actors with opacity < 1.0
        # this is causing some issues with flashing objects
        # render_window.SetAlphaBitPlanes(1)
        # render_window.SetMultiSamples(0)
        # renderer.UseDepthPeelingOn()
        # renderer.SetMaximumNumberOfPeels(2)

        return renderer, frame, vtk_widget, interactor, render_window

    def lut_value_changed(self):
        lut = self.brain.image_mapper.GetLookupTable()
        new_lut_value = self.brain_lut_sp.value()
        lut.SetValueRange(0.0, new_lut_value)
        lut.Build()
        self.brain.image_mapper.SetLookupTable(lut)
        self.brain.image_mapper.Update()
        self.render_window.Render()

    def add_brain_slicer(self):
        slicer_cb = QtWidgets.QCheckBox("Slicer")
        slicer_cb.clicked.connect(self.brain_slicer_vc)
        return slicer_cb

    def add_vtk_window_widget(self):
        base_brain_file = os.path.basename(self.app.BRAIN_FILE)
        object_title = "Brain: {0} (min: {1:.2f}, max: {2:.2f})       ".format(base_brain_file,
                                                                                         self.brain.scalar_range[0],
                                                                                         self.brain.scalar_range[1])
        object_group_box = QtWidgets.QGroupBox(object_title)
        object_layout = QtWidgets.QVBoxLayout()
        object_layout.addWidget(self.vtk_widget)
        object_group_box.setLayout(object_layout)
        self.grid.addWidget(object_group_box, 0, 2, 5, 5)
        # must manually set column width for vtk_widget to maintain height:width ratio
        self.grid.setColumnMinimumWidth(2, 700)

    def add_brain_settings_widget(self):
        brain_group_box = QtWidgets.QGroupBox("Brain Settings")
        brain_group_layout = QtWidgets.QGridLayout()
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Threshold"), 0, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Opacity"), 1, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Brain Smoothness"), 2, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Image Intensity"), 3, 0)
        brain_group_layout.addWidget(self.brain_threshold_sp, 0, 1, 1, 2)
        brain_group_layout.addWidget(self.brain_opacity_sp, 1, 1, 1, 2)
        brain_group_layout.addWidget(self.brain_smoothness_sp, 2, 1, 1, 2)
        brain_group_layout.addWidget(self.brain_lut_sp, 3, 1, 1, 2)
        brain_group_layout.addWidget(self.brain_projection_cb, 4, 0)
        brain_group_layout.addWidget(self.brain_slicer_cb, 4, 1)
        brain_group_layout.addWidget(self.create_new_separator(), 5, 0, 1, 3)
        brain_group_layout.addWidget(QtWidgets.QLabel("Axial Slice"), 6, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Coronal Slice"), 7, 0)
        brain_group_layout.addWidget(QtWidgets.QLabel("Sagittal Slice"), 8, 0)

        # order is important
        slicer_funcs = [self.axial_slice_changed, self.coronal_slice_changed, self.sagittal_slice_changed]
        current_label_row = 6
        # data extent is array [xmin, xmax, ymin, ymax, zmin, zmax)
        # we want all the max values for the range
        extent_index = 5
        for func in slicer_funcs:
            slice_widget = QtWidgets.QSlider(Qt.Qt.Horizontal)
            slice_widget.setDisabled(True)
            self.slicer_widgets.append(slice_widget)
            brain_group_layout.addWidget(slice_widget, current_label_row, 1, 1, 2)
            slice_widget.valueChanged.connect(func)
            slice_widget.setRange(self.brain.extent[extent_index - 1], self.brain.extent[extent_index])
            slice_widget.setValue(round(self.brain.extent[extent_index] / 2))
            current_label_row += 1
            extent_index -= 2

        brain_group_box.setLayout(brain_group_layout)
        self.grid.addWidget(brain_group_box, 0, 0, 1, 2)

    def axial_slice_changed(self):
        pos = self.slicer_widgets[0].value()
        self.brain_slicer_props[0].SetDisplayExtent(self.brain.extent[0], self.brain.extent[1], self.brain.extent[2],
                                                    self.brain.extent[3], pos, pos)
        self.render_window.Render()

    def coronal_slice_changed(self):
        pos = self.slicer_widgets[1].value()
        self.brain_slicer_props[1].SetDisplayExtent(self.brain.extent[0], self.brain.extent[1], pos, pos,
                                                    self.brain.extent[4], self.brain.extent[5])
        self.render_window.Render()

    def sagittal_slice_changed(self):
        pos = self.slicer_widgets[2].value()
        self.brain_slicer_props[2].SetDisplayExtent(pos, pos, self.brain.extent[2], self.brain.extent[3],
                                                    self.brain.extent[4], self.brain.extent[5])
        self.render_window.Render()

    def add_views_widget(self):
        axial_view = QtWidgets.QPushButton("Axial")
        coronal_view = QtWidgets.QPushButton("Coronal")
        sagittal_view = QtWidgets.QPushButton("Sagittal")
        views_box = QtWidgets.QGroupBox("Views")
        views_box_layout = QtWidgets.QVBoxLayout()
        views_box_layout.addWidget(axial_view)
        views_box_layout.addWidget(coronal_view)
        views_box_layout.addWidget(sagittal_view)
        views_box.setLayout(views_box_layout)
        self.grid.addWidget(views_box, 3, 0, 2, 2)
        axial_view.clicked.connect(self.set_axial_view)
        coronal_view.clicked.connect(self.set_coronal_view)
        sagittal_view.clicked.connect(self.set_sagittal_view)

    @staticmethod
    def create_new_picker(max_value, min_value, step, picker_value, value_changed_func):
        if isinstance(max_value, int):
            picker = QtWidgets.QSpinBox()
        else:
            picker = QtWidgets.QDoubleSpinBox()

        picker.setMaximum(max_value)
        picker.setMinimum(min_value)
        picker.setSingleStep(step)
        picker.setValue(picker_value)
        picker.valueChanged.connect(value_changed_func)
        return picker

    def add_brain_projection(self):
        projection_cb = QtWidgets.QCheckBox("Projection")
        projection_cb.clicked.connect(self.brain_projection_vc)
        return projection_cb


    def brain_projection_vc(self):
        projection_checked = self.brain_projection_cb.isChecked()
        self.brain_slicer_cb.setDisabled(projection_checked)  # disable slicer checkbox, cant use both at same time
        self.brain_image_prop.SetOpacity(projection_checked)
        self.render_window.Render()

    def brain_slicer_vc(self):
        slicer_checked = self.brain_slicer_cb.isChecked()

        for widget in self.slicer_widgets:
            widget.setEnabled(slicer_checked)

        self.brain_projection_cb.setDisabled(slicer_checked)  # disable projection checkbox, cant use both at same time
        for prop in self.brain_slicer_props:
            prop.GetProperty().SetOpacity(slicer_checked)
        self.render_window.Render()

    def brain_opacity_vc(self):
        opacity = round(self.brain_opacity_sp.value(), 2)
        self.brain.labels[0].property.SetOpacity(opacity)
        self.render_window.Render()

    def brain_threshold_vc(self):
        self.process_changes()
        threshold = self.brain_threshold_sp.value()
        self.brain.labels[0].extractor.SetValue(0, threshold)
        self.render_window.Render()

    def brain_smoothness_vc(self):
        self.process_changes()
        smoothness = self.brain_smoothness_sp.value()
        self.brain.labels[0].smoother.SetNumberOfIterations(smoothness)
        self.render_window.Render()

    def set_axial_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[0], fp[1], fp[2] + dist)
        self.renderer.GetActiveCamera().SetViewUp(0.0, 1.0, 0.0)
        self.renderer.GetActiveCamera().Zoom(1.8)
        self.render_window.Render()

    def set_coronal_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[0], fp[2] - dist, fp[1])
        self.renderer.GetActiveCamera().SetViewUp(0.0, 0.5, 0.5)
        self.renderer.GetActiveCamera().Zoom(1.8)
        self.render_window.Render()

    def set_sagittal_view(self):
        self.renderer.ResetCamera()
        fp = self.renderer.GetActiveCamera().GetFocalPoint()
        p = self.renderer.GetActiveCamera().GetPosition()
        dist = math.sqrt((p[0] - fp[0]) ** 2 + (p[1] - fp[1]) ** 2 + (p[2] - fp[2]) ** 2)
        self.renderer.GetActiveCamera().SetPosition(fp[2] + dist, fp[0], fp[1])
        self.renderer.GetActiveCamera().SetViewUp(0.0, 0.0, 1.0)
        self.renderer.GetActiveCamera().Zoom(1.6)
        self.render_window.Render()

    @staticmethod
    def create_new_separator():
        horizontal_line = QtWidgets.QWidget()
        horizontal_line.setFixedHeight(1)
        horizontal_line.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        horizontal_line.setStyleSheet("background-color: #c8c8c8;")
        return horizontal_line

    def process_changes(self):
        for _ in range(10):
            self.app.processEvents()
            time.sleep(0.1)
