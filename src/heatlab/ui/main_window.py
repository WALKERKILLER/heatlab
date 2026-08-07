"""Application main window and global seed control."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolBar,
)

from heatlab.constants import DEFAULT_SEED
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager
from heatlab.ui.brownian_tab import BrownianTab
from heatlab.ui.galton_tab import GaltonTab
from heatlab.ui.ideal_gas_tab import IdealGasTab
from heatlab.ui.maxwell_tab import MaxwellTab
from heatlab.ui.style import APP_STYLE


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HeatLab · 热学科学计算可视化")
        self.resize(1440, 850)
        self.setStyleSheet(APP_STYLE)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.statusBar().hide()
        self._create_toolbar()
        self.rebuild_tabs(DEFAULT_SEED)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("全局设置", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.addWidget(QLabel("随机种子"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(DEFAULT_SEED)
        self.seed_spin.setMinimumWidth(130)
        toolbar.addWidget(self.seed_spin)
        apply_button = QPushButton("应用并重置全部")
        apply_button.clicked.connect(lambda: self.rebuild_tabs(self.seed_spin.value()))
        toolbar.addWidget(apply_button)

    def rebuild_tabs(self, seed: int) -> None:
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()

        manager = RandomManager(seed)
        self.tabs.addTab(IdealGasTab(IdealGasModel(manager.stream("ideal-gas"))), "热力学")
        self.tabs.addTab(BrownianTab(BrownianModel(manager.stream("brownian"))), "布朗运动")
        self.tabs.addTab(MaxwellTab(MaxwellModel(manager.stream("maxwell"))), "麦克斯韦分布")
        self.tabs.addTab(GaltonTab(GaltonModel(manager.stream("galton"))), "伽尔顿板")
