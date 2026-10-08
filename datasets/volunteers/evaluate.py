"""Exploratory gesture recognition, NOT stroke detection, on volunteer clips.

Fixed nearest-centroid baseline; leave-one-person-out evaluation. No frame split,
augmentation, test-driven model selection, or clinical labels are used.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from src.face_analytics import FaceAnalyzer
from src.model_metrics import classification_metrics

LABELS = ['neutral', 'smile', 'blink']
FEATURES = ['mouth_width_median', 'mouth_open_median', 'mouth_lift_median',
            'eye_relative_range', 'eye_relative_speed', 'eye_low_fraction']
ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'data/volunteers-20261007/prepared'


def clip_features(samples):
    a = np.array([[s[k] for k in ('mouth_width', 'mouth_open', 'mouth_lift', 'ear')]
                  for s in samples], dtype=float)
    if len(a) < 15 or not np.isfinite(a).all():
        raise ValueError('At least 15 finite face samples required')
    ear = a[:, 3]
    upper = max(float(np.quantile(ear, .9)), 1e-6)
    # Do not bridge missing detections as if adjacent observations were continuous.
    intervals = np.diff([s['time'] for s in samples])
    adjacent = (intervals > 0) & (intervals <= .15)
    steps = np.abs(np.diff(ear))[adjacent] / intervals[adjacent]
    return [*np.median(a[:, :3], axis=0).tolist(),
            float((upper - np.quantile(ear, .1)) / upper),
            float(np.mean(steps) / upper) if len(steps) else 0.,
            float(np.mean(ear < .7 * upper))]


def fit_centroids(x, y):
    x, y = np.asarray(x, float), np.asarray(y, int)
    if set(y) != set(range(len(LABELS))) or not np.isfinite(x).all():
        raise ValueError('Training fold must contain all gesture classes and finite features')
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.maximum(scale, 1e-6)
    z = (x - mean) / scale
    return dict(mean=mean.tolist(), scale=scale.tolist(),
                centroids=[z[y == k].mean(axis=0).tolist() for k in range(len(LABELS))])


def predict(model, x):
    z = (np.asarray(x) - model['mean']) / model['scale']
    return np.argmin(((z[:, None, :] - np.array(model['centroids'])) ** 2).sum(axis=2), axis=1).tolist()


def evaluate(rows):
    actual, predicted, predictions, folds = [], [], [], []
    subjects = sorted({r['subject_key'] for r in rows})
    if len(subjects) < 3:
        raise ValueError('Need at least three people for exploratory evaluation')
    for subject in subjects:
        train = [r for r in rows if r['subject_key'] != subject]
        test = [r for r in rows if r['subject_key'] == subject]
        model = fit_centroids([r['features'] for r in train], [LABELS.index(r['action']) for r in train])
        pred = predict(model, [r['features'] for r in test])
        truth = [LABELS.index(r['action']) for r in test]
        folds.append(dict(test_subject=subject, train_subjects=sorted({r['subject_key'] for r in train}),
                          train_clips=len(train), test_clips=len(test),
                          metrics=classification_metrics(truth, pred, LABELS)))
        actual.extend(truth)
        predicted.extend(pred)
        predictions.extend(dict(sample_id=r['sample_id'], subject_key=subject,
                                actual=r['action'], predicted=LABELS[p]) for r, p in zip(test, pred))
    return dict(metrics=classification_metrics(actual, predicted, LABELS), folds=folds, predictions=predictions)


def extract(path):
    cap, analyzer = cv2.VideoCapture(str(path)), FaceAnalyzer()
    observations, sampled, decoded, next_time = [], 0, 0, 0.
    reasons = Counter()
    fps = cap.get(cv2.CAP_PROP_FPS)
    expected = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if not cap.isOpened() or not np.isfinite(fps) or fps <= 0:
        cap.release()
        analyzer.close()
        raise ValueError('Video cannot be opened or has invalid FPS')
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            time = decoded / fps
            decoded += 1
            if time + 1e-6 < next_time:
                continue
            next_time += 1 / 15
            sampled += 1
            h, w = frame.shape[:2]
            factor = min(1., 960 / max(h, w))
            frame = cv2.resize(frame, (round(w * factor), round(h * factor)))
            quality = analyzer.check_quality(frame)
            if not quality['ok']:
                reasons[quality['reason']] += 1
                continue
            v = analyzer.latest_features
            h, w = frame.shape[:2]
            xy = np.array([(p.x * w, p.y * h) for p in analyzer._last_landmarks])
            axis = xy[473] - xy[468]
            ipd = np.linalg.norm(axis)
            if ipd < 1:
                reasons['Iris spacing too small'] += 1
                continue
            horizontal = axis / ipd
            vertical = np.array([-horizontal[1], horizontal[0]])
            if vertical[1] < 0:
                vertical *= -1
            mouth_center = (xy[13] + xy[14]) / 2
            corners = (xy[61] + xy[291]) / 2
            observations.append(dict(time=time, mouth_width=float(np.linalg.norm(xy[61] - xy[291]) / ipd),
                                     mouth_open=float(np.linalg.norm(xy[13] - xy[14]) / ipd),
                                     mouth_lift=float(np.dot(mouth_center - corners, vertical) / ipd),
                                     ear=(v['left_ear'] + v['right_ear']) / 2))
    finally:
        cap.release()
        analyzer.close()
    complete = decoded >= expected - max(2, expected * .01)
    coverage = len(observations) / sampled if sampled else 0.
    eligible = complete and coverage >= .7 and len(observations) >= 15
    return dict(decoded_frames=decoded, sampled_frames=sampled, accepted_frames=len(observations),
                face_coverage=coverage, decode_complete=complete, rejection_reasons=dict(reasons),
                features=clip_features(observations) if eligible else None, timeline=observations)


def run(dataset, output):
    dataset, output = Path(dataset).resolve(), Path(output)
    if output.exists():
        raise ValueError('Use a new output directory to preserve previous experiments')
    rows = [json.loads(line) for line in (dataset / 'manifest.jsonl').read_text(encoding='utf-8').splitlines() if line]
    output.mkdir(parents=True)
    audited = []
    for row in rows:
        path = (dataset / row['path']).resolve()
        if not path.is_relative_to(dataset):
            raise ValueError('Video path outside dataset')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('Video hash changed')
        values = extract(path)
        timeline = values.pop('timeline')
        result = {**row, **values}
        result['eligible'] = row['action'] in LABELS and values['features'] is not None
        result['exclusion'] = ('arms: only one volunteer, demo only' if row['action'] == 'arms'
                               else 'insufficient face coverage or incomplete decode' if not result['eligible'] else None)
        audited.append(result)
        (output / f"{row['sample_id']}.timeline.json").write_text(json.dumps(timeline), encoding='utf-8')
        print(f"{row['sample_id']}: {values['accepted_frames']}/{values['sampled_frames']} face samples; eligible={result['eligible']}", flush=True)
    eligible = [r for r in audited if r['eligible']]
    evaluation = evaluate(eligible)
    dataset_reference = dataset.relative_to(ROOT).as_posix() if dataset.is_relative_to(ROOT) else dataset.name
    report = dict(schema='volunteer-gesture-report-v1', created_at=datetime.now(timezone.utc).isoformat(),
                  protocol='Leave-one-person-out; fixed standardized nearest-centroid classifier',
                  feature_names=FEATURES, dataset_directory=dataset_reference, subjects=sorted({r['subject_key'] for r in rows}),
                  counts=dict(Counter(r['action'] for r in rows)), clips=audited, **evaluation,
                  limitations=['Exploratory gesture classification only, not stroke diagnosis or risk prediction.',
                               'Task labels come from filenames; contact sheets were inspected, but no clinical labels exist.',
                               'Five people only; clips from the same person are correlated. Clip CI is not a clinical confidence interval.',
                               'No independent external test set, paired before/after visits, or verified abnormal cases.',
                               'One arms clip is for replay only. No arm classifier or closed-eye-hold evaluation.',
                               'Excluded/low-coverage clips do not contribute to gesture accuracy.',
                               'This experiment does not replace the live screening model or change alert thresholds.'])
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    final_model = dict(schema='volunteer-gesture-centroids-v1', labels=LABELS, features=FEATURES,
                       intended_use='Offline gesture experiment only; not clinical screening',
                       **fit_centroids([r['features'] for r in eligible], [LABELS.index(r['action']) for r in eligible]))
    (output / 'gesture-model.json').write_text(json.dumps(final_model, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DEFAULT)
    parser.add_argument('--output', type=Path, default=DEFAULT.parent / 'evaluation-v2')
    args = parser.parse_args()
    report = run(args.dataset, args.output)
    print(json.dumps(report['metrics'], indent=2))
