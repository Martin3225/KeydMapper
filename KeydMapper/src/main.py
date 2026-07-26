"""Main entry point for the KeydMapper application."""

import os
import shutil
import sys

from constants import LAYOUTS_PATH, RES_PATH
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow


def main() -> None:
    """Entry point for the KeydMapper application."""

    print("Starting KeydMapper...")
    app = QApplication(sys.argv)

    if not shutil.which("keyd"):
        print(
            "The 'keyd' application was not found on your system. You won't be able to record keys or apply configurations."
        )

    # Initialize basic layouts
    os.makedirs(LAYOUTS_PATH, exist_ok=True)
    for res_file in ["keyboard.layout", "mouse.layout"]:
        src = os.path.join(RES_PATH, res_file)
        dst = os.path.join(LAYOUTS_PATH, res_file)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy(src, dst)

    window = MainWindow()

    if not shutil.which("keyd"):
        QMessageBox.warning(
            window,
            "Missing keyd",
            "The 'keyd' application was not found on your system.\n\n"
            "You won't be able to record keys or apply configurations.",
        )

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
