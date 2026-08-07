"""Single-topic desktop windows (no multi-tab chrome)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QSpinBox, QToolBar, QWidget

from heatlab.constants import DEFAULT_SEED
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager
from heatlab.ui.brownian_tab import BrownianTab
from heatlab.ui.galton_tab import GaltonTab
from heatlab.ui.ideal_gas_tab import IdealGasTab
from heatlab.ui.maxwell_tab import MaxwellTab
from heatlab.ui.style import APP_STYLE

TOPIC_SPECS: dict[str, dict[str, str]] = {
    "ideal-gas": {
        "title": "HeatLab · 理想气体",
        "stream": "ideal-gas",
        "label": "理想气体",
    },
    "brownian": {
        "title": "HeatLab · 布朗运动",
        "stream": "brownian",
        "label": "布朗运动",
    },
    "maxwell": {
        "title": "HeatLab · 麦克斯韦分布",
        "stream": "maxwell",
        "label": "麦克斯韦分布",
    },
    "galton": {
        "title": "HeatLab · 伽尔顿板",
        "stream": "galton",
        "label": "伽尔顿板",
    },
}


def build_topic_widget(topic: str, seed: int) -> QWidget:
    if topic not in TOPIC_SPECS:
        raise ValueError(f"unknown topic: {topic}")
    manager = RandomManager(seed)
    stream_name = TOPIC_SPECS[topic]["stream"]
    rng = manager.stream(stream_name)
    if topic == "ideal-gas":
        return IdealGasTab(IdealGasModel(rng))
    if topic == "brownian":
        return BrownianTab(BrownianModel(rng))
    if topic == "maxwell":
        return MaxwellTab(MaxwellModel(rng))
    return GaltonTab(GaltonModel(rng))


class TopicWindow(QMainWindow):
    """Standalone window hosting exactly one HeatLab topic."""

    def __init__(self, topic: str, seed: int = DEFAULT_SEED) -> None:
        super().__init__()
        if topic not in TOPIC_SPECS:
            raise ValueError(f"unknown topic: {topic}")
        self.topic = topic
        self.setWindowTitle(TOPIC_SPECS[topic]["title"])
        self.resize(1280, 780)
        self.setStyleSheet(APP_STYLE)
        self._create_toolbar()
        self.rebuild(seed)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("设置", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.addWidget(QLabel("随机种子"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setValue(DEFAULT_SEED)
        self.seed_spin.setMinimumWidth(130)
        toolbar.addWidget(self.seed_spin)
        apply_button = QPushButton("应用并重置")
        apply_button.clicked.connect(lambda: self.rebuild(self.seed_spin.value()))
        toolbar.addWidget(apply_button)

    def rebuild(self, seed: int) -> None:
        self.seed_spin.setValue(seed)
        old = self.centralWidget()
        if old is not None:
            old.deleteLater()
        self.setCentralWidget(build_topic_widget(self.topic, seed))
