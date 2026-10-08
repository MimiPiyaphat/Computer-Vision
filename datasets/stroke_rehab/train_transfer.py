"""Frozen ImageNet encoder + temporal heads; validation selects, Test reports once.

Run from the repo: python -m datasets.stroke_rehab.train_transfer --root ...
Only rehabilitation exercise/completion labels are learned, never stroke risk.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from torchvision.models import resnet18, ResNet18_Weights

from datasets.stroke_rehab.train_classifier import CLASSES, STATUSES, read_records, sample_video, split_training, subject_key
from src.model_metrics import classification_metrics

VERSION = "resnet18-imagenet-v1-uniform-rgb160-temporal-v1"


class TemporalHead(nn.Module):
    def __init__(self, kind="mlp"):
        super().__init__()
        self.kind = kind
        if kind == "gru":
            self.temporal = nn.GRU(512, 96, batch_first=True, bidirectional=True)
            width = 384
        else:
            width = 2048  # mean, std, range, last minus first
        self.shared = (nn.Identity() if kind == "linear" else
                       nn.Sequential(nn.Linear(width, 128), nn.ReLU(), nn.Dropout(.5)))
        self.exercise = nn.Linear(width if kind == "linear" else 128, len(CLASSES))
        self.status = nn.Linear(width if kind == "linear" else 128, len(STATUSES))

    def forward(self, values):
        if self.kind == "gru":
            seq, _ = self.temporal(values)
            pooled = torch.cat((seq.mean(1), seq.amax(1)), dim=1)
        else:
            pooled = torch.cat((values.mean(1), values.std(1, unbiased=False),
                                values.amax(1) - values.amin(1), values[:, -1] - values[:, 0]), dim=1)
        shared = self.shared(pooled)
        return self.exercise(shared), self.status(shared)


def encode_video(path, encoder, frames, size, device):
    video = sample_video(path, frames, size).float().div_(255)
    mean = torch.tensor([.485, .456, .406]).view(1, 3, 1, 1)
    std = torch.tensor([.229, .224, .225]).view(1, 3, 1, 1)
    with torch.inference_mode():
        return encoder(((video - mean) / std).to(device)).cpu()


def extract(records, encoder, frames, size, device, cache):
    signature = [(str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns, e, s) for p, e, s in records]
    identity = {"version": VERSION, "frames": frames, "size": size, "records": signature}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    path = cache / (digest + ".pt")
    if path.exists():
        saved = torch.load(path, weights_only=True, map_location="cpu")
        if saved['identity'] == identity:
            print(f"cached features: {len(records)} videos", flush=True)
            return saved['features']
    vectors = []
    for index, (video, _, _) in enumerate(records, 1):
        vectors.append(encode_video(video, encoder, frames, size, device))
        if index % 10 == 0 or index == len(records):
            print(f"encoded {index}/{len(records)}", flush=True)
    features = torch.stack(vectors)
    cache.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.partial')
    torch.save({'identity': identity, 'features': features}, temporary)
    temporary.replace(path)
    return features


def loader(features, records, batch, shuffle=False):
    return DataLoader(TensorDataset(features, torch.tensor([r[1] for r in records]),
                                   torch.tensor([r[2] for r in records])), batch_size=batch, shuffle=shuffle)


def evaluate(model, data, device):
    model.eval()
    truth = [[], []]
    predictions = [[], []]
    loss_sum = 0
    with torch.inference_mode():
        for x, ex, st in data:
            outputs = model(x.to(device))
            for i, (out, target) in enumerate(zip(outputs, (ex, st))):
                truth[i].extend(target.tolist())
                predictions[i].extend(out.argmax(1).cpu().tolist())
                loss_sum += nn.functional.cross_entropy(out, target.to(device), reduction='sum').item()
    return {'exercise': classification_metrics(truth[0], predictions[0], CLASSES),
            'status': classification_metrics(truth[1], predictions[1], STATUSES),
            'loss': loss_sum / len(truth[0]),
            'predictions': {'exercise': predictions[0], 'status': predictions[1]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('models/stroke_rehab_transfer.pt'))
    parser.add_argument('--cache-dir', type=Path, default=Path('data/rehab-transfer-cache'))
    parser.add_argument('--frames', type=int, default=16)
    parser.add_argument('--size', type=int, default=160)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--patience', type=int, default=18)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if min(args.frames, args.epochs, args.patience, args.threads) < 1 or args.size < 32:
        parser.error('Invalid training dimensions or limits')
    if args.output.exists() or args.output.with_suffix('.metrics.json').exists():
        parser.error('Choose a new output; existing trained artifacts are preserved')
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    torch.hub.set_dir(str(Path('data/torch-hub').resolve()))
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    source_train, test_records = read_records(args.root, 'Train'), read_records(args.root, 'Test')
    if not source_train or not test_records:
        parser.error('Expected nonempty source Train and Test')
    if {subject_key(r) for r in source_train} & {subject_key(r) for r in test_records}:
        parser.error('Source Train/Test subject leakage')
    train_records, val_records = split_training(source_train, seed=args.seed)
    encoder = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    encoder.fc = nn.Identity()
    encoder.eval().to(device)
    for parameter in encoder.parameters():
        parameter.requires_grad_(False)
    print(f'device={device}; train={len(train_records)}; validation={len(val_records)}; test={len(test_records)}', flush=True)
    train_x = extract(train_records, encoder, args.frames, args.size, device, args.cache_dir)
    val_x = extract(val_records, encoder, args.frames, args.size, device, args.cache_dir)
    # Fit normalization exclusively on the training partition.
    mean = train_x.mean((0, 1), keepdim=True)
    std = train_x.std((0, 1), keepdim=True).clamp_min(.05)
    train_data = loader((train_x - mean) / std, train_records, 32, True)
    train_eval = loader((train_x - mean) / std, train_records, 64)
    val_data = loader((val_x - mean) / std, val_records, 64)
    candidates = [('linear', .001, .01), ('mlp', .001, .01), ('gru', .0003, .01)]
    trials = []
    best_global = None
    selected = None
    selected_state = None
    for kind, lr, decay in candidates:
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        model = TemporalHead(kind).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=decay)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=.5)
        history = []
        best = None
        best_epoch = 0
        best_state = None
        for epoch in range(1, args.epochs + 1):
            model.train()
            loss_sum = 0
            for x, ex, st in train_data:
                exercise, status = model(x.to(device))
                loss = nn.functional.cross_entropy(exercise, ex.to(device)) + nn.functional.cross_entropy(status, st.to(device))
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5)
                optimizer.step()
                loss_sum += loss.item() * len(x)
            metrics = evaluate(model, val_data, device)
            ranking = (metrics['status']['macro_f1'], metrics['exercise']['macro_f1'], -metrics['loss'])
            history.append({'epoch': epoch, 'train_loss': loss_sum / len(train_records),
                            'validation_loss': metrics['loss'], 'validation_status_accuracy': metrics['status']['accuracy'],
                            'validation_status_macro_f1': metrics['status']['macro_f1'],
                            'validation_exercise_accuracy': metrics['exercise']['accuracy']})
            scheduler.step(metrics['loss'])
            if best is None or ranking > best:
                best, best_epoch = ranking, epoch
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            if epoch % 5 == 0 or epoch == 1:
                print(json.dumps({'candidate': kind, **history[-1]}), flush=True)
            if epoch - best_epoch >= args.patience:
                break
        model.load_state_dict(best_state)
        trial = {'kind': kind, 'learning_rate': lr, 'weight_decay': decay, 'best_epoch': best_epoch,
                 'validation': evaluate(model, val_data, device), 'history': history}
        trials.append(trial)
        if best_global is None or best > best_global:
            best_global, selected, selected_state = best, trial, best_state
    # No test predictions have been evaluated before model selection is final.
    model = TemporalHead(selected['kind']).to(device)
    model.load_state_dict(selected_state)
    test_x = extract(test_records, encoder, args.frames, args.size, device, args.cache_dir)
    test_metrics = evaluate(model, loader((test_x - mean) / std, test_records, 64), device)
    train_metrics = evaluate(model, train_eval, device)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = {'version': VERSION, 'encoder': {k: v.cpu() for k, v in encoder.state_dict().items()},
                  'head': selected_state, 'kind': selected['kind'], 'mean': mean, 'std': std,
                  'frames': args.frames, 'size': args.size, 'classes': CLASSES, 'statuses': STATUSES}
    temporary = args.output.with_suffix('.partial')
    torch.save(checkpoint, temporary)
    temporary.replace(args.output)
    manifest = {name: [{'path': str(p.relative_to(args.root)), 'subject': subject_key((p,e,s)),
                       'exercise': e, 'status': s, 'bytes': p.stat().st_size} for p,e,s in records]
                for name, records in [('train', train_records), ('validation', val_records), ('test', test_records)]}
    report = {'schema': 'rehab-transfer-report-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
              'task': 'rehabilitation_exercise_and_completion', 'clinical_validation': False,
              'screening_model_trained': False, 'device': str(device), 'seed': args.seed,
              'pipeline': VERSION, 'frames': args.frames, 'size': args.size,
              'model_file': args.output.name, 'model_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'selection_metric': 'validation status macro F1, exercise macro F1, then lower loss',
              'selected_kind': selected['kind'], 'best_epoch': selected['best_epoch'],
              'train': train_metrics, 'validation': selected['validation'], 'test': test_metrics,
              'trials': trials, 'history': selected['history'], 'manifest': manifest,
              'subjects': {name: sorted({r['subject'] for r in records}) for name, records in manifest.items()},
              'limitations': ['Volunteer rehabilitation labels, not stroke outcomes.',
                             'One validation subject and four test subjects; generalization remains uncertain.',
                             'Wilson intervals are clip-level and ignore within-person correlation.',
                             'Test was not used for this run selection; legacy experiments previously observed this source test split.']}
    report_path = args.output.with_suffix('.metrics.json')
    report_tmp = report_path.with_suffix('.partial')
    report_tmp.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    report_tmp.replace(report_path)
    print(json.dumps({'saved': str(args.output), 'report': str(report_path), 'test': test_metrics}), flush=True)


if __name__ == '__main__':
    main()
