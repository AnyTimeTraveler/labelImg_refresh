#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import codecs
import os
import platform
import shutil
import webbrowser as wb
from functools import partial

from libs.combobox import ComboBox
from libs.default_label_combobox import DefaultLabelComboBox
from libs.constants import *
from libs.structs import Actions, Menus
from libs.utils import *
from libs.settings import Settings
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.stringBundle import StringBundle
from libs.canvas import Canvas
from libs.zoomWidget import ZoomWidget
from libs.lightWidget import LightWidget
from libs.labelDialog import LabelDialog
from libs.colorDialog import ColorDialog
from libs.labelFile import LabelFile, LabelFileError, LabelFileFormat
from libs.toolBar import ToolBar
from libs.pascal_voc_io import PascalVocReader
from libs.pascal_voc_io import XML_EXT
from libs.yolo_io import YoloReader
from libs.yolo_io import TXT_EXT
from libs.create_ml_io import CreateMLReader
from libs.create_ml_io import JSON_EXT
from libs.ustr import ustr
from libs.hashableQListWidgetItem import HashableQListWidgetItem
from libs.auto_annotate import YOLOAutoAnnotator

__appname__ = "labelImg Refresh"


class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            add_actions(menu, actions)
        return menu

    def toolbar(self, title, actions=None) -> ToolBar:
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            add_actions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = list(range(3))

    def __init__(
            self,
            default_filename=None,
            default_prefdef_class_file=None,
            default_label_dir=None,
    ):
        super(MainWindow, self).__init__()
        self.image_data = None
        self.label_file = None
        self.label_file_path = None
        self.setWindowTitle(__appname__)

        # Load setting in the main thread
        self.settings = Settings()
        self.settings.load()
        settings = self.settings

        self.os_name = platform.system()

        # Load string bundle for i18n

        # This import is needed to load builtin resources
        import libs.resources
        self.string_bundle = StringBundle.get_bundle()

        self.default_label_dir = default_label_dir
        self.label_file_format = settings.get(SETTING_LABEL_FILE_FORMAT, LabelFileFormat.PASCAL_VOC)

        # For loading all image under a directory
        self.m_img_list = []
        self.dir_name = None
        self.label_hist = []
        self.last_open_dir = None
        self.cur_img_idx = 0
        self.img_count = len(self.m_img_list)

        # Whether we need to save or not.
        self.dirty = False

        self._no_selection_slot = False
        self._advanced_mode = False
        self.screencast = "https://youtu.be/p0nR2YsCY_U"

        # Load predefined classes to the list
        self.load_predefined_classes(default_prefdef_class_file)
        self.default_prefdef_class_file = default_prefdef_class_file

        if self.label_hist:
            self.default_label = self.label_hist[0]
        else:
            print("Not find:/data/predefined_classes.txt (optional)")

        # Main widgets and related state.
        self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)

        self.items_to_shapes = {}
        self.shapes_to_items = {}
        self.prev_label_text = ""

        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(0, 0, 0, 0)

        # Create a widget for using default label
        self.use_default_label_checkbox = QCheckBox(self.get_str("useDefaultLabel"))
        self.use_default_label_checkbox.setChecked(False)
        self.default_label_combo_box = DefaultLabelComboBox(self, items=self.label_hist)

        use_default_label_qhbox_layout = QHBoxLayout()
        use_default_label_qhbox_layout.addWidget(self.use_default_label_checkbox)
        use_default_label_qhbox_layout.addWidget(self.default_label_combo_box)
        use_default_label_container = QWidget()
        use_default_label_container.setLayout(use_default_label_qhbox_layout)

        # Create a widget for edit and diffc button
        self.diffc_button = QCheckBox(self.get_str("useDifficult"))
        self.diffc_button.setChecked(False)
        self.diffc_button.stateChanged.connect(self.button_state)
        self.edit_button = QToolButton()
        self.edit_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Add some of widgets to list_layout
        list_layout.addWidget(self.edit_button)
        list_layout.addWidget(self.diffc_button)
        list_layout.addWidget(use_default_label_container)

        # Create and add combobox for showing unique labels in group
        self.combo_box = ComboBox(self)
        list_layout.addWidget(self.combo_box)

        # Create and add a widget for showing current label items
        self.label_list = QListWidget()
        label_list_container = QWidget()
        label_list_container.setLayout(list_layout)
        self.label_list.itemActivated.connect(self.label_selection_changed)
        self.label_list.itemSelectionChanged.connect(self.label_selection_changed)
        self.label_list.itemDoubleClicked.connect(self.edit_label)
        # Connect to itemChanged to detect checkbox changes.
        self.label_list.itemChanged.connect(self.label_item_changed)
        list_layout.addWidget(self.label_list)

        self.dock = QDockWidget(self.get_str("boxLabelText"), self)
        self.dock.setObjectName(self.get_str("labels"))
        self.dock.setWidget(label_list_container)

        # Text field to find images by index
        self.idx_text_box = QLineEdit()
        self.jump_button = QPushButton("Show image by Index", self)
        self.jump_button.clicked.connect(self.jump_on_click)

        self.file_list_widget = QListWidget()
        self.file_list_widget.itemSelectionChanged.connect(self.file_item_selected)
        file_list_layout = QVBoxLayout()
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.addWidget(self.idx_text_box)
        file_list_layout.addWidget(self.jump_button)
        file_list_layout.addWidget(self.file_list_widget)
        file_list_container = QWidget()
        file_list_container.setLayout(file_list_layout)
        self.file_dock = QDockWidget(self.get_str("fileList"), self)
        self.file_dock.setObjectName(self.get_str("files"))
        self.file_dock.setWidget(file_list_container)

        self.zoom_widget = ZoomWidget()
        self.light_widget = LightWidget(self.get_str("lightWidgetTitle"))
        self.color_dialog = ColorDialog(parent=self)

        self.canvas = Canvas(parent=self)
        self.canvas.zoomRequest.connect(self.zoom_request)
        self.canvas.lightRequest.connect(self.light_request)
        self.canvas.set_drawing_shape_to_square(settings.get(SETTING_DRAW_SQUARE, False))

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scroll_bars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar(),
        }
        self.scroll_area = scroll
        self.canvas.scrollRequest.connect(self.scroll_request)

        self.canvas.newShape.connect(self.new_shape)
        self.canvas.shapeMoved.connect(self.set_dirty)
        self.canvas.selectionChanged.connect(self.shape_selection_changed)
        self.canvas.drawingPolygon.connect(self.toggle_drawing_sensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)
        self.file_dock.setFeatures(QDockWidget.DockWidgetFloatable)

        self.dock_features = QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() & ~int(self.dock_features))

        # Actions
        a_quit = new_action(
            self, self.get_str("quit"), self.close, "Ctrl+Q", "quit", self.get_str("quitApp"))

        a_open = new_action(
            self,
            self.get_str("openFile"),
            self.open_file,
            "Ctrl+O",
            "open",
            self.get_str("openFileDetail"),
        )

        a_open_dir = new_action(
            self,
            self.get_str("openDir"),
            self.open_dir_dialog,
            "Ctrl+u",
            "open",
            self.get_str("openDir"),
        )

        change_label_dir = new_action(
            self,
            self.get_str("changeLabelDir"),
            self.change_label_dir_dialog,
            "Ctrl+r",
            "open",
            self.get_str("changeLabelDirDetail"),
        )

        a_open_annotation = new_action(
            self,
            self.get_str("openAnnotation"),
            self.open_annotation_dialog,
            "Ctrl+Shift+O",
            "open",
            self.get_str("openAnnotationDetail"),
        )
        a_copy_prev_bounding = new_action(
            self,
            self.get_str("copyPrevBounding"),
            self.copy_previous_bounding_boxes,
            "Ctrl+v",
            "copy",
            self.get_str("copyPrevBounding"),
        )

        a_open_next_image = new_action(
            self,
            self.get_str("nextImg"),
            self.open_next_image,
            "d",
            "next",
            self.get_str("nextImgDetail"),
        )

        a_open_prev_image = new_action(
            self,
            self.get_str("prevImg"),
            self.open_prev_image,
            "a",
            "prev",
            self.get_str("prevImgDetail"),
        )

        a_verify = new_action(
            self,
            self.get_str("verifyImg"),
            self.verify_image,
            "space",
            "verify",
            self.get_str("verifyImgDetail"),
        )

        a_save = new_action(
            self,
            self.get_str("save"),
            self.save_labels_file,
            "Ctrl+S",
            "save",
            self.get_str("saveDetail"),
            enabled=False,
        )

        def get_format_meta(label_format: int):
            """
            returns a tuple containing (title, icon_name) of the selected format
            """
            match label_format:
                case LabelFileFormat.PASCAL_VOC:
                    return "&PascalVOC", "format_voc"
                case LabelFileFormat.YOLO:
                    return "&YOLO", "format_yolo"
                case LabelFileFormat.CREATE_ML:
                    return "&CreateML", "format_createml"
                case _:
                    raise ValueError("Unknown label file format.")

        a_label_format_change = new_action(
            self,
            get_format_meta(self.label_file_format)[0],
            self.cycle_label_formats,
            "Ctrl+Y",
            get_format_meta(self.label_file_format)[1],
            self.get_str("changeSaveFormat"),
            enabled=True,
        )

        a_save_as = new_action(
            self,
            self.get_str("saveAs"),
            self.save_file_as,
            "Ctrl+Shift+S",
            "save-as",
            self.get_str("saveAsDetail"),
            enabled=False,
        )

        a_close = new_action(
            self,
            self.get_str("closeCur"),
            self.close_file,
            "Ctrl+W",
            "close",
            self.get_str("closeCurDetail"),
        )

        a_delete_image = new_action(
            self,
            self.get_str("deleteImg"),
            self.delete_image,
            "Ctrl+Shift+D",
            "close",
            self.get_str("deleteImgDetail"),
        )

        a_reset_all = new_action(
            self,
            self.get_str("resetAll"),
            self.reset_all,
            None,
            "resetall",
            self.get_str("resetAllDetail"),
        )

        a_chose_line_color = new_action(
            self,
            self.get_str("boxLineColor"),
            self.choose_line_color,
            "Ctrl+L",
            "color_line",
            self.get_str("boxLineColorDetail"),
        )

        a_switch_to_create_mode = new_action(
            self,
            self.get_str("crtModeBox"),
            self.set_create_mode,
            "w",
            "new",
            self.get_str("crtModeBoxDetail"),
            enabled=False,
        )
        a_switch_to_edit_mode = new_action(
            self,
            self.get_str("editBox"),
            self.set_edit_mode,
            "Ctrl+J",
            "edit",
            self.get_str("editBoxDetail"),
            enabled=False,
        )

        a_create = new_action(
            self,
            self.get_str("crtBox"),
            self.create_shape,
            "w",
            "new",
            self.get_str("crtBoxDetail"),
            enabled=False,
        )
        a_delete = new_action(
            self,
            self.get_str("delBox"),
            self.delete_selected_shape,
            "Delete",
            "delete",
            self.get_str("delBoxDetail"),
            enabled=False,
        )
        a_copy = new_action(
            self,
            self.get_str("dupBox"),
            self.copy_selected_shape,
            "Ctrl+D",
            "copy",
            self.get_str("dupBoxDetail"),
            enabled=False,
        )

        a_toggle_advanced_mode = new_action(
            self,
            self.get_str("advancedMode"),
            self.toggle_advanced_mode,
            "Ctrl+Shift+A",
            "expert",
            self.get_str("advancedModeDetail"),
            checkable=True,
        )

        a_labels_hide_all = new_action(
            self,
            self.get_str("hideAllBox"),
            partial(self.toggle_polygons, False),
            "Ctrl+H",
            "hide",
            self.get_str("hideAllBoxDetail"),
            enabled=False,
        )
        a_labels_show_all = new_action(
            self,
            self.get_str("showAllBox"),
            partial(self.toggle_polygons, True),
            "Ctrl+A",
            "hide",
            self.get_str("showAllBoxDetail"),
            enabled=False,
        )

        a_help_default = new_action(
            self,
            self.get_str("tutorialDefault"),
            self.show_default_tutorial_dialog,
            None,
            "help",
            self.get_str("tutorialDetail"),
        )
        a_show_info = new_action(
            self, self.get_str("info"), self.show_info_dialog, None, "help", self.get_str("info"))
        a_show_shortcut = new_action(
            self,
            self.get_str("shortcut"),
            self.show_shortcuts_dialog,
            None,
            "help",
            self.get_str("shortcut"),
        )

        w_zoom = QWidgetAction(self)
        w_zoom.setDefaultWidget(self.zoom_widget)
        self.zoom_widget.setWhatsThis(
            "Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas."
            % (format_shortcut("Ctrl+[-+]"), format_shortcut("Ctrl+Wheel"))
        )
        self.zoom_widget.setEnabled(False)

        a_zoom_in = new_action(
            self,
            self.get_str("zoomin"),
            partial(self.add_zoom, 10),
            "Ctrl++",
            "zoom-in",
            self.get_str("zoominDetail"),
            enabled=False,
        )
        a_zoom_out = new_action(
            self,
            self.get_str("zoomout"),
            partial(self.add_zoom, -10),
            "Ctrl+-",
            "zoom-out",
            self.get_str("zoomoutDetail"),
            enabled=False,
        )
        a_zoom_reset = new_action(
            self,
            self.get_str("originalsize"),
            partial(self.set_zoom, 100),
            "Ctrl+=",
            "zoom",
            self.get_str("originalsizeDetail"),
            enabled=False,
        )
        a_zoom_fit_window = new_action(
            self,
            self.get_str("fitWin"),
            self.set_fit_window,
            "Ctrl+F",
            "fit-window",
            self.get_str("fitWinDetail"),
            checkable=True,
            enabled=False,
        )
        a_zoom_fit_width = new_action(
            self,
            self.get_str("fitWidth"),
            self.set_fit_width,
            "Ctrl+Shift+F",
            "fit-width",
            self.get_str("fitWidthDetail"),
            checkable=True,
            enabled=False,
        )

        self.zoom_mode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scale_fit_window,
            self.FIT_WIDTH: self.scale_fit_width,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        w_light = QWidgetAction(self)
        w_light.setDefaultWidget(self.light_widget)
        self.light_widget.setWhatsThis(
            "Brighten or darken current image. Also accessible with"
            " %s and %s from the canvas."
            % (
                format_shortcut("Ctrl+Shift+[-+]"),
                format_shortcut("Ctrl+Shift+Wheel"),
            )
        )
        self.light_widget.setEnabled(False)

        a_light_brighten = new_action(
            self,
            self.get_str("lightbrighten"),
            partial(self.add_light, 10),
            "Ctrl+Shift++",
            "light_lighten",
            self.get_str("lightbrightenDetail"),
            enabled=False,
        )
        a_light_darken = new_action(
            self,
            self.get_str("lightdarken"),
            partial(self.add_light, -10),
            "Ctrl+Shift+-",
            "light_darken",
            self.get_str("lightdarkenDetail"),
            enabled=False,
        )
        a_light_reset = new_action(
            self,
            self.get_str("lightreset"),
            partial(self.set_light, 50),
            "Ctrl+Shift+=",
            "light_reset",
            self.get_str("lightresetDetail"),
            checkable=True,
            enabled=False,
        )
        a_light_reset.setChecked(True)

        a_edit = new_action(
            self,
            self.get_str("editLabel"),
            self.edit_label,
            "Ctrl+E",
            "edit",
            self.get_str("editLabelDetail"),
            enabled=False,
        )
        self.edit_button.setDefaultAction(a_edit)

        a_current_shape_chose_line_color = new_action(
            self,
            self.get_str("shapeLineColor"),
            self.current_shape_choose_line_color,
            icon="color_line",
            tip=self.get_str("shapeLineColorDetail"),
            enabled=False,
        )
        a_current_shape_chose_fill_color = new_action(
            self,
            self.get_str("shapeFillColor"),
            self.choose_shape_fill_color,
            icon="color",
            tip=self.get_str("shapeFillColorDetail"),
            enabled=False,
        )
        a_draw_squares_option = new_action(
            self,
            self.get_str("drawSquares"),
            self.toggle_draw_square,
            "Ctrl+Shift+R",
            tip=self.get_str("shapeFillColorDetail"),
            checkable=True,
        )
        a_draw_squares_option.setChecked(settings.get(SETTING_DRAW_SQUARE, False))

        a_labels_toggle = self.dock.toggleViewAction()
        a_labels_toggle.setText(self.get_str("showHide"))
        a_labels_toggle.setShortcut("Ctrl+Shift+L")

        # Label list context menu.
        m_labels = QMenu()
        add_actions(m_labels, (a_edit, a_delete))
        self.label_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.label_list.customContextMenuRequested.connect(self.pop_label_list_menu)

        # Store actions for further handling.

        self.actions = Actions(
            a_open=a_open,
            a_open_dir=a_open_dir,
            a_save=a_save,
            a_save_as=a_save_as,
            a_close=a_close,
            a_reset_all=a_reset_all,
            a_quit=a_quit,
            g_file_menu_actions=(
                a_open,
                a_open_dir,
                a_save,
                a_save_as,
                a_close,
                a_reset_all,
                a_quit,
            ),

            a_edit=a_edit,
            a_copy=a_copy,
            a_delete=a_delete,
            a_chose_line_color=a_chose_line_color,
            a_draw_squares_option=a_draw_squares_option,
            g_edit_menu=(
                a_edit,
                a_copy,
                a_delete,
                None,
                a_chose_line_color,
                a_draw_squares_option,
            ),

            a_label_format_change=a_label_format_change,
            a_delete_img=a_delete_image,
            a_create=a_create,
            a_switch_to_create_mode=a_switch_to_create_mode,
            a_switch_to_edit_mode=a_switch_to_edit_mode,
            a_toggle_advanced_mode=a_toggle_advanced_mode,
            a_current_shape_chose_line_color=a_current_shape_chose_line_color,
            a_current_shape_chose_fill_color=a_current_shape_chose_fill_color,

            a_zoom_in=a_zoom_in,
            a_zoom_out=a_zoom_out,
            a_zoom_reset=a_zoom_reset,
            a_zoom_fit_window=a_zoom_fit_window,
            a_zoom_fit_width=a_zoom_fit_width,
            g_zoom_actions=(
                self.zoom_widget,
                a_zoom_in,
                a_zoom_out,
                a_zoom_reset,
                a_zoom_fit_window,
                a_zoom_fit_width,
            ),

            a_light_brighten=a_light_brighten,
            a_light_darken=a_light_darken,
            a_light_reset=a_light_reset,
            g_light_actions=(
                self.light_widget,
                a_light_brighten,
                a_light_darken,
                a_light_reset,
            ),

            g_toolbar_beginner=None,
            g_toolbar_advanced=None,

            g_menu_beginner=(a_create, a_edit, a_copy, a_delete),
            g_menu_advanced=(
                a_switch_to_create_mode,
                a_switch_to_edit_mode,
                a_edit,
                a_copy,
                a_delete,
                a_delete_image,
                a_current_shape_chose_line_color,
                a_current_shape_chose_fill_color,
            ),
            g_on_load_active=(a_close, a_create, a_switch_to_create_mode, a_switch_to_edit_mode),
            g_on_shapes_present=(a_save_as, a_labels_hide_all, a_labels_show_all),
        )
        # Auto-Annotate via yolo model
        self.a_auto_annotate = QAction("Yolo Auto-Annotate", self)
        self.a_auto_annotate.setStatusTip("Automatically annotate using YOLO")
        self.a_auto_annotate.triggered.connect(self.auto_annotate)

        self.a_auto_annotate_all = QAction("Yolo Auto-Annotate All images", self)
        self.a_auto_annotate_all.setShortcut("Alt+A")
        self.a_auto_annotate_all.setStatusTip("Automatically annotate ALL images using YOLO")
        self.a_auto_annotate_all.triggered.connect(self.auto_annotate_all_images)

        self.menus = Menus(
            m_file=self.menu(self.get_str("menu_file")),
            m_edit=self.menu(self.get_str("menu_edit")),
            m_view=self.menu(self.get_str("menu_view")),
            m_help=self.menu(self.get_str("menu_help")),
            m_recent_files=QMenu(self.get_str("menu_openRecent")),
            m_label_list=m_labels,
        )

        # Auto saving : Enable auto saving if pressing next
        self.a_toggle_auto_saving = QAction(self.get_str("autoSaveMode"), self)
        self.a_toggle_auto_saving.setCheckable(True)
        self.a_toggle_auto_saving.setChecked(settings.get(SETTING_AUTO_SAVE, False))
        # Sync single class mode from PR#106
        self.a_toggle_single_class_mode = QAction(self.get_str("singleClsMode"), self)
        self.a_toggle_single_class_mode.setShortcut("Ctrl+Shift+S")
        self.a_toggle_single_class_mode.setCheckable(True)
        self.a_toggle_single_class_mode.setChecked(settings.get(SETTING_SINGLE_CLASS, False))
        self.lastLabel = None
        # Add option to enable/disable labels being displayed at the top of bounding boxes
        self.a_toggle_display_label_option = QAction(self.get_str("displayLabel"), self)
        self.a_toggle_display_label_option.setShortcut("Ctrl+Shift+P")
        self.a_toggle_display_label_option.setCheckable(True)
        self.a_toggle_display_label_option.setChecked(settings.get(SETTING_PAINT_LABEL, False))
        self.a_toggle_display_label_option.triggered.connect(self.toggle_paint_labels_option)

        add_actions(
            self.menus.m_file,
            (
                a_open,
                a_open_dir,
                change_label_dir,
                a_open_annotation,
                a_copy_prev_bounding,
                self.menus.m_recent_files,
                a_save,
                a_label_format_change,
                a_save_as,
                a_close,
                a_reset_all,
                a_delete_image,
                a_quit,
            ),
        )
        add_actions(self.menus.m_help, (a_help_default, a_show_info, a_show_shortcut))
        add_actions(
            self.menus.m_view,
            (
                self.a_toggle_auto_saving,
                self.a_toggle_single_class_mode,
                self.a_toggle_display_label_option,
                a_labels_toggle,
                a_toggle_advanced_mode,
                None,
                self.a_auto_annotate_all,
                None,
                a_labels_hide_all,
                a_labels_show_all,
                None,
                a_zoom_in,
                a_zoom_out,
                a_zoom_reset,
                None,
                a_zoom_fit_window,
                a_zoom_fit_width,
                None,
                a_light_brighten,
                a_light_darken,
                a_light_reset,
            ),
        )

        self.menus.m_file.aboutToShow.connect(self.update_file_menu)

        # Custom context menu for the canvas widget:
        add_actions(self.canvas.menus[0], self.actions.g_menu_beginner)
        add_actions(
            self.canvas.menus[1],
            (
                new_action(
                    self, "&Copy here", self.copy_shape),
                new_action(
                    self, "&Move here", self.move_shape),
            ),
        )

        self.toolbar = self.toolbar("Tools")
        self.toolbar.addAction(self.a_auto_annotate)

        self.actions.g_toolbar_beginner = (
            a_open,
            a_open_dir,
            change_label_dir,
            a_open_next_image,
            a_open_prev_image,
            a_save,
            a_label_format_change,
            None,
            self.a_auto_annotate,
            None,
            a_create,
            a_edit,
            None,
            a_labels_hide_all,
            a_labels_show_all,
            a_delete,
            a_delete_image,
        )

        self.actions.g_toolbar_advanced = (
            a_open,
            a_open_dir,
            change_label_dir,
            a_open_next_image,
            a_open_prev_image,
            a_verify,
            a_save,
            a_label_format_change,
            None,
            self.a_auto_annotate,
            None,
            a_switch_to_create_mode,
            a_switch_to_edit_mode,
            a_copy,
            a_delete,
            a_delete_image,
            None,
            a_zoom_in,
            w_zoom,
            a_zoom_out,
            a_zoom_fit_window,
            a_zoom_fit_width,
            None,
            a_light_brighten,
            w_light,
            a_light_darken,
            a_light_reset,
        )

        self.statusBar().showMessage("%s started." % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.file_path = ustr(default_filename)
        self.last_open_dir = None
        self.recent_files = []
        self.max_recent = 7
        self.line_color = None
        self.fill_color = None
        self.zoom_level = 100
        self.fit_window = False
        # Add Chris
        self.difficult = False

        # Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)
                self.recent_files = [ustr(i) for i in recent_file_qstring_list]
            else:
                self.recent_files = recent_file_qstring_list = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = QPoint(0, 0)
        saved_position = settings.get(SETTING_WIN_POSE, position)
        # Fix the multiple monitors issue
        for i in range(QApplication.desktop().screenCount()):
            if QApplication.desktop().availableGeometry(i).contains(saved_position):
                position = saved_position
                break
        self.resize(size)
        self.move(position)
        label_dir = ustr(settings.get(SETTING_LABEL_DIR, None))
        self.last_open_dir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if self.default_label_dir is None and label_dir is not None and os.path.exists(label_dir):
            self.default_label_dir = label_dir
            self.statusBar().showMessage(
                "%s started. Annotation will be saved to %s" % (__appname__, self.default_label_dir)
            )
            self.statusBar().show()

        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        Shape.line_color = self.line_color = QColor(
            settings.get(SETTING_LINE_COLOR, DEFAULT_LINE_COLOR)
        )
        Shape.fill_color = self.fill_color = QColor(
            settings.get(SETTING_FILL_COLOR, DEFAULT_FILL_COLOR)
        )
        self.canvas.set_drawing_color(self.line_color)
        # Add chris
        Shape.difficult = self.difficult

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.a_toggle_advanced_mode.setChecked(True)
            self.toggle_advanced_mode(True)
        else:
            self.toggle_advanced_mode(False)

        # Populate the File menu dynamically.
        self.update_file_menu()

        # Since loading the file may take some time, make sure it runs in the background.
        if self.file_path and os.path.isdir(self.file_path):
            self.queue_event(partial(self.import_dir_images, self.file_path or ""))
        elif self.file_path:
            self.queue_event(partial(self.load_file, self.file_path or ""))

        # Callbacks:
        self.zoom_widget.valueChanged.connect(self.paint_canvas)
        self.light_widget.valueChanged.connect(self.paint_canvas)

        self.populate_mode_actions()

        # Display cursor coordinates at the right of status bar
        self.label_coordinates = QLabel("")
        self.statusBar().addPermanentWidget(self.label_coordinates)

        # Open Dir if default file
        if self.file_path and os.path.isdir(self.file_path):
            self.open_dir_dialog(dir_path=self.file_path, silent=True)

    def keyReleaseEvent(self, event, QKeyEvent=None):
        if event.key() == Qt.Key_Control:
            self.canvas.set_drawing_shape_to_square(False)

    def keyPressEvent(self, event, QKeyEvent=None):
        if event.key() == Qt.Key_Control:
            # Draw rectangle if Ctrl is pressed
            self.canvas.set_drawing_shape_to_square(True)

    def get_str(self, text_id: str) -> str:
        return self.string_bundle.get_string(text_id)

    # Support Functions #
    def set_format(self, label_format: LabelFileFormat):
        self.label_file_format = label_format
        self.actions.a_label_format_change.setText(self.get_str(label_format.resource_id()))
        self.actions.a_label_format_change.setIcon(new_icon(label_format.resource_id()))
        LabelFile.suffix = label_format.extension()

    def cycle_label_formats(self):
        match self.label_file_format:
            case LabelFileFormat.PASCAL_VOC:
                self.set_format(LabelFileFormat.YOLO)
            case LabelFileFormat.YOLO:
                self.set_format(LabelFileFormat.CREATE_ML)
            case LabelFileFormat.CREATE_ML:
                self.set_format(LabelFileFormat.PASCAL_VOC)
            case _:
                self.set_format(LabelFileFormat.YOLO)
        self.set_dirty()

    def no_shapes(self):
        return not self.items_to_shapes

    def toggle_advanced_mode(self, advanced_mode=None):
        if advanced_mode is None:
            advanced_mode = not self._advanced_mode
        print(f"Advanced: {self._advanced_mode} -> {advanced_mode}")
        self._advanced_mode = advanced_mode
        self.canvas.set_creating(False)
        self.populate_mode_actions()
        self.edit_button.setVisible(advanced_mode)
        if advanced_mode:
            self._set_create_mode(False)
            self.dock.setFeatures(self.dock.features() | self.dock_features)
        else:
            self.dock.setFeatures(self.dock.features() & ~int(self.dock_features))

    def populate_mode_actions(self):
        if self.beginner():
            tool, menu = self.actions.g_toolbar_beginner, self.actions.g_menu_beginner
        else:
            tool, menu = self.actions.g_toolbar_advanced, self.actions.g_menu_advanced
        self.toolbar.clear()
        add_actions(self.toolbar, tool)
        self.canvas.menus[0].clear()
        add_actions(self.canvas.menus[0], menu)
        self.menus.m_edit.clear()
        actions = (
            (self.actions.a_create,)
            if self.beginner()
            else (self.actions.a_switch_to_create_mode, self.actions.a_switch_to_edit_mode)
        )
        add_actions(self.menus.m_edit, actions + self.actions.g_edit_menu)

    def set_beginner(self):
        self.toolbar.clear()
        add_actions(self.toolbar, self.actions.g_toolbar_beginner)

    def set_advanced(self):
        self.toolbar.clear()
        add_actions(self.toolbar, self.actions.g_toolbar_advanced)

    def set_dirty(self):
        self.dirty = True
        self.actions.a_save.setEnabled(True)

    def set_clean(self):
        self.dirty = False
        self.actions.a_save.setEnabled(False)
        self.actions.a_create.setEnabled(True)

    def toggle_actions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.g_zoom_actions:
            z.setEnabled(value)
        for z in self.actions.g_light_actions:
            z.setEnabled(value)
        for action in self.actions.g_on_load_active:
            action.setEnabled(value)

    def queue_event(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def reset_state(self):
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()
        self.label_list.clear()
        self.file_path = None
        self.image_data = None
        self.label_file = None
        self.canvas.reset_state()
        self.label_coordinates.clear()
        self.combo_box.cb.clear()

    def current_item(self):
        items = self.label_list.selectedItems()
        if items:
            return items[0]
        return None

    def add_recent_file(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        elif len(self.recent_files) >= self.max_recent:
            self.recent_files.pop()
        self.recent_files.insert(0, file_path)

    def beginner(self):
        return not self._advanced_mode

    def advanced(self):
        return self._advanced_mode

    def show_tutorial_dialog(self, browser="default", link=None):
        if link is None:
            link = self.screencast

        if browser.lower() == "default":
            wb.open(link, new=2)
        elif browser.lower() == "chrome" and self.os_name == "Windows":
            if shutil.which(browser.lower()):  # 'chrome' not in wb._browsers in windows
                wb.register("chrome", None, wb.BackgroundBrowser("chrome"))
            else:
                chrome_path = "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
                if os.path.isfile(chrome_path):
                    wb.register("chrome", None, wb.BackgroundBrowser(chrome_path))
            try:
                wb.get("chrome").open(link, new=2)
            except:
                wb.open(link, new=2)
        elif browser.lower() in wb._browsers:
            wb.get(browser.lower()).open(link, new=2)

    def show_default_tutorial_dialog(self):
        self.show_tutorial_dialog(browser="default")

    def show_info_dialog(self):
        from libs.__init__ import __version__

        msg = "Name:{0} \nApp Version:{1} \n{2} ".format(__appname__, __version__, sys.version_info)
        QMessageBox.information(self, "Information", msg)

    def show_shortcuts_dialog(self):
        self.show_tutorial_dialog(
            browser="default",
            link="https://github.com/tzutalin/labelImg#Hotkeys",
        )

    def create_shape(self):
        assert self.beginner()
        self.canvas.set_creating(True)
        self.actions.a_create.setEnabled(False)

    def toggle_drawing_sensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        if self.advanced():
            self.actions.a_switch_to_edit_mode.setEnabled(drawing)

        if not drawing and self.beginner():
            # Cancel creation.
            print("Cancel creation.")
            self.canvas.set_creating(False)
            self.canvas.restore_cursor()
            self.actions.a_create.setEnabled(True)

    def _set_create_mode(self, create_mode: bool):
        print(f"Set create mode: {create_mode}")
        self.canvas.set_creating(create_mode)
        self.actions.a_switch_to_create_mode.setEnabled(not create_mode)
        self.actions.a_switch_to_edit_mode.setEnabled(create_mode)

    def set_create_mode(self):
        assert self.advanced()
        self._set_create_mode(True)

    def set_edit_mode(self):
        assert self.advanced()
        self._set_create_mode(False)
        self.label_selection_changed()

    def update_file_menu(self):
        curr_file_path = self.file_path

        def exists(filename):
            return os.path.exists(filename)

        menu = self.menus.m_recent_files
        menu.clear()
        files = [f for f in self.recent_files if f != curr_file_path and exists(f)]
        for i, f in enumerate(files):
            icon = new_icon("labels")
            action = QAction(icon, "&%d %s" % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.load_recent, f))
            menu.addAction(action)

    def pop_label_list_menu(self, point):
        self.menus.m_label_list.exec_(self.label_list.mapToGlobal(point))

    def edit_label(self):
        if not self.canvas.editing():
            return

        # Получить текущую метку
        item = self.current_item()
        if not item:
            return

        # Открыть диалоговое окно для редактирования
        current_label = item.text()
        new_label = self.label_dialog.pop_up(current_label)
        if new_label and new_label != current_label:
            # Обновляем текст метки
            item.setText(new_label)
            item.setBackground(generate_color_by_text(new_label))

            # Синхронизируем метку с фигурой на холсте
            shape = self.items_to_shapes[item]
            shape.label = new_label
            shape.line_color = generate_color_by_text(new_label)
            shape.fill_color = generate_color_by_text(new_label)

            # Установить флаг изменения
            self.set_dirty()

            # Обновляем список уникальных меток
            self.update_combo_box()

            # Если в истории меток нет новой метки, добавляем её
            if new_label not in self.label_hist:
                self.label_hist.append(new_label)

    def file_item_selected(self):
        item = self.file_list_widget.currentItem()
        if item is None:
            return
        self.cur_img_idx = self.m_img_list.index(ustr(item.text()))
        filename = self.m_img_list[self.cur_img_idx]
        if filename:
            self.load_file(filename)
        self.file_list_widget.setFocus()

    # Takes index from text box and opens corresponding file
    def jump_on_click(self):
        idx_text = self.idx_text_box.text().strip()
        if not idx_text.isdigit():
            self.status("Enter the index number in the window above", 6000)
            return
        self.cur_img_idx = int(idx_text) - 1

        if not self.m_img_list:
            self.status("Select image folder first", 6000)
            return
        if self.cur_img_idx < 0 or self.cur_img_idx >= len(self.m_img_list):
            return

        filename = self.m_img_list[self.cur_img_idx]
        if filename:
            self.load_file(filename)
        self.idx_text_box.setText("")

    # Add chris
    def button_state(self, item=None):
        """Function to handle difficult examples
        Update on each object"""
        if not self.canvas.editing():
            return

        item = self.current_item()
        if not item:  # If not selected Item, take the first one
            item = self.label_list.item(self.label_list.count() - 1)

        difficult = self.diffc_button.isChecked()

        try:
            shape = self.items_to_shapes[item]
        except:
            pass
        # Checked and Update
        try:
            if difficult != shape.difficult:
                shape.difficult = difficult
                self.set_dirty()
            else:  # User probably changed item visibility
                self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)
        except:
            pass

    # React to canvas signals.
    def shape_selection_changed(self, selected=False):
        if self._no_selection_slot:
            self._no_selection_slot = False
        else:
            shape = self.canvas.selected_shape
            if shape:
                self.shapes_to_items[shape].setSelected(True)
            else:
                self.label_list.clearSelection()
        self.actions.a_delete.setEnabled(selected)
        self.actions.a_copy.setEnabled(selected)
        self.actions.a_edit.setEnabled(selected)
        self.actions.a_current_shape_chose_line_color.setEnabled(selected)
        self.actions.a_current_shape_chose_fill_color.setEnabled(selected)

    def add_label(self, shape):
        if shape is None:
            return
        shape.paint_label = self.a_toggle_display_label_option.isChecked()
        item = HashableQListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setBackground(generate_color_by_text(shape.label))
        self.items_to_shapes[item] = shape
        self.shapes_to_items[shape] = item
        self.label_list.addItem(item)
        for action in self.actions.g_on_shapes_present:
            action.setEnabled(True)
        self.update_combo_box()

    def remove_label(self, shape):
        if shape is None:
            # print('rm empty label')
            return

        # Удаляем метку из списка
        item = self.shapes_to_items[shape]
        self.label_list.takeItem(self.label_list.row(item))
        del self.shapes_to_items[shape]
        del self.items_to_shapes[item]
        self.update_combo_box()

        # Проверяем, пуст ли список меток
        if self.label_list.count() == 0:
            # Определяем путь к файлу меток
            if self.default_label_dir:
                label_file_path = os.path.join(
                    self.default_label_dir,
                    os.path.splitext(os.path.basename(self.file_path))[0] + LabelFile.suffix,
                )
            else:
                label_file_path = os.path.splitext(self.file_path)[0] + LabelFile.suffix

            # Если файл меток существует, удаляем его
            if os.path.exists(label_file_path):
                print(f"Deleted label file: {os.path.basename(label_file_path)}")
                try:
                    os.remove(label_file_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete label file: {str(e)}")

    def load_labels(self, shapes):
        # Очищаем текущие данные меток перед загрузкой новых
        self.label_list.clear()
        self.items_to_shapes.clear()
        self.shapes_to_items.clear()

        s = []
        for label, points, line_color, fill_color, difficult in shapes:
            shape = Shape(label=label)
            for x, y in points:

                # Ensure the labels are within the bounds of the image. If not, fix them.
                x, y, snapped = self.canvas.snap_point_to_canvas(x, y)
                if snapped:
                    self.set_dirty()

                shape.add_point(QPointF(x, y))
            shape.difficult = difficult
            shape.close()
            s.append(shape)

            if line_color:
                shape.line_color = QColor(*line_color)
            else:
                shape.line_color = generate_color_by_text(label)

            if fill_color:
                shape.fill_color = QColor(*fill_color)
            else:
                shape.fill_color = generate_color_by_text(label)

            self.add_label(shape)
        self.update_combo_box()
        self.canvas.load_shapes(s)

    def update_combo_box(self):
        # Get the unique labels and add them to the Combobox.
        items_text_list = [
            str(self.label_list.item(i).text()) for i in range(self.label_list.count())
        ]

        unique_text_list = list(set(items_text_list))
        # Add a null row for showing all the labels
        unique_text_list.append("")
        unique_text_list.sort()

        self.combo_box.update_items(unique_text_list)

    def save_labels(self, annotation_file_path):
        annotation_file_path = ustr(annotation_file_path)
        if self.label_file is None:
            self.label_file = LabelFile()
            self.label_file.verified = self.canvas.verified

        def format_shape(s):
            return dict(
                label=s.label,
                line_color=s.line_color.getRgb(),
                fill_color=s.fill_color.getRgb(),
                points=[(p.x(), p.y()) for p in s.points],
                # add chris
                difficult=s.difficult,
            )

        # Форматируем список фигур для сохранения
        shapes = [format_shape(shape) for shape in self.canvas.shapes]

        # Если список фигур пуст, удаляем файл меток (если он существует)
        if not shapes:
            if os.path.exists(annotation_file_path):
                try:
                    os.remove(annotation_file_path)
                    print(f"Label file deleted: {annotation_file_path}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete label file: {str(e)}")
            return False

        # Can add different annotation formats here
        try:
            match self.label_file_format:
                case LabelFileFormat.PASCAL_VOC:
                    if annotation_file_path[-4:].lower() != XML_EXT:
                        annotation_file_path += XML_EXT
                    self.label_file.save_pascal_voc_format(
                        annotation_file_path,
                        shapes,
                        self.file_path,
                        self.image_data,
                        self.line_color.getRgb(),
                        self.fill_color.getRgb(),
                    )
                case LabelFileFormat.YOLO:
                    if annotation_file_path[-4:].lower() != TXT_EXT:
                        annotation_file_path += TXT_EXT
                    self.label_file.save_yolo_format(
                        annotation_file_path,
                        shapes,
                        self.file_path,
                        self.image_data,
                        self.label_hist,
                        self.line_color.getRgb(),
                        self.fill_color.getRgb(),
                    )
                case LabelFileFormat.CREATE_ML:
                    if annotation_file_path[-5:].lower() != JSON_EXT:
                        annotation_file_path += JSON_EXT
                    self.label_file.save_create_ml_format(
                        annotation_file_path,
                        shapes,
                        self.file_path,
                        self.image_data,
                        self.label_hist,
                        self.line_color.getRgb(),
                        self.fill_color.getRgb(),
                    )
                case _:
                    raise ValueError(f"Unknown label file format: {self.label_file_format}")
            print(
                "Image: {0} -> Annotation: {1} \nShapes: {2}".format(
                    os.path.basename(self.file_path), os.path.basename(annotation_file_path), shapes
                )
            )

            return True
        except LabelFileError as e:
            self.error_message("Error saving label data", "<b>%s</b>" % e)
            return False

    def copy_selected_shape(self):
        self.add_label(self.canvas.copy_selected_shape())
        # fix copy and delete
        self.shape_selection_changed(True)

    def combo_selection_changed(self, index):
        text = self.combo_box.cb.itemText(index)
        for i in range(self.label_list.count()):
            if text == "":
                self.label_list.item(i).setCheckState(2)
            elif text != self.label_list.item(i).text():
                self.label_list.item(i).setCheckState(0)
            else:
                self.label_list.item(i).setCheckState(2)

    def default_label_combo_selection_changed(self, index):
        self.default_label = self.label_hist[index]

    def label_selection_changed(self):
        item = self.current_item()
        if item and self.canvas.editing():
            self._no_selection_slot = True
            self.canvas.select_shape(self.items_to_shapes[item])
            shape = self.items_to_shapes[item]
            # Add Chris
            self.diffc_button.setChecked(shape.difficult)

    def label_item_changed(self, item):
        shape = self.items_to_shapes[item]
        label = item.text()
        if label != shape.label:
            shape.label = item.text()
            shape.line_color = generate_color_by_text(shape.label)
            self.set_dirty()
        else:  # User probably changed item visibility
            self.canvas.set_shape_visible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def new_shape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if not self.use_default_label_checkbox.isChecked():
            if len(self.label_hist) > 0:
                self.label_dialog = LabelDialog(parent=self, list_item=self.label_hist)

            # Sync single class mode from PR#106
            if self.a_toggle_single_class_mode.isChecked() and self.lastLabel:
                text = self.lastLabel
            else:
                text = self.label_dialog.pop_up(text=self.prev_label_text)
                self.lastLabel = text
        else:
            text = self.default_label

        # Add Chris
        self.diffc_button.setChecked(False)
        if text is not None:
            self.prev_label_text = text
            generate_color = generate_color_by_text(text)
            shape = self.canvas.set_last_label(text, generate_color, generate_color)
            self.add_label(shape)
            if self.beginner():  # Switch to edit mode.
                self.canvas.set_creating(False)
                self.actions.a_create.setEnabled(True)
            else:
                self.actions.a_switch_to_create_mode.setEnabled(False)
                self.actions.a_switch_to_edit_mode.setEnabled(True)
            self.set_dirty()

            if text not in self.label_hist:
                self.label_hist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.reset_all_lines()

    def scroll_request(self, delta, orientation):
        units = -delta // (8 * 15)
        bar = self.scroll_bars[orientation]
        bar.setValue(int(bar.value() + bar.singleStep() * units))

    def set_zoom(self, value):
        self.actions.a_zoom_fit_width.setChecked(False)
        self.actions.a_zoom_fit_window.setChecked(False)
        self.zoom_mode = self.MANUAL_ZOOM
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.zoom_widget.setValue(int(value))

    def add_zoom(self, increment=10):
        self.set_zoom(self.zoom_widget.value() + increment)

    def zoom_request(self, delta):
        # get the current scrollbar positions
        # calculate the percentages ~ coordinates
        h_bar = self.scroll_bars[Qt.Horizontal]
        v_bar = self.scroll_bars[Qt.Vertical]

        # get the current maximum, to know the difference after zooming
        h_bar_max = h_bar.maximum()
        v_bar_max = v_bar.maximum()

        # get the cursor position and canvas size
        # calculate the desired movement from 0 to 1
        # where 0 = move left
        #       1 = move right
        # up and down analogous
        cursor = QCursor()
        pos = cursor.pos()
        relative_pos = QWidget.mapFromGlobal(self, pos)

        cursor_x = relative_pos.x()
        cursor_y = relative_pos.y()

        w = self.scroll_area.width()
        h = self.scroll_area.height()

        # the scaling from 0 to 1 has some padding
        # you don't have to hit the very leftmost pixel for a maximum-left movement
        margin = 0.1
        move_x = (cursor_x - margin * w) / (w - 2 * margin * w)
        move_y = (cursor_y - margin * h) / (h - 2 * margin * h)

        # clamp the values from 0 to 1
        move_x = min(max(move_x, 0), 1)
        move_y = min(max(move_y, 0), 1)

        # zoom in
        units = delta // (8 * 15)
        scale = 10
        self.add_zoom(scale * units)

        # get the difference in scrollbar values
        # this is how far we can move
        d_h_bar_max = h_bar.maximum() - h_bar_max
        d_v_bar_max = v_bar.maximum() - v_bar_max

        # get the new scrollbar values
        new_h_bar_value = int(h_bar.value() + move_x * d_h_bar_max)
        new_v_bar_value = int(v_bar.value() + move_y * d_v_bar_max)

        h_bar.setValue(new_h_bar_value)
        v_bar.setValue(new_v_bar_value)

    def light_request(self, delta):
        self.add_light(5 * delta // (8 * 15))

    def set_fit_window(self, value=True):
        if value:
            self.actions.a_zoom_fit_width.setChecked(False)
        self.zoom_mode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_fit_width(self, value=True):
        if value:
            self.actions.a_zoom_fit_window.setChecked(False)
        self.zoom_mode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjust_scale()

    def set_light(self, value):
        self.actions.a_light_reset.setChecked(int(value) == 50)
        # Arithmetic on scaling factor often results in float
        # Convert to int to avoid type errors
        self.light_widget.setValue(int(value))

    def add_light(self, increment=10):
        self.set_light(self.light_widget.value() + increment)

    def toggle_polygons(self, value):
        for item, shape in self.items_to_shapes.items():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def load_file(self, file_path=None):
        """Load the specified file, or the last opened file if None."""
        self.reset_state()
        self.canvas.setEnabled(False)
        if file_path is None:
            file_path = self.settings.get(SETTING_FILENAME)
        # Make sure that filePath is a regular python string, rather than QString
        unicode_file_path = ustr(file_path)

        # Fix bug: An  index error after select a directory when open a new file.
        unicode_file_path = os.path.abspath(unicode_file_path)
        # Tzutalin 20160906 : Add file list and dock to move faster
        # Highlight the file item
        if unicode_file_path and self.file_list_widget.count() > 0:
            if unicode_file_path in self.m_img_list:
                img_list_index = self.m_img_list.index(unicode_file_path)
                file_widget_item = self.file_list_widget.item(img_list_index)
                file_widget_item.setSelected(True)
            else:
                self.file_list_widget.clear()
                self.m_img_list.clear()

        if unicode_file_path and os.path.exists(unicode_file_path):
            if LabelFile.is_label_file(unicode_file_path):
                try:
                    self.label_file = LabelFile(unicode_file_path)
                except LabelFileError as e:
                    self.error_message(
                        "Error opening file",
                        ("<p><b>%s</b></p>" "<p>Make sure <i>%s</i> is a valid label file.")
                        % (e, unicode_file_path),
                    )
                    self.status("Error reading %s" % unicode_file_path)

                    return False
                self.image_data = self.label_file.image_data
                self.line_color = QColor(*self.label_file.lineColor)
                self.fill_color = QColor(*self.label_file.fillColor)
                self.canvas.verified = self.label_file.verified
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.image_data = self.read(unicode_file_path)
                self.label_file = None
                self.canvas.verified = False

            if isinstance(self.image_data, QImage):
                image = self.image_data
            else:
                image = QImage.fromData(self.image_data)
            if image.isNull():
                self.error_message(
                    "Error opening file",
                    "<p>Make sure <i>%s</i> is a valid image file." % unicode_file_path,
                )
                self.status("Error reading %s" % unicode_file_path)
                return False
            self.status("Loaded %s" % os.path.basename(unicode_file_path))
            self.image = image
            self.file_path = unicode_file_path
            self.canvas.load_pixmap(QPixmap.fromImage(image))
            if self.label_file:
                self.load_labels(self.label_file.shapes)
            self.set_clean()
            self.canvas.setEnabled(True)
            self.adjust_scale(initial=True)
            self.paint_canvas()
            self.add_recent_file(self.file_path)
            self.toggle_actions(True)
            self.show_bounding_box_from_annotation_file(self.file_path)

            counter = self.counter_str()
            self.setWindowTitle(__appname__ + " " + file_path + " " + counter)
            self.canvas.setFocus(True)
            return True
        return False

    def read(self, filename):
        try:
            reader = QImageReader(filename)
            reader.setAutoTransform(True)
            return reader.read()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read file: {filename}\nError: {str(e)}")
            return None

    def counter_str(self):
        """
        Converts image counter to string representation.
        """
        return "[{} / {}]".format(self.cur_img_idx + 1, self.img_count)

    def show_bounding_box_from_annotation_file(self, file_path) -> bool:
        """
        Returns True if the file is successfully loaded.
        """
        if not file_path:
            self.status("Select image folder first", 6000)
            return False
        # Try load labels from specified directory first
        if self.default_label_dir is not None:
            basename = os.path.basename(os.path.splitext(file_path)[0])
            xml_path = os.path.join(self.default_label_dir, basename + XML_EXT)
            txt_path = os.path.join(self.default_label_dir, basename + TXT_EXT)
            json_path = os.path.join(self.default_label_dir, basename + JSON_EXT)

            success = self.try_load_all_formats(file_path, json_path, txt_path, xml_path)
            if success:
                return True

        xml_path = os.path.splitext(file_path)[0] + XML_EXT
        txt_path = os.path.splitext(file_path)[0] + TXT_EXT
        json_path = os.path.splitext(file_path)[0] + JSON_EXT

        return self.try_load_all_formats(file_path, json_path, txt_path, xml_path)

    def try_load_all_formats(self, file_path, json_path, txt_path, xml_path) -> bool:
        """Annotation file priority:
            PascalXML > YOLO > CreateML
            Return True if the file was successfully loaded.
            """
        if os.path.isfile(xml_path):
            return self.load_pascal_xml_by_filename(xml_path)
        elif os.path.isfile(txt_path):
            return self.load_yolo_txt_by_filename(txt_path)
        elif os.path.isfile(json_path):
            return self.load_create_ml_json_by_filename(json_path, file_path)
        return False

    def resizeEvent(self, event, QResizeEvent=None):
        if self.canvas and not self.image.isNull() and self.zoom_mode != self.MANUAL_ZOOM:
            self.adjust_scale()
        super(MainWindow, self).resizeEvent(event)

    def paint_canvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoom_widget.value()
        self.canvas.overlay_color = self.light_widget.color()
        self.canvas.label_font_size = int(0.02 * max(self.image.width(), self.image.height()))
        self.canvas.adjustSize()
        self.canvas.update()

    def adjust_scale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoom_mode]()
        self.zoom_widget.setValue(int(100 * value))

    def scale_fit_window(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scale_fit_width(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event, QCloseEvent=None):
        if not self.may_continue():
            event.ignore()
        settings = self.settings
        # If it loads images from dir, don't load it at the beginning
        if self.dir_name is None:
            settings[SETTING_FILENAME] = self.file_path if self.file_path else ""
        else:
            settings[SETTING_FILENAME] = ""

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.line_color
        settings[SETTING_FILL_COLOR] = self.fill_color
        settings[SETTING_RECENT_FILES] = self.recent_files
        settings[SETTING_ADVANCE_MODE] = self._advanced_mode
        if self.default_label_dir and os.path.exists(self.default_label_dir):
            settings[SETTING_LABEL_DIR] = ustr(self.default_label_dir)
        else:
            settings[SETTING_LABEL_DIR] = ""

        if self.last_open_dir and os.path.exists(self.last_open_dir):
            settings[SETTING_LAST_OPEN_DIR] = self.last_open_dir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ""

        settings[SETTING_AUTO_SAVE] = self.a_toggle_auto_saving.isChecked()
        settings[SETTING_SINGLE_CLASS] = self.a_toggle_single_class_mode.isChecked()
        settings[SETTING_PAINT_LABEL] = self.a_toggle_display_label_option.isChecked()
        settings[SETTING_DRAW_SQUARE] = self.actions.a_draw_squares_option.isChecked()
        settings[SETTING_LABEL_FILE_FORMAT] = self.label_file_format
        settings.save()

    def load_recent(self, filename):
        if self.may_continue():
            self.load_file(filename)

    @staticmethod
    def scan_all_images(folder_path):
        extensions = [
            ".%s" % fmt.data().decode("ascii").lower()
            for fmt in QImageReader.supportedImageFormats()
        ]
        images = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relative_path = os.path.join(root, file)
                    path = ustr(os.path.abspath(relative_path))
                    images.append(path)
        images.sort()
        return images

    def change_label_dir_dialog(self, _value=False):
        if isinstance(_value, str) and os.path.isdir(_value):
            self.default_label_dir = _value
            self.show_bounding_box_from_annotation_file(self.file_path)
            self.statusBar().showMessage(
                "%s . Annotation will be saved to %s"
                % ("Change saved folder", self.default_label_dir)
            )
            print("Change saved folder", self.default_label_dir)
            self.statusBar().show()
            return

        if self.default_label_dir is not None:
            path = ustr(self.default_label_dir)
        else:
            path = "."

        dir_path = QFileDialog.getExistingDirectory(
            self,
            "%s - Save annotations to the directory" % __appname__,
            path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if dir_path:
            self.default_label_dir = ustr(dir_path)
            self.status("Save directory changed to %s" % self.default_label_dir, 5000)
        else:
            # Prevent application from closing when canceling the dialog
            self.status("Save directory change canceled", 2000)
            return

        if dir_path is not None and len(dir_path) > 1:
            self.default_label_dir = dir_path
            self.show_bounding_box_from_annotation_file(self.file_path)

            self.status(
                "%s . Annotation will be saved to %s"
                % ("Change saved folder", self.default_label_dir)
            )
            self.statusBar().show()
        else:
            self.status("Select image folder first", 2000)
            self.statusBar().show()
            return

    def open_annotation_dialog(self, _value=False):
        if self.file_path is None:
            self.statusBar().showMessage("Please select image first")
            self.statusBar().show()
            return

        path = os.path.dirname(ustr(self.file_path)) if self.file_path else "."
        match self.label_file_format:
            case LabelFileFormat.PASCAL_VOC:
                filters = "Open Annotation XML file (%s)" % " ".join(["*.xml"])
                filename = ustr(
                    QFileDialog.getOpenFileName(
                        self, "%s - Choose a xml file" % __appname__, path, filters
                    )
                )
                if filename:
                    if isinstance(filename, (tuple, list)):
                        filename = filename[0]
                self.load_pascal_xml_by_filename(filename)
            case LabelFileFormat.YOLO:
                filters = "Open Annotation TXT file (%s)" % " ".join(["*.txt"])
                filename = ustr(
                    QFileDialog.getOpenFileName(
                        self, "%s - Choose a txt file" % __appname__, path, filters
                    )
                )
                if filename:
                    if isinstance(filename, (tuple, list)):
                        filename = filename[0]

                self.load_yolo_txt_by_filename(filename)
            case LabelFileFormat.CREATE_ML:
                filters = "Open Annotation JSON file (%s)" % " ".join(["*.json"])
                filename = ustr(
                    QFileDialog.getOpenFileName(
                        self, "%s - Choose a json file" % __appname__, path, filters
                    )
                )
                if filename:
                    if isinstance(filename, (tuple, list)):
                        filename = filename[0]

                self.load_create_ml_json_by_filename(filename, self.file_path)

    def open_dir_dialog(self, _value=False, dir_path=None, silent=False):
        if not self.may_continue():
            return

        if dir_path is not None:
            default_open_dir_path = dir_path
        elif self.last_open_dir and os.path.exists(self.last_open_dir):
            default_open_dir_path = self.last_open_dir
        else:
            default_open_dir_path = os.path.dirname(self.file_path) if self.file_path else "."

        if not silent:
            target_dir_path = ustr(
                QFileDialog.getExistingDirectory(
                    self,
                    "%s - Open Directory" % __appname__,
                    default_open_dir_path,
                    QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
                )
            )
        else:
            target_dir_path = ustr(default_open_dir_path)
        self.last_open_dir = target_dir_path
        self.import_dir_images(target_dir_path)

        if not self.default_label_dir:
            self.default_label_dir = target_dir_path
        file_containing_labels = os.path.join(self.default_label_dir, "labels.txt")
        if not self.label_hist:
            self.load_predefined_classes(file_containing_labels)
            if not os.path.exists(file_containing_labels):
                self.label_hist = []

        if self.file_path:
            if not self.show_bounding_box_from_annotation_file(file_path=self.file_path):
                qm = QMessageBox()
                answer = qm.question(
                    self,
                    self.get_str("noLabelsFound"),
                    self.get_str("noLabelsFoundLoadQuestion"),
                    qm.Yes | qm.No
                )
                if answer == qm.Yes:
                    self.change_label_dir_dialog()

    def import_dir_images(self, dir_path):
        if not self.may_continue() or not dir_path:
            return

        self.last_open_dir = dir_path
        self.dir_name = dir_path
        self.file_path = None
        self.file_list_widget.clear()
        self.m_img_list = self.scan_all_images(dir_path)
        self.img_count = len(self.m_img_list)
        self.open_next_image()
        for imgPath in self.m_img_list:
            item = QListWidgetItem(imgPath)
            self.file_list_widget.addItem(item)

    def verify_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if self.file_path is not None:
            try:
                self.label_file.toggle_verify()
            except AttributeError:
                # If the labelling file does not exist yet, create if and
                # re-save it with the verified attribute.
                self.save_labels_file()
                if self.label_file is not None:
                    self.label_file.toggle_verify()
                else:
                    return

            self.canvas.verified = self.label_file.verified
            self.paint_canvas()
            self.save_labels_file()

    def is_okay_to_load_new_image(self) -> bool:
        if self.a_toggle_auto_saving.isChecked():
            if self.default_label_dir is not None:
                if self.dirty:
                    self.save_labels_file()
            else:
                self.change_label_dir_dialog()
                return False

        if not self.may_continue():
            return False

        if self.img_count <= 0:
            return False
        return True

    def open_prev_image(self, _value=False):
        # Proceeding prev image without dialog if having any label
        if not self.is_okay_to_load_new_image():
            return

        if self.file_path is None:
            return

        if self.cur_img_idx - 1 >= 0:
            self.cur_img_idx -= 1
            filename = self.m_img_list[self.cur_img_idx]
            if filename:
                self.load_file(filename)

    def open_next_image(self, _value=False):
        # Proceeding next image without dialog if having any label
        if not self.is_okay_to_load_new_image():
            return

        if not self.m_img_list:
            return

        filename = None
        if self.file_path is None:
            filename = self.m_img_list[0]
            self.cur_img_idx = 0
        else:
            if self.cur_img_idx + 1 < self.img_count:
                self.cur_img_idx += 1
                filename = self.m_img_list[self.cur_img_idx]

        if filename:
            self.load_file(filename)

    def open_file(self, _value=False):
        if not self.may_continue():
            return
        path = os.path.dirname(ustr(self.file_path)) if self.file_path else "."
        formats = [
            "*.%s" % fmt.data().decode("ascii").lower()
            for fmt in QImageReader.supportedImageFormats()
        ]
        filters = "Image & Label files (%s)" % " ".join(formats + ["*%s" % LabelFile.suffix])
        filename, _ = QFileDialog.getOpenFileName(
            self, "%s - Choose Image or Label file" % __appname__, path, filters
        )
        if filename:
            if isinstance(filename, (tuple, list)):
                filename = filename[0]
            self.cur_img_idx = 0
            self.img_count = 1
            self.load_file(filename)

    def save_labels_file(self, _value=False):
        if self.default_label_dir is not None and len(ustr(self.default_label_dir)):
            if self.file_path:
                image_file_name = os.path.basename(self.file_path)
                saved_file_name = os.path.splitext(image_file_name)[0]
                saved_path = os.path.join(ustr(self.default_label_dir), saved_file_name)
                self._save_labels_file(saved_path)
            else:
                QMessageBox.warning(self, "Warning", "No file is currently loaded to save.")
        else:
            if self.file_path:
                image_file_dir = os.path.dirname(self.file_path)
                image_file_name = os.path.basename(self.file_path)
                saved_file_name = os.path.splitext(image_file_name)[0]
                saved_path = os.path.join(image_file_dir, saved_file_name)
                self._save_labels_file(
                    saved_path if self.label_file else self.save_file_dialog(remove_ext=False)
                )
            else:
                QMessageBox.warning(self, "Warning", "No file is currently loaded to save.")

    def save_file_as(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._save_labels_file(self.save_file_dialog())

    def save_file_dialog(self, remove_ext=True):
        caption = "%s - Choose File" % __appname__
        filters = "File (*%s)" % LabelFile.suffix
        open_dialog_path = self.current_path()
        dlg = QFileDialog(self, caption, open_dialog_path, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        filename_without_extension = os.path.splitext(self.file_path)[0]
        dlg.selectFile(filename_without_extension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            full_file_path = ustr(dlg.selectedFiles()[0])
            if remove_ext:
                return os.path.splitext(full_file_path)[
                    0
                ]  # Return file path without the extension.
            else:
                return full_file_path
        return ""

    def _save_labels_file(self, annotation_file_path):
        if annotation_file_path and self.save_labels(annotation_file_path):
            self.set_clean()
            self.statusBar().showMessage("Saved to  %s" % annotation_file_path)
            self.statusBar().show()

    def close_file(self, _value=False):
        if not self.may_continue():
            return
        self.reset_state()
        self.set_clean()
        self.toggle_actions(False)
        self.canvas.setEnabled(False)
        self.actions.a_save_as.setEnabled(False)

    def delete_image(self):
        if not self.file_path:
            QMessageBox.warning(self, "Warning", "No image selected for deletion.")
            return
        else:
            delete_path = self.file_path
            idx = self.cur_img_idx

            # Удаление изображения
            if os.path.exists(delete_path):
                print(f"Deleted image: {delete_path}")
                os.remove(delete_path)

                if self.default_label_dir:
                    label_file_path = os.path.join(
                        self.default_label_dir,
                        os.path.splitext(os.path.basename(self.file_path))[0] + LabelFile.suffix,
                    )
                else:
                    label_file_path = os.path.splitext(self.file_path)[0] + LabelFile.suffix

                if os.path.exists(label_file_path):
                    try:
                        print(f"Deleted label file: {label_file_path}")
                        os.remove(label_file_path)
                    except Exception as e:
                        QMessageBox.warning(self, "Error", f"Failed to delete label file: {str(e)}")

            self.import_dir_images(self.last_open_dir)
            if self.img_count > 0:
                self.cur_img_idx = min(idx, self.img_count - 1)
                filename = self.m_img_list[self.cur_img_idx]
                self.load_file(filename)
            else:
                self.close_file()

    def reset_all(self):
        self.settings.reset()
        self.close()
        process = QProcess()
        process.startDetached(os.path.abspath(__file__))

    def may_continue(self) -> bool:
        if not self.dirty:
            return True
        else:
            discard_changes = self.discard_changes_dialog()
            if discard_changes == QMessageBox.No:
                return True
            elif discard_changes == QMessageBox.Yes:
                self.save_labels_file()
                return True
            else:
                return False

    def discard_changes_dialog(self):
        yes, no, cancel = QMessageBox.Yes, QMessageBox.No, QMessageBox.Cancel
        msg = 'You have unsaved changes, would you like to save them and proceed?\nClick "No" to undo all changes.'
        return QMessageBox.warning(self, "Attention", msg, yes | no | cancel)

    def error_message(self, title, message):
        return QMessageBox.critical(self, title, "<p><b>%s</b></p>%s" % (title, message))

    def current_path(self):
        return os.path.dirname(self.file_path) if self.file_path else "."

    def choose_line_color(self):
        color = self.color_dialog.getColor(
            self.line_color, "Choose line color", default=DEFAULT_LINE_COLOR
        )
        if color:
            self.line_color = color
            Shape.line_color = color
            self.canvas.set_drawing_color(color)
            self.canvas.update()
            self.set_dirty()

    def delete_selected_shape(self):
        self.remove_label(self.canvas.delete_selected())
        self.set_dirty()

        if self.no_shapes():
            for action in self.actions.g_on_shapes_present:
                action.setEnabled(False)

    def current_shape_choose_line_color(self):
        color = self.color_dialog.getColor(
            self.line_color, "Choose Line Color", default=DEFAULT_LINE_COLOR
        )
        if color:
            self.canvas.selected_shape.line_color = color
            self.canvas.update()
            self.set_dirty()

    def choose_shape_fill_color(self):
        color = self.color_dialog.getColor(
            self.fill_color, "Choose Fill Color", default=DEFAULT_FILL_COLOR
        )
        if color:
            self.canvas.selected_shape.fill_color = color
            self.canvas.update()
            self.set_dirty()

    def copy_shape(self):
        if self.canvas.selected_shape is None:
            # True if one accidentally touches the left mouse button before releasing
            return
        self.canvas.end_move(copy=True)
        self.add_label(self.canvas.selected_shape)
        self.set_dirty()

    def move_shape(self):
        self.canvas.end_move(copy=False)
        self.set_dirty()

    def load_predefined_classes(self, predef_classes_file):
        if os.path.exists(predef_classes_file):
            with codecs.open(predef_classes_file, "r", "utf8") as f:
                for line in f:
                    line = line.strip()
                    if self.label_hist is None:
                        self.label_hist = [line]
                    else:
                        self.label_hist.append(line)

    def load_pascal_xml_by_filename(self, xml_path) -> bool:
        """
        Returns True if the file is successfully loaded.
        """
        if self.file_path is None:
            return False
        if not os.path.isfile(xml_path):
            return False

        self.set_format(LabelFileFormat.PASCAL_VOC)

        t_voc_parse_reader = PascalVocReader(xml_path)
        shapes = t_voc_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = t_voc_parse_reader.verified
        return True

    def load_yolo_txt_by_filename(self, txt_path) -> bool:
        """
        Returns True if the file is successfully loaded.
        """
        print(f"Loading YOLO txt file 1: {txt_path}")
        if self.file_path is None:
            return False
        if not os.path.isfile(txt_path):
            return False

        self.set_format(LabelFileFormat.YOLO)
        t_yolo_parse_reader = YoloReader(txt_path, self.image, self.default_prefdef_class_file)
        shapes = t_yolo_parse_reader.get_shapes()

        # print(os.path.basename(txt_path), shapes)
        self.load_labels(shapes)
        self.canvas.verified = t_yolo_parse_reader.verified
        return True

    def load_create_ml_json_by_filename(self, json_path, file_path) -> bool:
        """
        Returns True if the file is successfully loaded.
        """
        if self.file_path is None:
            return False
        if not os.path.isfile(json_path):
            return False

        self.set_format(LabelFileFormat.CREATE_ML)

        create_ml_parse_reader = CreateMLReader(json_path, file_path)
        shapes = create_ml_parse_reader.get_shapes()
        self.load_labels(shapes)
        self.canvas.verified = create_ml_parse_reader.verified
        return True

    def copy_previous_bounding_boxes(self):
        current_index = self.m_img_list.index(self.file_path)
        if current_index - 1 >= 0:
            prev_file_path = self.m_img_list[current_index - 1]
            self.show_bounding_box_from_annotation_file(prev_file_path)
            self.save_labels_file()

    def toggle_paint_labels_option(self):
        for shape in self.canvas.shapes:
            shape.paint_label = self.a_toggle_display_label_option.isChecked()

    def toggle_draw_square(self):
        self.canvas.set_drawing_shape_to_square(self.actions.a_draw_squares_option.isChecked())

    def auto_annotate(self):
        if not hasattr(self, "file_path") or not self.file_path:
            QMessageBox.warning(self, "Warning", "No image loaded for annotation.")
            return

        try:
            annotator = YOLOAutoAnnotator()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Model Not Found", str(e))
            return

        annotations = annotator.annotate(self.file_path)
        if not annotations:
            QMessageBox.information(self, "No Annotations", "No objects detected.")
            return

        shapes = []
        for ann in annotations:
            label = ann["label"]
            x1, y1, x2, y2 = ann["bbox"]
            points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            shape_data = (label, points, None, None, False)
            shapes.append(shape_data)

        self.load_labels(shapes)
        self.set_dirty()

    def auto_annotate_all_images(self):
        if not self.m_img_list:
            QMessageBox.information(self, "No Images", "No images loaded.")
            return

        try:
            annotator = YOLOAutoAnnotator()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Model Not Found", str(e))
            return

        for index, imgPath in enumerate(self.m_img_list):
            self.file_path = imgPath
            self.load_file(imgPath)

            annotations = annotator.annotate(imgPath)
            if not annotations:
                continue

            shapes = []
            for ann in annotations:
                label = ann["label"]
                x1, y1, x2, y2 = ann["bbox"]
                points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
                shapes.append((label, points, None, None, False))

            self.load_labels(shapes)
            self.save_labels_file()

        QMessageBox.information(self, "Complete", "All images have been auto-annotated.")


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def get_main_app(argv=None):
    """
    Standard boilerplate Qt application code.
    Do everything but app.exec_() -- so that we can test the application in one thread
    """
    if not argv:
        argv = []
    app = QApplication(argv)
    app.setApplicationName(__appname__)
    app.setWindowIcon(new_icon("app"))
    # Tzutalin 201705+: Accept extra agruments to change predefined class file
    argparser = argparse.ArgumentParser()
    argparser.add_argument("image_dir", nargs="?")
    argparser.add_argument(
        "class_file",
        default=os.path.join(os.path.dirname(__file__), "data", "predefined_classes.txt"),
        nargs="?",
    )
    argparser.add_argument("label_dir", nargs="?")
    args = argparser.parse_args(argv[1:])

    args.image_dir = args.image_dir and os.path.normpath(args.image_dir)
    args.class_file = args.class_file and os.path.normpath(args.class_file)
    args.label_dir = args.label_dir and os.path.normpath(args.label_dir)

    # Usage : labelImg.py image classFile saveDir
    win = MainWindow(args.image_dir, args.class_file, args.label_dir)
    win.show()
    return app, win


def main():
    """construct main app and run it"""
    app, _win = get_main_app(sys.argv)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
