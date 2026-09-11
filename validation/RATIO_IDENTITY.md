# Ratio measurements and identity verification — 2026-09-11

This change replaces the v1 signed facial differences with regional asymmetry
ratios and adds one-to-one face verification to the paired camera workflow.
The previous implementation already removed translation and scale from geometry;
its additional `face_x`, `face_y`, and `face_scale` compatibility checks caused
otherwise usable rechecks to be rejected. No raw coordinate subtraction remains
in the facial delta contract.

## Measurement definition

`src/features.py:face_geometry` uses MediaPipe's 468 facial landmarks plus ten
iris landmarks (`refine_landmarks=True`, 478 total). The distance between iris
centers 468 and 473 estimates image-space inter-pupillary distance (IPD).
These are inferred iris centers, not measured pupils in millimeters. Iris
estimates during eye closure, gaze changes, and low-resolution capture need
validation. The ordinary 468-point mesh has no iris centers, so v2 requires
refinement rather than silently substituting outer-eye span for IPD.

The facial vertical midline passes through the iris midpoint, perpendicular to
the iris axis. For bilateral distances `dL`, `dR`, compute:

```text
L = dL / IPD
R = dR / IPD
S = 1 - min(L/R, R/L) = 1 - min(L,R)/max(L,R)
```

The latter form avoids division by a zero side. Both normalized distances at
most `1e-8` give zero asymmetry; exactly one zero gives one. Invalid IPD or
degenerate eye geometry rejects the sample. Every regional S is in [0, 1].
Although IPD cancels algebraically, normalization is performed explicitly.

| Region | Bilateral measurements, each normalized by IPD | Regional score |
| --- | --- | --- |
| Mouth | Corner distances to vertical midline; corner heights from horizontal iris axis | Maximum of the two S values |
| Brows | Mean brow positions on each side, measured against both reference axes | Maximum of the two S values |
| Eyelids | Mean eye landmark distances to vertical midline; mean upper/lower lid separation per eye | Maximum of lateral S and aperture S |

The complementary height/aperture measurements are deliberate: perpendicular
distances to a vertical line alone miss purely vertical droop and incomplete
eye closure. EAR remains available for blink timing; raw
left/right EAR values no longer enter the paired facial delta.

Median regional scores are collected at neutral, smile, and eye closure stages.
`face_delta` remains the maximum absolute post-minus-pre change across the five
facial features. Arm normalization and aggregation are unchanged. Symmetric
ratios discard which side is affected: a side switch of equal magnitude or
symmetric bilateral deterioration can produce no change. A low delta must
never dismiss symptoms. The 0.10 research rule remains an **untuned demo value**
and needs fresh validation on the new score distribution.

Translation, uniform scaling and modest in-plane roll do not change ideal
ratios. Perspective, yaw, pitch, expression, gaze, occlusion and landmark noise
still affect measurements. This does not establish angle independence or
sub-millimeter precision. Every accepted face sample must have absolute roll,
yaw and pitch within **18 degrees**, configurable in `HEAD_POSE_MAX_DEGREES`.
Roll comes from the iris axis; yaw/pitch use OpenCV PnP with generic six-point
face geometry and estimated camera intrinsics. These are approximate engineering
gates and require camera/subject validation. Body setup gates, same camera,
resolution, station, protocol and instructed posture requirements remain.

## Identity gate and storage

`src/face_identity.py` runs the pinned `facenet-pytorch==2.5.3` VGGFace2
InceptionResnetV1 on CPU in eval/inference mode. MediaPipe supplies the face
region; the crop is aligned by the iris axis, padded 10%, resized to 160×160 RGB
and standardized with `(pixel - 127.5) / 128`. The 512-number output is L2
normalized. Crops and frames stay in memory. The custom crop differs from the
upstream MTCNN pipeline; published recognition accuracy does not transfer.

Prepare the model once before camera use:

```powershell
python -m pip install -r requirements.txt
python prepare_identity_model.py
python desktop.py --research
```

Runtime requires the local weights and never silently downloads them. Loading
uses PyTorch `weights_only=True`. The identity signature binds weight bytes,
the embedding implementation and the package version. Threads are configurable
with `IDENTITY_CPU_THREADS` (default two; shared PyTorch CPU thread setting).

Before **every paired acquisition frame**, including the arm hold, the session
requires one visible face within the rotation limits and checks an embedding.
Baseline enrollment keeps the initial embedding; later baseline frames must
match it. Recheck frames must match the enrolled embedding with cosine
similarity **>= 0.6** (`IDENTITY_COSINE_THRESHOLD`, experimental). Verification
also gates both clinical and research comparison methods at the workflow
boundary, so calling a delta through the live workflow cannot skip it.

Missing or unusable faces pause capture and invalidate the current verification.
An interrupted arm hold restarts from arms down. A mismatch immediately stops
measurement collection and comparison, latches rejection until restart, and
displays **Identity mismatch: does not match registered user**. No rejected
recheck is saved. Symptom care notices remain visible. Expression changes or
new facial weakness may lower similarity even for the same person; rejection
is not grounds to delay care.

SQLite adds nullable `baselines.identity_embedding` and `identity_model`
columns without overwriting existing rows. The embedding is separate from the
measurement `record` JSON. Exports select measurement records explicitly and
exclude biometric embeddings and identity model identifiers. Customer deletion
also deletes their stored embeddings. These are **sensitive biometric data**,
pseudonymized but not encrypted by this application; limit access, obtain
appropriate participant consent and define retention. No raw media is stored.

Face recognition verifies resemblance to enrollment; it does **not** establish
liveness or resist photographs, video replays, masks or synthetic faces. Do not
describe this prototype as a completed anti-spoofing system. The experimental
threshold needs independent same-person/different-person pairs, including
expression, lighting and pose variation, with false-match/nonmatch reporting.

## Migration and verification

The new schema is `mesh478-ipd-ratios-pose17-v2`; the score definition is
`max-absolute-face-ratio-change+max-arm-change-v2`. Old baselines cannot be
converted without the original measurements (which were intentionally not
stored). Capture a fresh baseline under a new visit reference. Missing identity
embeddings also require fresh enrollment. Old threshold artifacts are rejected;
retune and evaluate against held-out symptomatic pairs before approval. YFP
single-video extraction also has a new benchmark schema; re-extract old scores.

Tests cover transformed asymmetric geometry, vertical droop, unilateral eye
closure, zero-distance handling, all rotation axes, arm setup checks, successful
identity matches, mismatches bypassing both delta functions, the exact 0.6
boundary, invalid vectors, persistence/migration and export exclusion. Synthetic
tests establish software behavior, not clinical accuracy, identity accuracy,
liveness resistance or camera FPS. The supplied real datasets are still pending.

## Implementation references

- [MediaPipe Face Mesh refinement and iris landmarks](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_mesh.md)
- [FaceNet PyTorch model and preprocessing documentation](https://github.com/timesler/facenet-pytorch)
- [Pinned 2.5.3 dependency metadata](https://pypi.org/pypi/facenet-pytorch/2.5.3/json)
- [OpenCV PnP geometry](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html)
