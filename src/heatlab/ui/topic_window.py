"""Single-topic desktop windows (top bar + three-column workbench + status bar)."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from heatlab.constants import DEFAULT_SEED
from heatlab.models import BrownianModel, GaltonModel, IdealGasModel, MaxwellModel
from heatlab.randomness import RandomManager
from heatlab.ui.brownian_tab import BrownianTab
from heatlab.ui.common import StatusBar, TopBar
from heatlab.ui.galton_tab import GaltonTab
from heatlab.ui.ideal_gas_tab import IdealGasTab
from heatlab.ui.maxwell_tab import MaxwellTab
from heatlab.ui.style import APP_STYLE, STATUS_LIVE, STATUS_PAUSED

TOPIC_SPECS: dict[str, dict[str, str]] = {
    "ideal-gas": {
        "title": "HeatLab · 热力学",
        "stream": "ideal-gas",
        "label": "热力学",
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
        self.resize(1400, 860)
        self.setStyleSheet(APP_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar(seed)
        self.top_bar.seedApplied.connect(self.rebuild)
        self.top_bar.pauseToggled.connect(self._set_global_pause)
        outer.addWidget(self.top_bar)

        self.body = QWidget()
        outer.addWidget(self.body, 1)

        self.status_bar = StatusBar()
        outer.addWidget(self.status_bar)

        self.rebuild(seed)

    def rebuild(self, seed: int) -> None:
        self.top_bar.seed_spin.setValue(seed)
        self._current_tab = build_topic_widget(self.topic, seed)

        while self.body.layout() is not None:
            old_layout = self.body.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._current_tab)

        self.status_bar.set_seed(seed)
        self.status_bar.set_topic(TOPIC_SPECS[self.topic]["label"])

    def _set_global_pause(self, paused: bool) -> None:
        set_paused = getattr(self._current_tab, "set_animation_paused", None)
        if callable(set_paused):
            set_paused(paused)
        state = STATUS_PAUSED if paused else STATUS_LIVE
        text = "动画已暂停" if paused else "动画实时运行中"
        self.status_bar.set_state(state, text)
        self.status_bar.set_running(paused)
        self.top_bar.set_state(state)
