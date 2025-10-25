import sys, requests
from PySide6 import QtWidgets, QtCore

FIREBASE_DB = "https://iot-group9-smart-parking-default-rtdb.firebaseio.com"
AUTH = ""           # optional - using a token for authentication
REQ_TIMEOUT = 5

def fb_url(path: str) -> str:
    url = f"{FIREBASE_DB}{path}.json"
    if AUTH:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}auth={AUTH}"
    return url
# Normalizing a license plate number
def normalize_plate(s: str) -> str:
    return s.strip().upper().replace("-", "").replace(" ", "")

def fb_get_all():
    r = requests.get(fb_url("/drivers_by_plate"), timeout=REQ_TIMEOUT)
    r.raise_for_status()
    j = r.json() or {}
    if not isinstance(j, dict): j = {}
    items = [(k, int(v.get("points", 0))) for k, v in j.items() if isinstance(v, dict)]
    items.sort(key=lambda x: x[1], reverse=True)
    return items

def fb_get_plate(p):
    r = requests.get(fb_url(f"/drivers_by_plate/{p}"), timeout=REQ_TIMEOUT)
    r.raise_for_status()
    j = r.json() or {}
    pts = int(j.get("points", 0)) if isinstance(j, dict) else 0
    return p, pts

class WorkerSignals(QtCore.QObject):
    done = QtCore.Signal(object, object)  # in the following format: (result, error)

class NetWorker(QtCore.QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()

    @QtCore.Slot()
    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.done.emit(res, None)
        except Exception as e:
            self.signals.done.emit(None, e)

class ScoresApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parking Leaderboard")
        self.resize(560, 600)

        self.topBtn = QtWidgets.QPushButton("Refresh Top 20")
        self.topTable = QtWidgets.QTableWidget(0, 2)
        self.topTable.setHorizontalHeaderLabels(["Plate", "Points"])
        self.topTable.horizontalHeader().setStretchLastSection(True)
        self.topTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Enter plates (comma/space)")
        self.lookupBtn = QtWidgets.QPushButton("Lookup")
        self.lookupTable = QtWidgets.QTableWidget(0, 2)
        self.lookupTable.setHorizontalHeaderLabels(["Plate", "Points"])
        self.lookupTable.horizontalHeader().setStretchLastSection(True)
        self.lookupTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.topBtn)
        lay.addWidget(self.topTable)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.input); row.addWidget(self.lookupBtn)
        lay.addLayout(row)
        lay.addWidget(self.lookupTable)
        lay.addWidget(self.status)

        self.pool = QtCore.QThreadPool.globalInstance()
        self.topBtn.clicked.connect(self.load_top_async)
        self.lookupBtn.clicked.connect(self.lookup_async)

        QtCore.QTimer.singleShot(0, self.load_top_async)
        self.auto = QtCore.QTimer(self)
        self.auto.timeout.connect(self.load_top_async)
        self.auto.start(10000)

    def set_error(self, e):
        self.status.setText("" if e is None else f"Error: {e}")

    def load_top_async(self):
        worker = NetWorker(fb_get_all)
        worker.signals.done.connect(self.on_top_loaded)
        self.pool.start(worker)

    @QtCore.Slot(object, object)
    def on_top_loaded(self, result, error):
        if error:
            self.set_error(error); return
        self.set_error(None)
        items = (result or [])[:20]
        self.topTable.setRowCount(len(items))
        for r, (plate, pts) in enumerate(items):
            self.topTable.setItem(r, 0, QtWidgets.QTableWidgetItem(plate))
            self.topTable.setItem(r, 1, QtWidgets.QTableWidgetItem(str(pts)))
        self.status.setText(f"Top {len(items)} loaded.")

    def lookup_async(self):
        raw = self.input.text().replace("  ", " ").replace(" ", ",")
        plates = [normalize_plate(p) for p in raw.split(",") if p.strip()]
        if not plates:
            self.lookupTable.setRowCount(0)
            self.status.setText("No plates entered."); return

        def fetch_many(ps):
            return [fb_get_plate(p) for p in ps]

        worker = NetWorker(fetch_many, plates)
        worker.signals.done.connect(self.on_lookup_loaded)
        self.pool.start(worker)

    @QtCore.Slot(object, object)
    def on_lookup_loaded(self, result, error):
        if error:
            self.set_error(error); return
        self.set_error(None)
        items = result or []
        self.lookupTable.setRowCount(len(items))
        for r, (plate, pts) in enumerate(items):
            self.lookupTable.setItem(r, 0, QtWidgets.QTableWidgetItem(plate))
            self.lookupTable.setItem(r, 1, QtWidgets.QTableWidgetItem(str(pts)))
        self.status.setText("Lookup done.")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = ScoresApp(); w.show()
    sys.exit(app.exec())
