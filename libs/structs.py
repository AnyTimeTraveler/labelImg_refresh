from dataclasses import dataclass
from typing import Optional

from PyQt5.QtWidgets import QAction, QWidgetAction, QMenu

from libs.lightWidget import LightWidget
from libs.zoomWidget import ZoomWidget


@dataclass
class Actions:
    a_open: QAction
    a_open_dir: QAction
    a_save: QAction
    a_save_as: QAction
    a_close: QAction
    a_reset_all: QAction
    a_quit: QAction
    g_file_menu_actions: tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction]

    a_edit: QAction
    a_copy: QAction
    a_delete: QAction
    a_chose_line_color: QAction
    a_draw_squares_option: QAction
    g_edit_menu: tuple[QAction, QAction, QAction, None, QAction, QAction]

    a_label_format_change: QAction
    a_delete_img: QAction
    a_create: QAction
    a_switch_to_create_mode: QAction
    a_switch_to_edit_mode: QAction
    a_toggle_advanced_mode: QAction
    a_current_shape_chose_line_color: QAction
    a_current_shape_chose_fill_color: QAction

    a_zoom_in: QAction
    a_zoom_out: QAction
    a_zoom_reset: QAction
    a_zoom_fit_window: QAction
    a_zoom_fit_width: QAction
    g_zoom_actions: tuple[ZoomWidget, QAction, QAction, QAction, QAction, QAction]

    a_light_brighten: QAction
    a_light_darken: QAction
    a_light_reset: QAction
    g_light_actions: tuple[LightWidget, QAction, QAction, QAction]

    g_toolbar_beginner: Optional[tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, None, QAction, None, QAction, QAction, None, QAction, QAction, QAction, QAction]]
    g_toolbar_advanced: Optional[tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, QAction, None, QAction, None, QAction, QAction, QAction, QAction, QAction, None, QAction, QWidgetAction, QAction, QAction, QAction, None, QAction, QWidgetAction, QAction, QAction]]
    g_menu_beginner: tuple[QAction, QAction, QAction, QAction]
    g_menu_advanced: tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, QAction]
    g_on_load_active: tuple[QAction, QAction, QAction, QAction]
    g_on_shapes_present: tuple[QAction, QAction, QAction]

@dataclass
class Menus:
    m_file: QMenu
    m_edit: QMenu
    m_view: QMenu
    m_help: QMenu
    m_recent_files: QMenu
    m_label_list: QMenu