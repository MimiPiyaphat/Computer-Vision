"""Explicit one-time download; camera startup never silently downloads weights."""

from pathlib import Path
import urllib.request
from config import IDENTITY_MODEL_PATH
from src.face_identity import MODEL_URL, FaceIdentity


def main():
    path = Path(IDENTITY_MODEL_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(".download")
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as source, temporary.open("wb") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    model = FaceIdentity(path)
    print("Identity model ready:", model.signature)
    model.close()


if __name__ == "__main__":
    main()
