"""Panda Training Standalone entry point."""

import sys

from panda.ui.main_window import MainWindow, create_application


def main() -> int:
    app = create_application(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
