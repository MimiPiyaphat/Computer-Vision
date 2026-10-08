"""Import user-supplied ZIPs into a private, pseudonymous demo dataset."""

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

import cv2
import numpy as np

ACTION_NAMES = {'หน้านิ่ง': 'neutral', 'ยิ้ม': 'smile', 'กระพริบตา': 'blink', 'ยกแขน': 'arms'}


def action_from_name(name):
    stem = re.sub(r'\s*\(\d+\)$', '', PurePosixPath(name).stem).strip()
    return ACTION_NAMES.get(stem, 'unreviewed')


def probe(path):
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError(f'Cannot open {path.name}')
        fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not all(math.isfinite(v) and v > 0 for v in (fps, frames)):
            raise ValueError(f'Missing timing metadata: {path.name}')
        previews = []
        for ratio in (.2, .5, .8):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((frames - 1) * ratio))
            ok, image = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode preview: {path.name}')
            h, w = image.shape[:2]
            scale = min(320 / w, 220 / h)
            resized = cv2.resize(image, (round(w * scale), round(h * scale)))
            tile = np.zeros((250, 320, 3), np.uint8)
            y, x = (220 - resized.shape[0]) // 2, (320 - resized.shape[1]) // 2
            tile[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
            cv2.putText(tile, f'{path.stem} {ratio * frames / fps:.1f}s', (5, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
            previews.append(tile)
        return dict(fps=fps, declared_frames=int(frames), duration_sec=frames / fps,
                    width=w, height=h), np.hstack(previews)
    finally:
        cap.release()


def prepare(archives, output):
    archives, output = Path(archives), Path(output)
    sources = sorted(archives.glob('p[0-9][0-9].zip'))
    if not sources or output.exists():
        raise ValueError('Need pseudonymous pNN.zip files and a new output directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    rows, mapping, seen = [], [], {}
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.volunteers-') as temp:
        staged = Path(temp) / 'prepared'
        staged.mkdir()
        for source in sources:
            subject = source.stem
            counts, sheets = {}, []
            with zipfile.ZipFile(source) as z:
                members = [i for i in z.infolist() if not i.is_dir()
                           and PurePosixPath(i.filename).suffix.lower() in ('.mp4', '.mov', '.avi')]
                if sum(i.file_size for i in members) > 2 * 1024**3:
                    raise ValueError('Archive exceeds 2 GiB import limit')
                for member in sorted(members, key=lambda i: i.filename):
                    name = PurePosixPath(member.filename)
                    if name.is_absolute() or '..' in name.parts or '\\' in member.filename:
                        raise ValueError('Unsafe archive member')
                    action = action_from_name(member.filename)
                    counts[action] = counts.get(action, 0) + 1
                    sample_id = f'{subject}-{action}-{counts[action]:02d}'
                    relative = Path('videos') / subject / (sample_id + name.suffix.lower())
                    target = staged / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(member) as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
                    with target.open('rb') as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if digest in seen:
                        raise ValueError(f'Duplicate clip: {sample_id} and {seen[digest]}')
                    seen[digest] = sample_id
                    meta, sheet = probe(target)
                    sheets.append(sheet)
                    rows.append(dict(sample_id=sample_id, subject_key=subject, action=action,
                                     action_label_source='filename_pending_visual_review',
                                     clinical_label=None, simulated_change=None, paired_visit=None,
                                     path=relative.as_posix(), sha256=digest, **meta))
                    mapping.append(dict(sample_id=sample_id, archive=source.name, member=member.filename))
            if sheets:
                cv2.imwrite(str(staged / f'{subject}-contact.jpg'), np.vstack(sheets))
        (staged / 'manifest.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        (staged / 'private-source-map.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
        staged.rename(output)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives', default='data/volunteers-20261007/archives')
    parser.add_argument('--output', default='data/volunteers-20261007/prepared')
    args = parser.parse_args()
    rows = prepare(args.archives, args.output)
    print(json.dumps([dict(id=r['sample_id'], seconds=round(r['duration_sec'], 2),
                           size=[r['width'], r['height']]) for r in rows], indent=2))
