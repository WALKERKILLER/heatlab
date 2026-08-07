"""Shared Qt stylesheet for HeatLab windows."""

from __future__ import annotations

APP_STYLE = """
QMainWindow, QWidget { background: #0b0f14; color: #dbe7f3; font-size: 14px; }
QToolBar { background: #101720; border: none; spacing: 8px; padding: 8px; }
QTabWidget::pane { border: 1px solid #263241; border-radius: 8px; }
QTabBar::tab { background: #111821; color: #8ea1b5; padding: 10px 20px; margin-right: 3px; }
QTabBar::tab:selected { color: #dbe7f3; background: #172330; border-bottom: 2px solid #43d7c5; }
QFrame#controlPanel { background: #111821; border: 1px solid #263241; border-radius: 12px; }
QLabel#panelHeading { font-size: 18px; font-weight: 700; color: #ffffff; padding-bottom: 4px; }
QLabel#valueLabel { color: #43d7c5; font-weight: 700; }
QLabel#metricText { background: #0d141c; border: 1px solid #263241; border-radius: 8px; padding: 10px; line-height: 1.35; }
QLabel#noteText { color: #8ea1b5; font-size: 12px; }
QLabel#formulaText { color: #b9c9d9; background: #0d141c; border-radius: 8px; padding: 9px; }
QPushButton { background: #1b2937; border: 1px solid #31445a; border-radius: 8px; padding: 8px 12px; min-height: 20px; }
QPushButton:hover { background: #223447; }
QPushButton:checked { background: #25493f; border-color: #43d7c5; }
QPushButton:disabled { color: #5f7082; background: #141c25; }
QSlider::groove:horizontal { height: 5px; background: #263241; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #43d7c5; border-radius: 2px; }
QSlider::handle:horizontal { background: #e9ffff; border: 2px solid #43d7c5; width: 16px; margin: -6px 0; border-radius: 8px; }
QSpinBox { background: #111821; border: 1px solid #31445a; border-radius: 6px; padding: 5px; }
"""
