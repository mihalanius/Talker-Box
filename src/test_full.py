import sys
import traceback

log = open("D:\\OpenCode_Arhive\\Talker Box\\src\\crash.log", "w", encoding="utf-8")

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    log.write("Creating MainWindow...\n")
    log.flush()

    from main import MainWindow
    window = MainWindow()

    log.write("MainWindow created, showing...\n")
    log.flush()
    window.show()

    log.write("Window shown successfully!\n")
    log.flush()

    QTimer.singleShot(5000, app.quit)
    app.exec()

    log.write("App exited normally\n")
except Exception:
    traceback.print_exc(file=log)
finally:
    log.close()
