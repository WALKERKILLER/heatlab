"""Application main window: top bar + topic tabs + three-column workbench + status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget

from heatlab.constants import DEFAULT_SEED
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager
from heatlab.ui.brownian_tab import BrownianTab
from heatlab.ui.common import StatusBar, TopBar
from heatlab.ui.galton_tab import GaltonTab
from heatlab.ui.ideal_gas_tab import IdealGasTab
from heatlab.ui.maxwell_tab import MaxwellTab
from heatlab.ui.style import APP_STYLE, STATUS_LIVE, STATUS_PAUSED


class MainWindow(QMainWindow):
    """合并窗口：顶栏 + Tab 栏 + 三栏工作台 + 底部状态栏（对齐 Web 工作台）。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HeatLab · 热学科学计算可视化")
        self.resize(1500, 880)
        self.setStyleSheet(APP_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar(DEFAULT_SEED)
        self.top_bar.seedApplied.connect(self.rebuild_tabs)
        self.top_bar.pauseToggled.connect(self._set_global_pause)
        outer.addWidget(self.top_bar)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)

        self.status_bar = StatusBar()
        outer.addWidget(self.status_bar)

        self.rebuild_tabs(DEFAULT_SEED)
        self.tabs.currentChanged.connect(self._on_topic_changed)
        self._on_topic_changed(0)

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
        self.top_bar.seed_spin.setValue(seed)
        self.status_bar.set_seed(seed)

    def _set_global_pause(self, paused: bool) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            set_paused = getattr(widget, "set_animation_paused", None)
            if callable(set_paused):
                set_paused(paused)
        state = STATUS_PAUSED if paused else STATUS_LIVE
        text = "动画已暂停" if paused else "动画实时运行中"
        self.status_bar.set_state(state, text)
        self.status_bar.set_running(paused)
        self.top_bar.set_state(state)

    def _on_topic_changed(self, index: int) -> None:
        title = self.tabs.tabText(index) if 0 <= index < self.tabs.count() else ""
        self.status_bar.set_topic(title)
