"""Shared Qt stylesheet for HeatLab windows, matching ``Simulation/*.py``."""

from __future__ import annotations

APP_STYLE = """
/* ---- 全局表面（Simulation 黑色实验台） ---- */
QMainWindow { background: #080808; }
QWidget { color: #E5E5E5; font-size: 12px; font-family: "Segoe UI", "Microsoft YaHei"; }
QToolTip { background: #171717; color: #E5E5E5; border: 1px solid #333333; padding: 4px; }

/* ---- 顶栏（title bar） ---- */
QWidget#topBar {
  background: #080808;
  border-bottom: 1px solid #333333;
}
QLabel#brandName { color: #ffffff; font-size: 13px; font-weight: 600; }
QLabel#brandDivider { color: #777777; font-size: 13px; }
QLabel#brandProduct { color: #A8A8A8; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#brandSub { color: #A8A8A8; font-size: 10px; }

QWidget#commandTray {
  background: #171717;
  border: 1px solid #333333;
  border-radius: 3px;
}
QLabel#trayLabel { color: #A8A8A8; font-size: 11px; }
QSpinBox#seedSpin {
  background: #202020;
  color: #E3C15A;
  border: 1px solid #333333;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: "Consolas", "Cascadia Mono", monospace;
  min-width: 96px;
}
QSpinBox#seedSpin:focus { border-color: #4FA3D9; }
QPushButton#applyButton {
  background: #4FA3D9;
  color: #ffffff;
  border: none;
  border-radius: 3px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}
QPushButton#applyButton:hover { background: #69B5E5; }
QPushButton#applyButton:pressed { background: #387FAE; }

QWidget#runCluster {
  background: #171717;
  border: 1px solid #333333;
  border-left: 3px solid #65C68A;
  border-radius: 3px;
}
QWidget#runCluster[paused="true"] { border-left: 3px solid #E3C15A; background: #171717; }
QWidget#runCluster[error="true"] { border-left: 3px solid #D66A6A; background: #171717; }
QLabel#runKicker { color: #A8A8A8; font-size: 8px; font-weight: 700; letter-spacing: 1px; }
QLabel#runState { color: #65C68A; font-size: 11px; font-weight: 600; }
QWidget#runCluster[paused="true"] QLabel#runState { color: #E3C15A; }
QWidget#runCluster[error="true"] QLabel#runState { color: #D66A6A; }
QPushButton#transportButton {
  background: #252525;
  color: #E5E5E5;
  border: none;
  border-radius: 3px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}
QPushButton#transportButton:hover { background: #333333; }
QPushButton#transportButton:checked { background: #252525; color: #E3C15A; }

/* ---- tab bar ---- */
QTabWidget::pane { border: none; }
QTabWidget::tab-bar { alignment: left; }
QTabBar { background: #121212; border-bottom: 1px solid #333333; }
QTabBar::tab {
  background: #171717;
  color: #A8A8A8;
  padding: 6px 16px 8px;
  margin-right: 0;
  border: none;
  border-right: 1px solid #333333;
  min-width: 120px;
}
QTabBar::tab:hover { background: #252525; color: #E5E5E5; }
QTabBar::tab:selected {
  background: #080808;
  color: #ffffff;
  border-top: 2px solid #4FA3D9;
  font-weight: 600;
}

/* ---- 工作台三栏 ---- */
QFrame#controlPanel {
  background: #121212;
  border: none;
  border-right: 1px solid #333333;
}
QLabel#panelHeading { font-size: 14px; font-weight: 600; color: #ffffff; }
QLabel#panelKicker { color: #A8A8A8; font-size: 11px; font-weight: 600; }
QLabel#panelLead { color: #A8A8A8; font-size: 11px; }

QWidget#cardChrome {
  background: #171717;
  border-bottom: 1px solid #333333;
}
QLabel#cardTitle { color: #E5E5E5; font-size: 12px; font-weight: 600; }
QLabel#cardBadge {
  color: #A8A8A8;
  font-size: 10px;
  border: 1px solid #333333;
  border-radius: 3px;
  padding: 1px 6px;
}
QFrame#sceneCard, QFrame#chartCard { background: #080808; border: none; }
QFrame#sceneCard { border-right: 1px solid #333333; }

/* ---- 控件 ---- */
QLabel#valueLabel { color: #E3C15A; font-family: "Consolas", monospace; font-weight: 500; }
QLabel#metricText {
  color: #E5E5E5;
  background: #171717;
  border: 1px solid #333333;
  border-radius: 3px;
  padding: 8px 10px;
  font-family: "Consolas", "Microsoft YaHei", monospace;
  font-size: 12px;
}
QLabel#metricKey { color: #A8A8A8; font-size: 12px; }
QLabel#metricValue { color: #ffffff; font-family: "Consolas", monospace; font-size: 12px; }

QPushButton {
  background: #252525;
  color: #E5E5E5;
  border: 1px solid #333333;
  border-radius: 3px;
  padding: 5px 12px;
  min-height: 18px;
  font-size: 12px;
}
QPushButton:hover { background: #333333; color: #ffffff; }
QPushButton:pressed { background: #3a3a3a; }
QPushButton:checked { background: #4FA3D9; color: #ffffff; border-color: transparent; }
QPushButton:disabled { color: #777777; background: #171717; }

QPushButton#primaryButton { background: #4FA3D9; color: #ffffff; font-weight: 600; }
QPushButton#primaryButton:hover { background: #69B5E5; }

QSlider::groove:horizontal {
  height: 4px;
  background: #353535;
  border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #4FA3D9; border-radius: 2px; }
QSlider::handle:horizontal {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 60%);
  width: 14px;
  margin: -6px 0;
  border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #69B5E5; }
QSlider:disabled::sub-page:horizontal { background: #5a5a5a; }
QSlider:disabled::handle:horizontal { background: #8a8a8a; }

QSpinBox {
  background: #202020;
  color: #E3C15A;
  border: 1px solid #333333;
  border-radius: 3px;
  padding: 3px 6px;
  min-height: 18px;
}

/* ---- 底部状态栏 ---- */
QWidget#statusBar {
  background: #151515;
  color: #A8A8A8;
  border: none;
}
QWidget#statusBar[paused="true"] { background: #151515; }
QWidget#statusBar[error="true"] { background: #151515; }
QLabel#statusItem { color: #A8A8A8; font-size: 12px; }
QLabel#statusMono { color: #A8A8A8; font-size: 11px; font-family: "Consolas", monospace; }
"""

# 状态栏 / 运行簇的状态取值（live / paused / error）
STATUS_LIVE = "live"
STATUS_PAUSED = "paused"
STATUS_ERROR = "error"
