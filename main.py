"""FormassyBridge 入口

运行方式：
  python main.py           开发环境
  FormassyBridge.exe       PyInstaller 打包后
"""
import tkinter as tk

from src.utils.logger import setup_logger
from src.app.gui.main_window import MainWindow


def main() -> None:
    setup_logger()
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
