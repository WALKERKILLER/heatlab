"""Shared Qt stylesheet for HeatLab windows (VS Code Dark+ workbench).

配色与布局令牌与 Web 版 (app.css) 对齐：editor / sidebar / titlebar / tabbar /
statusbar 使用同一套深色表面，控件使用同一组强调色。Qt QSS 能力有限，
无法完全复刻 CSS 的渐变、阴影与动画，因此以「表面配色 + 布局 + 交互」对齐为准。
"""

from __future__ import annotations

APP_STYLE = """
/* ---- 全局表面（VS Code Dark+） ---- */
QMainWindow { background: #333333; }
QWidget { color: #cccccc; font-size: 13px; font-family: "Segoe UI", "Microsoft YaHei"; }
QToolTip { background: #252526; color: #cccccc; border: 1px solid #3e3e42; padding: 4px; }

/* ---- 顶栏（title bar） ---- */
QWidget#topBar {
  background: #3c3c3c;
  border-bottom: 1px solid #2b2b2b;
}
QLabel#brandName { color: #ffffff; font-size: 13px; font-weight: 600; }
QLabel#brandDivider { color: rgba(255, 255, 255, 45%); font-size: 13px; }
QLabel#brandProduct { color: #9d9d9d; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#brandSub { color: #9d9d9d; font-size: 10px; }

QWidget#commandTray {
  background: #2d2d2d;
  border: 1px solid #3e3e42;
  border-radius: 8px;
}
QLabel#trayLabel { color: #9d9d9d; font-size: 11px; }
QSpinBox#seedSpin {
  background: #3c3c3c;
  color: #ffffff;
  border: 1px solid #3e3e42;
  border-radius: 4px;
  padding: 2px 6px;
  font-family: "Consolas", "Cascadia Mono", monospace;
  min-width: 96px;
}
QSpinBox#seedSpin:focus { border-color: #3794ff; }
QPushButton#applyButton {
  background: #007acc;
  color: #ffffff;
  border: none;
  border-radius: 5px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}
QPushButton#applyButton:hover { background: #1c97ea; }
QPushButton#applyButton:pressed { background: #005f9e; }

QWidget#runCluster {
  background: #2d2d2d;
  border: 1px solid #3e3e42;
  border-left: 3px solid #89d185;
  border-radius: 8px;
}
QWidget#runCluster[paused="true"] { border-left: 3px solid #e2c35a; background: #33291b; }
QWidget#runCluster[error="true"] { border-left: 3px solid #f48771; background: #331c16; }
QLabel#runKicker { color: #9d9d9d; font-size: 8px; font-weight: 700; letter-spacing: 1px; }
QLabel#runState { color: #89d185; font-size: 11px; font-weight: 600; }
QWidget#runCluster[paused="true"] QLabel#runState { color: #e2c35a; }
QWidget#runCluster[error="true"] QLabel#runState { color: #f48771; }
QPushButton#transportButton {
  background: #1e3a5c;
  color: #cfe7ff;
  border: none;
  border-radius: 5px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}
QPushButton#transportButton:hover { background: #29538a; }
QPushButton#transportButton:checked { background: #6b4a1b; color: #ffe6b0; }

/* ---- tab bar ---- */
QTabWidget::pane { border: none; }
QTabWidget::tab-bar { alignment: left; }
QTabBar { background: #2d2d2d; border-bottom: 1px solid #2b2b2b; }
QTabBar::tab {
  background: #2d2d2d;
  color: #9d9d9d;
  padding: 6px 16px 8px;
  margin-right: 0;
  border: none;
  border-right: 1px solid #2b2b2b;
  min-width: 120px;
}
QTabBar::tab:hover { background: #323232; color: #cccccc; }
QTabBar::tab:selected {
  background: #1e1e1e;
  color: #ffffff;
  border-top: 2px solid #007acc;
  font-weight: 600;
}

/* ---- 工作台三栏 ---- */
QFrame#controlPanel {
  background: #252526;
  border: none;
  border-right: 1px solid #2b2b2b;
}
QLabel#panelHeading { font-size: 14px; font-weight: 600; color: #ffffff; }
QLabel#panelKicker { color: #9d9d9d; font-size: 11px; font-weight: 600; }
QLabel#panelLead { color: #9d9d9d; font-size: 11px; }

QWidget#cardChrome {
  background: #252526;
  border-bottom: 1px solid #2b2b2b;
}
QLabel#cardTitle { color: #cccccc; font-size: 12px; font-weight: 600; }
QLabel#cardBadge {
  color: #9d9d9d;
  font-size: 10px;
  border: 1px solid #3e3e42;
  border-radius: 3px;
  padding: 1px 6px;
}
QFrame#sceneCard, QFrame#chartCard { background: #1e1e1e; border: none; }
QFrame#sceneCard { border-right: 1px solid #2b2b2b; }

/* ---- 控件 ---- */
QLabel#valueLabel { color: #ffffff; font-family: "Consolas", monospace; font-weight: 500; }
QLabel#metricText {
  color: #cccccc;
  background: #1e1e1e;
  border: 1px solid #3e3e42;
  border-radius: 4px;
  padding: 8px 10px;
  font-family: "Consolas", "Microsoft YaHei", monospace;
  font-size: 12px;
}
QLabel#metricKey { color: #9d9d9d; font-size: 12px; }
QLabel#metricValue { color: #ffffff; font-family: "Consolas", monospace; font-size: 12px; }

QPushButton {
  background: #3c3c3c;
  color: #cccccc;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 5px 12px;
  min-height: 18px;
  font-size: 12px;
}
QPushButton:hover { background: #454545; color: #ffffff; }
QPushButton:pressed { background: #3a3a3a; }
QPushButton:checked { background: #007acc; color: #ffffff; border-color: transparent; }
QPushButton:disabled { color: #5f7082; background: #252526; }

QPushButton#primaryButton { background: #007acc; color: #ffffff; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1c97ea; }

QSlider::groove:horizontal {
  height: 4px;
  background: #5a5a5a;
  border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #3794ff; border-radius: 2px; }
QSlider::handle:horizontal {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 60%);
  width: 14px;
  margin: -6px 0;
  border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #1c97ea; }
QSlider:disabled::sub-page:horizontal { background: #5a5a5a; }
QSlider:disabled::handle:horizontal { background: #8a8a8a; }

QSpinBox {
  background: #3c3c3c;
  color: #ffffff;
  border: 1px solid #3e3e42;
  border-radius: 4px;
  padding: 3px 6px;
  min-height: 18px;
}

/* ---- 底部状态栏 ---- */
QWidget#statusBar {
  background: #0b6aa2;
  color: #ffffff;
  border: none;
}
QWidget#statusBar[paused="true"] { background: #a35a1f; }
QWidget#statusBar[error="true"] { background: #a1260d; }
QLabel#statusItem { color: #ffffff; font-size: 12px; }
QLabel#statusMono { color: #ffffff; font-size: 11px; font-family: "Consolas", monospace; }
"""

# 状态栏 / 运行簇的状态取值（live / paused / error）
STATUS_LIVE = "live"
STATUS_PAUSED = "paused"
STATUS_ERROR = "error"
