"""Predict rehabilitation labels from the self-contained transfer checkpoint."""

import argparse
import json

import torch
from torch import nn
from torchvision.models import resnet18
from pathlib import Path

from datasets.stroke_rehab.train_transfer import TemporalHead, VERSION, encode_video


def predict(checkpoint_path, video_path):
    saved = torch.load(checkpoint_path, weights_only=True, map_location='cpu')
    if saved.get('version') != VERSION:
        raise ValueError('Unsupported transfer checkpoint')
    encoder = resnet18(weights=None)
    encoder.fc = nn.Identity()
    encoder.load_state_dict(saved['encoder'], strict=True)
    encoder.eval()
    model = TemporalHead(saved['kind'])
    model.load_state_dict(saved['head'], strict=True)
    model.eval()
    features = encode_video(Path(video_path), encoder, saved['frames'], saved['size'], 'cpu').unsqueeze(0)
    with torch.inference_mode():
        ex, st = model((features - saved['mean']) / saved['std'])
    ex_prob, st_prob = ex.softmax(1)[0], st.softmax(1)[0]
    return {'exercise': saved['classes'][ex_prob.argmax().item()],
            'status': saved['statuses'][st_prob.argmax().item()],
            'exercise_confidence': ex_prob.max().item(), 'status_confidence': st_prob.max().item(),
            'clinical_validation': False, 'warning': 'Exercise completion only; softmax confidence is not stroke risk.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, default=Path('models/stroke_rehab_transfer.pt'))
    parser.add_argument('--video', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    print(json.dumps(predict(args.model, args.video), indent=2))
