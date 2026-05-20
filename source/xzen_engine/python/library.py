from PyQt5 import QtCore, QtGui, QtWidgets
from pathlib import Path
import os, sys

# ---------- EXE-safe project root ----------
def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = project_root()
# -----------------------------------------

# Paths
MODS_ROOT = PROJECT_ROOT / "source" / "mods" / "modded"

# Categories
CATEGORIES = {
    "All": None,
    "Characters": "characters",
    "Emotes": "emoticon",
    "UI": "ui_mods"
}

# ===== Stealth Theme Colors =====
ACCENT   = "#ffffff"   
BG_DARK  = "#6F00CA"   
PANEL    = "#0a0a0a"   
TEXT     = "#eeeeee"   
TEXT_DIM = "#888888"   
BORDER   = "#333333"

# Qt Compat
QtNoFocus = getattr(QtCore.Qt, "NoFocus", getattr(QtCore.Qt.FocusPolicy, "NoFocus"))

# Custom Tree Widget to force Double Click behavior
class FileTreeWidget(QtWidgets.QTreeWidget):
    def mouseDoubleClickEvent(self, event):
        # Override default double-click expansion
        item = self.itemAt(event.pos())
        if item:
            # Emit our custom signal instead of expanding
            self.itemDoubleClicked.emit(item, 0)
        # Do NOT call super().mouseDoubleClickEvent(event) 
        # to prevent the default expand/collapse behavior.

class LibraryPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LibraryRoot")
        self.setStyleSheet(self._qss())
        
        self.current_filter = "All"
        self._build_ui()
        QtCore.QTimer.singleShot(100, self.refresh_list)

    def _build_ui(self):
        # Header
        title = QtWidgets.QLabel("Installed Mods")
        title.setObjectName("headerTitle")
        
        sub = QtWidgets.QLabel("Browse files and folders in source/mods/modded")
        sub.setObjectName("subTitle")

        # Filter Bar
        self.filter_layout = QtWidgets.QHBoxLayout()
        self.filter_layout.setSpacing(10)
        self.filter_btns = {}

        for name in ["All", "Characters", "Emotes", "UI"]:
            btn = QtWidgets.QPushButton(name)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setFocusPolicy(QtNoFocus)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, n=name: self.change_filter(n))
            self.filter_layout.addWidget(btn)
            self.filter_btns[name] = btn
        
        self.filter_layout.addStretch()
        self.filter_btns["All"].setChecked(True)

        # Main Tree Widget (Using Custom Class)
        self.mod_tree = FileTreeWidget()
        self.mod_tree.setHeaderHidden(True)
        self.mod_tree.setFocusPolicy(QtNoFocus)
        self.mod_tree.setAnimated(True)
        self.mod_tree.setIndentation(20)
        
        # 1. Single Click -> Expand/Collapse
        self.mod_tree.itemClicked.connect(self.toggle_expand)
        
        # 2. Double Click -> Open Path (Handled by custom class + this slot)
        self.mod_tree.itemDoubleClicked.connect(self.open_item)

        # Refresh Button
        btn_refresh = QtWidgets.QPushButton("Refresh List")
        btn_refresh.setCursor(QtCore.Qt.PointingHandCursor)
        btn_refresh.setFocusPolicy(QtNoFocus)
        btn_refresh.setObjectName("GhostBtn")
        btn_refresh.clicked.connect(self.refresh_list)

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.addStretch()
        bottom_bar.addWidget(btn_refresh)

        # Layout Assembly
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        
        main_layout.addWidget(title)
        main_layout.addWidget(sub)
        main_layout.addSpacing(5)
        main_layout.addLayout(self.filter_layout)
        main_layout.addWidget(self.mod_tree)
        main_layout.addLayout(bottom_bar)

    def change_filter(self, filter_name):
        self.current_filter = filter_name
        for name, btn in self.filter_btns.items():
            btn.setChecked(name == filter_name)
        self.refresh_list()

    def refresh_list(self):
        self.mod_tree.clear()
        
        target_folders = []
        if self.current_filter == "All":
            target_folders = ["characters", "emoticon", "ui_mods"]
        else:
            folder_name = CATEGORIES.get(self.current_filter)
            if folder_name:
                target_folders = [folder_name]

        found_any = False
        
        for folder_name in target_folders:
            path = MODS_ROOT / folder_name
            if not path.exists():
                continue

            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item_path in items:
                    self.add_tree_item(self.mod_tree, item_path)
                    found_any = True
            except Exception as e:
                print(f"Error scanning {path}: {e}")

        if not found_any:
            item = QtWidgets.QTreeWidgetItem(self.mod_tree)
            item.setText(0, "No mods found for this category.")
            item.setFlags(QtCore.Qt.NoItemFlags)

    def add_tree_item(self, parent, path: Path):
        item = QtWidgets.QTreeWidgetItem(parent)
        
        display_name = path.name
        item.setText(0, display_name)
        item.setData(0, QtCore.Qt.UserRole, str(path))
        
        if path.is_dir():
            item.setIcon(0, self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))
            try:
                children = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for child in children:
                    self.add_tree_item(item, child)
            except PermissionError:
                pass
        else:
            item.setIcon(0, self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon))

    def toggle_expand(self, item, column):
        # Single click toggles expansion
        if item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def open_item(self, item, column):
        # Double click opens file/folder in Explorer
        path_str = item.data(0, QtCore.Qt.UserRole)
        if not path_str: 
            return
        path = Path(path_str)
        if path.exists():
            os.startfile(path)

    def _qss(self) -> str:
        return f"""
        QWidget#LibraryRoot {{
            background: {BG_DARK};
            color: {TEXT};
            font-family: "Segoe UI", system-ui, sans-serif;
            font-size: 13px;
        }}
        
        QLabel#headerTitle {{
            font-size: 20px;
            font-weight: 700;
            color: {TEXT};
        }}
        
        QLabel#subTitle {{
            color: {TEXT_DIM};
            font-size: 13px;
        }}

        /* Filter Buttons */
        QPushButton {{
            background: transparent;
            color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 6px 16px;
            border-radius: 16px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: #111111;
            color: {TEXT};
            border-color: {TEXT_DIM};
        }}
        QPushButton:checked {{
            background: {TEXT};
            color: {BG_DARK};
            border: 1px solid {TEXT};
        }}

        QPushButton#GhostBtn {{
            border-radius: 4px;
            padding: 6px 12px;
        }}

        /* Tree Widget */
        QTreeWidget {{
            background: {PANEL};
            border: 1px solid {BORDER};
            border-radius: 4px;
            padding: 8px;
            outline: none;
        }}
        QTreeWidget::item {{
            padding: 6px;
            color: {TEXT};
            border: none;
            border-radius: 4px;
        }}
        
        /* HOVER: Light Grey background */
        QTreeWidget::item:hover {{
            background: #2a2a2a; 
            color: #ffffff;
        }}

        /* SELECTED: Dark Grey background (Stealth) */
        QTreeWidget::item:selected {{
            background: #222222;
            color: #ffffff;
            border: 1px solid #444444;
        }}
        
        /* NO ARROWS */
        QTreeView::branch {{
            image: none;
            border-image: none;
            background: transparent;
        }}
        """
