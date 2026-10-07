# StrokeVision AI

A local university research prototype that captures pre-massage measurements
and compares them with a routine or symptom-reported post-massage recheck. The desktop UI contains the
camera window; UI components, acquisition, identity checks and validation tools
are separate modules.

This is not a medical device or clearance for massage. Reported stroke symptoms
need urgent medical attention; do not wait for a camera result. The demo rules
and performance goals are unvalidated.

The draft intended use is limited to assisting trained staff in tracking
within-person changes after massage against the same person's compatible baseline.
A recheck may be recorded with or without reported symptoms; the symptom field
only adds urgent safety guidance. Routine tracking is not a validated medical-risk
screen for people without symptoms. The system does not diagnose or rule out stroke
or authorize massage. See [intended use and prohibited uses](validation/INTENDED_USE_TH.md)
and the [production readiness gates](validation/PRODUCTION_READINESS_TH.md).

## How to run

Use **64-bit Python 3.12 with Tkinter**, a webcam and Windows PowerShell. Run the
commands from the project folder. Internet access is needed to install packages
and download missing weights. Create a fresh environment after cloning; virtual
environments, model weights and local visit data are not included in Git.

To get this branch on a new computer:

```powershell
git clone --branch ThanaTester https://github.com/MimiPiyaphat/Computer-Vision.git
cd Computer-Vision
```

Then run the setup commands below from your clone's directory.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe prepare_identity_model.py
.\.venv\Scripts\python.exe desktop.py --research
```

If `py -3.12` reports no installed Python, install Python 3.12 with the Tcl/Tk
component first. These commands use the environment's interpreter directly;
PowerShell activation is unnecessary. `.venv/` and other conventional environment
directory names are ignored by Git. For a custom environment name, add it to
`.gitignore` before installing packages. Ignoring does not untrack files already
committed to Git.

Face Mesh uses assets bundled with MediaPipe. `prepare_identity_model.py` downloads
FaceNet weights once into `models/`; camera startup then uses that local file.
YOLO uses `yolov8n-pose.pt`, downloading it on first use if missing.
Ultralytics settings and its persistent cache default to the project's ignored
`data/ultralytics/` directory. An explicit `YOLO_CONFIG_DIR` takes precedence.

For later runs:

```powershell
.\.venv\Scripts\python.exe desktop.py --research
```

Other modes:

```powershell
# UI preview: simulated data, no camera, models or saved records
.\.venv\Scripts\python.exe desktop.py --preview

# Paired capture with clinical delta threshold initially unconfigured
.\.venv\Scripts\python.exe desktop.py

# Four synthetic rule scenarios, without camera access
.\.venv\Scripts\python.exe research_demo.py
```

`--research` enables the provisional rules in `research_parameters.json`: facial
ratio delta 0.10 and projected arm-angle delta 28.9 degrees. The 33.0-degree
alternative and sensitivity/specificity goals are documented in
[literature baselines](validation/LITERATURE_BASELINES.md). They are not measured
performance or approved clinical cutoffs. Real face/arm datasets are still pending.

The v3 research rule checks **increases** in facial asymmetry; absolute changes
are still retained for audit, but decreases alone do not trigger the face rule.
The eye-closure feature uses the left/right EAR difference divided by the resting
eye opening, rather than dividing by a nearly closed eye. The 0.10 threshold is
still an unfitted engineering placeholder; this correction is not model training.
Restart the app and collect a fresh baseline before the next paired demonstration.
The capture signature rejects older baselines measured with the previous formula;
the replacement workflow archives them rather than reinterpreting old values.

No labelled before/after stroke-risk training set is included. The rehabilitation
classifier under `datasets/stroke_rehab` predicts exercise completion and does
not drive the dashboard result. Training it cannot calibrate this face rule.
Risk-model training needs independently labelled paired captures from the current
pipeline, repeat captures to measure variability, and separate subjects for tuning
and evaluation. The application does not currently estimate stroke probability.

## Camera workflow

The dedicated mode panel has **ก่อนนวด · Baseline** and **หลังนวด · Recheck**
buttons. Switching retains the customer/visit IDs, resets setup confirmation and
clears the displayed result. During capture, stop before switching modes. Choosing
Recheck does not automatically assert that symptoms were reported. The optional
symptom checkbox must reflect the customer's actual report; when checked, urgent
care guidance appears immediately. Existing care notices remain visible.
The symptom checkbox appears only in **หลังนวด · Recheck**. Before-massage capture
records a reference without requiring symptom selection.

Thai text is rendered directly in the desktop widgets using **Leelawadee UI**
(available on this Windows computer). Change `font` in `ui/theme.json` and press
F5 to use another installed font, such as Sarabun or Noto Sans Thai. The UI falls
back to an installed Thai-capable font if the chosen font is unavailable. No
font download or system installation is performed. Unknown technical diagnostics
remain in their original language for troubleshooting.

1. Enter a customer ID and a new visit reference; select **baseline** and confirm
   the camera/station and instructed posture.
2. Click **Connect camera**, wait for model loading, then **Start visit step**.
3. Follow quality check, neutral face, smile, gentle eye closure, blink and arm
   lift/hold. Keep one complete face visible, including during the arm hold.
4. After massage, select **recheck** using the same customer/visit IDs whether or
   not the customer reports symptoms. Check the symptom-report box only when an
   abnormal symptom is actually reported; urgent care guidance then appears
   immediately, even if acquisition cannot proceed.
5. Identity must match before measurements and deltas proceed. Missing faces
   pause capture; interrupted arm holds restart from arms down. A mismatch shows
   **Identity mismatch: does not match registered user** and requires restart.

Use **Stop** to discard the current acquisition, **Disconnect** to release models
and camera, and **New customer** to end the session and clear its form and notices.
Baselines expire for comparison after 12 hours by default. When a baseline is
expired or incompatible, select **baseline** with the same customer/visit IDs to
capture a replacement. SQLite archives the previous baseline and its rechecks;
only the new generation remains active for future comparisons.

## Measurements and identity

- **MediaPipe Face Mesh:** 468 facial plus 10 iris landmarks. Mouth, brow and
  eyelid scores use IPD-normalized `S = 1 - min(L/R, R/L)`. Complementary height
  and eyelid-aperture ratios retain sensitivity to vertical changes.
- **YOLOv8n-pose:** shoulder-relative arm lift/drift in shoulder-span units;
  research mode also evaluates a projected 2D arm-angle change.
- **CPU FaceNet:** separate 512-value embeddings; cosine similarity must be
  **>= 0.6**, an experimental value. This is identity consistency checking,
  not liveness or photo/replay protection.

Face x/y and scale are stored as acquisition metadata, **never baseline rejection
checks or delta inputs**. Absolute head roll/yaw/pitch must stay within 18 degrees;
yaw and pitch are approximate PnP estimates. Body positioning, camera, resolution,
station and pipeline compatibility checks remain. Small-face and visibility
checks still use image geometry; no pixel drift risk classification remains.

Ratios are dimensionless, not calibrated millimeters, and are still affected by
perspective and landmark quality. Symmetric ratios discard the affected side.
See [exact formulas, identity storage and limitations](validation/RATIO_IDENTITY.md).

## Background execution

The app runs in one Python process. Tkinter owns the main thread. Clicking
**Connect camera** starts one daemon `SessionWorker` thread, which opens the
camera/models and performs acquisition, identity inference, measurement, delta
comparison and SQLite writes. Native inference libraries may use their own CPU
threads; `IDENTITY_CPU_THREADS` controls the shared PyTorch CPU setting.

UI actions enter a command queue. The worker publishes snapshots into a queue
holding only the newest frame/result, so slow rendering does not accumulate
stale video. Tkinter polls approximately every 33 ms and is the only thread that
updates widgets. Actual FPS depends on inference and hardware, not that interval.
Identity is checked before every acquired frame, including arm frames.
The identity gate and face stages share one fresh Face Mesh observation per
frame. A missing face pauses acquisition without reusing previous landmarks.
The lighting gate compares pixels inside the facial mesh hull, excluding the
background. This remains an engineering quality check, not exposure calibration.

Invalid form commands leave the camera connected and display an error. Camera or
model failures stop the worker and attempt resource cleanup. Disconnect/close
sets a stop event; the UI waits through scheduled callbacks for cleanup. An
in-flight native call must return before cleanup can finish. No separate server,
scheduled job or persistent background service is installed. Preview uses the
same worker interface with simulated snapshots and no model imports.

## Storage and validation

Complete visits are stored in `data/features/visits.sqlite3`; research mode uses
`data/features-research/visits.sqlite3`. Baseline embeddings occupy separate
identity columns and are excluded from measurement exports. Customer and visit
IDs are keyed with HMAC-SHA256 using each store's `identity.key`; raw IDs, images,
landmarks, video and audio are not saved. Embeddings are sensitive biometric data.
Records are pseudonymized, **not encrypted**; protect the database/key and define
participant consent, access and retention procedures. Customer deletion removes
local records and embeddings; backups/exports need separate handling.

```powershell
.\.venv\Scripts\python.exe export_feature_pairs.py data/features-research/visits.sqlite3 data/unlabeled-pairs.jsonl
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Exports are unlabeled and do not establish performance. Follow the
[threshold protocol](validation/README.md) for independent labels, customer-level
tuning/holdout splits and ROC/confusion-matrix evaluation. The
[YFP benchmark](datasets/yfp/README.md) is a separate single-video task. Native
tests skip when their dependencies/weights are unavailable; synthetic tests do
not establish clinical accuracy, recognition accuracy or camera FPS.

## Editing the UI and code

| Change | Location |
| --- | --- |
| Colors, fonts, spacing; F5 reload | `ui/theme.json` |
| Layout, interactions, camera rendering | `ui/app.py`, `ui/components.py` |
| Instructions and simulated preview | `ui/content.py`, `ui/preview.py` |
| Baseline/Recheck panel and lock rules | `ui/visit_panel.py`, `ui/visit_state.py` |
| Thai messages and installed-font selection | `ui/thai.py` |
| Background command/snapshot queues | `ui/worker.py` |
| Camera/model lifecycle and persistence | `src/session.py` |
| Screening stages and timers | `src/screening_flow.py` |
| Ratios, normalized arms, rotation | `src/features.py`, `src/arm_features.py`, `src/head_pose.py` |
| Identity embedding and comparison gates | `src/face_identity.py`, `src/visit_workflow.py` |
| Settings and provisional rules | `config.py`, `research_parameters.json` |

See [UI_GUIDE.md](UI_GUIDE.md) for the UI workflow. Reconnect after code/config
changes; F5 reloads only the theme. Pipeline fingerprints include source and
settings, so code cleanup can invalidate old baseline comparisons. Select baseline
with the same customer/visit IDs to archive and replace an incompatible record;
never bypass fingerprint checks.

## Developer model evaluation

The desktop app includes a developer-only evaluation page. Click **Dev** in the
header or press `Ctrl+Shift+D`, then enter the configured developer password to
view the held-out rehabilitation evaluation, accuracy/precision/recall/F1 and
confusion matrices. This page is for development and demonstration only; the
current transfer model is trained on rehabilitation exercise-completion labels,
not stroke-risk labels, and its metrics must not be presented as clinical
accuracy. The paired before/after screening workflow remains the source of the
customer-facing result.

## Troubleshooting

- **Camera unavailable:** close other camera apps and select the correct camera index.
- **Identity weights missing:** run `prepare_identity_model.py` using the same environment.
- **No usable face:** keep the full face visible, improve lighting and face forward.
- **Identity mismatch:** restart with the enrolled participant. The experimental
  threshold can reject the same person under changed conditions; it is not a care decision.
- **`torchvision::nms` missing:** recreate `.venv` and install the pinned requirements
  with the same interpreter. Mixed torch/torchvision binaries can cause this error.
- **Tkinter missing:** use a standard Python installation with Tcl/Tk. An embedded
  Python runtime can run pure tests but does not include this desktop toolkit.

## Changelog

### 2026-10-07 — capture and dataset reliability

- Reuse the current identity-gated Face Mesh observation in face stages and
  measure lighting within the facial region.
- Keep default Ultralytics settings/cache under local ignored `data/`.
- Select the 30-clip rehabilitation subset across exercise/status/source-split
  groups with a fixed seed; preserve existing outputs and publish complete sets.
- Select rehabilitation checkpoints on subject-disjoint validation people from
  Train; evaluate Test only after selection and report confusion matrices.
- These acquisition changes update the pipeline fingerprint. Existing visit
  records remain intact in history when a fresh baseline replaces them.

### 2026-09-12 — Thai visit UI

- Added a separate reusable Baseline/Recheck panel with Thai/English labels,
  mode-specific guidance, capture locking and mode-aware preview.
- Added Thai controls, stage instructions, result labels and care notices,
  using native widget text and Leelawadee UI with configurable font fallbacks.
- Added page scrolling, compact stage layout and mode-transition tests.

### 2026-09-11 — project cleanup

- Consolidated live use on `desktop.py`; removed the old `main.py` OpenCV launcher,
  legacy risk classifier/logger, obsolete repair/sync scripts and redundant setup guide.
- Removed duplicate absolute wrist tracking, pixel drift flags, old smile-lift
  scoring, unused settings/FPS helper and the unused direct SciPy pin (SciPy may
  still be installed transitively by inference packages).
- Removed broken `venv` folders, generated Python caches and the unused Face
  Landmarker Task asset. Preserved visit databases, dataset guidance and current weights.
- Expanded ignore rules for virtual environments and local generated files.
- Documented current setup, background execution and the maintained test suite.

### 2026-09-11 — ratios and identity

- Introduced `mesh478-ipd-ratios-pose17-v2`, regional ratio deltas, iris IPD and an
  18-degree rotation gate; removed facial position/scale matching requirements.
- Added CPU FaceNet identity verification, separate SQLite embedding columns,
  mismatch rejection and migration/validation tests.

### 2026-09-10 — paired research workflow

- Added feature-only measurement storage, symptom-triggered comparisons,
  provisional research rules and offline threshold/YFP evaluation tools.

### 2026-09-09 — desktop UI

- Added a configurable Tkinter dashboard, camera worker and hardware-free preview.
