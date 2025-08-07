from dataclasses import dataclass
from typing import Optional

from PyQt5.QtWidgets import QAction, QWidgetAction, QMenu

from libs.lightWidget import LightWidget
from libs.zoomWidget import ZoomWidget


@dataclass
class Actions:
    save: QAction
    save_format: QAction
    saveAs: QAction
    open: QAction
    close: QAction
    resetAll: QAction
    deleteImg: QAction
    lineColor: QAction
    create: QAction
    delete: QAction
    edit: QAction
    copy: QAction
    createMode: QAction
    editMode: QAction
    advancedMode: QAction
    shapeLineColor: QAction
    shapeFillColor: QAction
    zoom: QWidgetAction
    zoomIn: QAction
    zoomOut: QAction
    zoomOrg: QAction
    fitWindow: QAction
    fitWidth: QAction
    zoomActions: tuple[ZoomWidget, QAction, QAction, QAction, QAction, QAction]
    lightBrighten: QAction
    lightDarken: QAction
    lightOrg: QAction
    lightActions: tuple[LightWidget, QAction, QAction, QAction]
    fileMenuActions: tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction]
    beginner: Optional[tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, None, QAction, None, QAction, QAction, None, QAction, QAction, QAction, QAction]]
    advanced: Optional[tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, QAction, None, QAction, None, QAction, QAction, QAction, QAction, QAction, None, QAction, QWidgetAction, QAction, QAction, QAction, None, QAction, QWidgetAction, QAction, QAction]]
    editMenu: tuple[QAction, QAction, QAction, None, QAction, QAction]
    beginnerContext: tuple[QAction, QAction, QAction, QAction]
    advancedContext: tuple[QAction, QAction, QAction, QAction, QAction, QAction, QAction, QAction]
    onLoadActive: tuple[QAction, QAction, QAction, QAction]
    onShapesPresent: tuple[QAction, QAction, QAction]

@dataclass
class Menus:
    file: QMenu
    edit: QMenu
    view: QMenu
    help: QMenu
    recentFiles: QMenu
    labelList: QMenu