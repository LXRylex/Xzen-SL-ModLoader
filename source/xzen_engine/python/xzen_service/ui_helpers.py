from __future__ import annotations

from dataclasses import dataclass
from PyQt5 import QtCore, QtGui, QtWidgets


@dataclass
class UiHelpers:
    bg_dark: str
    text: str

    def format_mod_count_label(self, mod_count: int | None) -> str:
        if mod_count is None:
            return "Unknown mods"
        count = max(0, int(mod_count))
        return f"{count} mod" if count == 1 else f"{count} mods"

    def style_compact_message_box(self, box: QtWidgets.QMessageBox) -> QtWidgets.QMessageBox:
        button_style = """
            QPushButton {
                background-color: #e8e8e8;
                color: #000000;
                border: 1px solid #f4f4f4;
                border-radius: 4px;
                padding: 5px 12px;
                min-width: 72px;
                min-height: 28px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: #f3f3f3;
            }
            QPushButton:pressed {
                background-color: #dcdcdc;
            }
        """
        box.setWindowFlags((box.windowFlags() | QtCore.Qt.WindowCloseButtonHint) & ~QtCore.Qt.WindowContextHelpButtonHint)
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {self.bg_dark};
            }}
            QMessageBox QLabel {{
                color: {self.text};
                font-size: 12px;
            }}
        """)
        for button in box.buttons():
            button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            button.setStyleSheet(button_style)
            button.setMinimumSize(72, 28)
        return box

    def show_compact_message_box(
        self,
        parent,
        title: str,
        text: str,
        *,
        icon=QtWidgets.QMessageBox.Information,
        buttons=QtWidgets.QMessageBox.Ok,
        default_button=QtWidgets.QMessageBox.NoButton,
    ) -> int:
        box = QtWidgets.QMessageBox(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QtWidgets.QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        self.style_compact_message_box(box)
        return box.exec_()

    def show_compact_warning(self, parent, title: str, text: str) -> int:
        return self.show_compact_message_box(parent, title, text, icon=QtWidgets.QMessageBox.Warning)

    def show_compact_information(self, parent, title: str, text: str) -> int:
        return self.show_compact_message_box(parent, title, text, icon=QtWidgets.QMessageBox.Information)

    def show_compact_question(
        self,
        parent,
        title: str,
        text: str,
        *,
        buttons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        default_button=QtWidgets.QMessageBox.No,
    ) -> int:
        return self.show_compact_message_box(
            parent,
            title,
            text,
            icon=QtWidgets.QMessageBox.Question,
            buttons=buttons,
            default_button=default_button,
        )
