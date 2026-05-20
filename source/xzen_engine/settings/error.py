# error.py (compact)
# Usage: python error.py "Title" "Message"

import sys
from PyQt5 import QtCore, QtGui, QtWidgets

# stealth theme
ACCENT="#fff"; BG="#050505"; PANEL="#0a0a0a"; TEXT="#eee"; DIM="#888"; BORDER="#333"; RED="#ff6b6b"

class Popup(QtWidgets.QDialog):
    def __init__(self, title, msg):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 220)

        root = QtWidgets.QVBoxLayout(self); root.setContentsMargins(0,0,0,0)

        f = QtWidgets.QFrame(objectName="F")
        f.setStyleSheet(f"""
        QFrame#F{{background:{PANEL};border:1px solid {BORDER};border-radius:10px;}}
        QLabel#T{{color:{TEXT};font-weight:800;font-size:15px;}}
        QLabel#M{{color:{DIM};font-size:12px;}}
        QPushButton#X{{background:transparent;border:1px solid {BORDER};color:{TEXT};
                      min-width:32px;max-width:32px;min-height:26px;max-height:26px;
                      border-radius:6px;font-weight:900;}}
        QPushButton#X:hover{{border-color:{RED};background:rgba(255,107,107,0.12);}}
        QPushButton#OK{{background:{TEXT};color:{BG};border:none;padding:8px 16px;
                        border-radius:6px;font-weight:800;min-width:90px;}}
        QPushButton#OK:hover{{background:#fff;}}
        """)

        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(18,18,18,16); lay.setSpacing(12)

        top = QtWidgets.QHBoxLayout(); top.setContentsMargins(0,0,0,0)
        lab_t = QtWidgets.QLabel(title, objectName="T")
        btn_x = QtWidgets.QPushButton("×", objectName="X"); btn_x.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_x.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn_x.clicked.connect(self.accept)
        top.addWidget(lab_t, 1); top.addWidget(btn_x, 0)
        lay.addLayout(top)

        lab_m = QtWidgets.QLabel(msg, objectName="M"); lab_m.setWordWrap(True)
        lay.addWidget(lab_m, 1)

        row = QtWidgets.QHBoxLayout(); row.addStretch(1)
        ok = QtWidgets.QPushButton("OK", objectName="OK"); ok.setFocusPolicy(QtCore.Qt.NoFocus)
        ok.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)

        sh = QtWidgets.QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(34); sh.setColor(QtGui.QColor(0,0,0,170)); sh.setOffset(0,10)
        f.setGraphicsEffect(sh)

        root.addWidget(f)

        # drag anywhere
        self._dp = None
        f.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.MouseButtonPress and ev.button() == QtCore.Qt.LeftButton:
            self._dp = ev.globalPos() - self.frameGeometry().topLeft(); return True
        if ev.type() == QtCore.QEvent.MouseMove and self._dp and (ev.buttons() & QtCore.Qt.LeftButton):
            self.move(ev.globalPos() - self._dp); return True
        if ev.type() == QtCore.QEvent.MouseButtonRelease:
            self._dp = None; return True
        return False

def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "Soemthing went wrong"
    msg   = sys.argv[2] if len(sys.argv) > 2 else "Uhhh ye something went wrong...xD"
    app = QtWidgets.QApplication(sys.argv)
    Popup(title, msg).exec_()

if __name__ == "__main__":
    main()
