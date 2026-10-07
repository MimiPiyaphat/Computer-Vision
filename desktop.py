"""Run `python desktop.py --preview` to work on the UI without a camera."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="StrokeVision desktop dashboard")
    parser.add_argument("--preview", action="store_true", help="Use simulated data; no camera, models, or logs")
    parser.add_argument("--research", action="store_true", help="Use visibly labeled, unvalidated university demonstration rules")
    args = parser.parse_args()
    # CLI help stays available without loading the desktop toolkit.
    import tkinter as tk
    from ui.app import Dashboard
    # Model and feature-store configuration uses paths relative to the project.
    os.chdir(Path(__file__).resolve().parent)
    root = tk.Tk()
    Dashboard(root, preview=args.preview, research=args.research)
    root.mainloop()


if __name__ == "__main__":
    main()
