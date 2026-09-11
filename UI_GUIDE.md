# Desktop UI development

The dashboard embeds the live webcam feed and reuses the existing screening
engine through `desktop.py`, the maintained camera entry point.

Use `python desktop.py --research` for the university demonstration. Its persistent
banner identifies the provisional facial-delta and projected-angle rules. Edit
`research_parameters.json` and reconnect to reload rules; F5 only changes the
theme. Research acquisitions use a separate numeric store and cannot clear a
customer's reported symptoms. See `validation/LITERATURE_BASELINES.md`.

## Launch

The desktop UI now displays Thai text. Choose **ก่อนนวด · Baseline** or
**หลังนวด · Recheck** in the dedicated panel above the visit form. Stop an active
capture before switching. IDs remain in the form; setup confirmation must be
checked again. Selecting Recheck does not check the symptom-report box for you.
The UI uses the same backend mode keys and identity checks as before.

`ui/visit_panel.py` contains the reusable selector, `ui/visit_state.py` its copy
and lock rules, and `ui/thai.py` Thai messages/font selection. Leelawadee UI is the
default; change `font` in `ui/theme.json` to another installed Thai font and press
F5. Text is rendered by Tk widgets directly, including Thai marks; no camera image
overlay or additional rendering dependency is used. Unknown diagnostics remain
verbatim. Theme reload preserves the selected mode and form values.

From the `Computer-Vision` folder, with Python and the requirements installed:

```powershell
python desktop.py
```

Run `python prepare_identity_model.py` once after installing requirements.
The paired camera workflow now verifies FaceNet identity before every acquired
frame. Keep the face visible during the arm hold. A missing face pauses capture;
a mismatch displays a persistent warning and requires restart. Identity matching
does not provide liveness or photo/replay detection. Tune the experimental 0.6
cosine threshold in `config.py`; face position/scale matching is removed, while
the 18-degree rotation limit remains. See `validation/RATIO_IDENTITY.md`.

Enter a customer ID and visit reference, choose baseline or recheck, and confirm
the capture setup. Rechecks require a customer symptom report. Click **Connect
camera**, wait for the models, and click **Start visit step**. See the README
for the paired workflow and its unconfigured clinical threshold.
Use **Stop** to discard an in-progress acquisition, **Restart visit step** to start
fresh, and **Disconnect** to release the camera. The camera number can be changed
while disconnected. **Overlay** toggles face/pose annotations.

If an existing virtual environment says `No Python at ...`, its original Python
installation has been removed or moved. Install Python with Tkinter support and
create a fresh virtual environment, then install `requirements.txt`. A portable
embedded Python runtime can run the boundary tests but does not include Tkinter
and cannot launch this dashboard.

The dashboard has no automatic camera activation. Paired sessions use the numeric
feature store and separate identity embedding columns.
Frames and video are not saved. **New customer** ends the session and clears the
form and its latched care notice. Theme reload preserves these session fields.

## Work on the UI without hardware

```powershell
python desktop.py --preview
```

Click **Open preview**, then **Start visit step**. The fixture cycles through each
stage and displays a clearly marked simulated summary. It never imports the CV
models, opens a camera, or writes screening results. Preview needs only Python
with Tkinter (included with the standard Windows Python installer).

## Where to make changes

| Change | File |
| --- | --- |
| Colors, font, font size, spacing | `ui/theme.json` |
| Layout and screen interactions | `ui/app.py` |
| Reusable labels, buttons, cards, camera panel | `ui/components.py` |
| Stage labels and safety copy | `ui/content.py` |
| Simulated data for UI development | `ui/preview.py` |
| Camera/model adapter and result persistence | `src/session.py` |
| Baseline/recheck gate and delta comparison | `src/visit_workflow.py` |
| Numeric storage and keyed customer/visit references | `src/feature_store.py` |
| Feature schema and scoring | `src/features.py` |
| Face embedding, crop and cosine similarity | `src/face_identity.py` |
| Approximate head rotation measurement | `src/head_pose.py` |
| Background commands and latest-frame delivery | `ui/worker.py` |
| Screening sequence | `src/screening_flow.py` |
| Existing timings and thresholds | `config.py` |

Save `ui/theme.json` and press **F5** or **Reload theme** to apply design tokens
without restarting the camera or the screening. Invalid tokens show an error
and preserve the current theme. Python code changes require an app restart.
Keep screening durations in `config.py`; `ui/content.py` reads them for progress.

## Architecture

`Dashboard -> SessionWorker -> ScreeningSession -> ScreeningFlow -> analyzers`

The worker owns all camera and model resources. UI actions enqueue commands;
the UI consumes snapshots on Tk's main thread. A one-frame queue drops stale
frames rather than letting rendering fall behind inference. Model startup and
camera errors appear in the dashboard and allow reconnection. Shutdown waits
for the current native call to return before cleaning up resources; a stalled
driver or model download can delay shutdown.

A snapshot contains `status`, `state`, `instruction`, `elapsed`, `extra`, `frame`
(RGB array or `None`), `assessment`, `save_status`, `comparison`, `care_message`,
`visit_mode`, `command_error`, and `fps`. To add another
frontend, consume this boundary instead of calling analyzers from widgets.
`PreviewSession` implements the same `open/start/stop/read/close` lifecycle.

## Checks

```powershell
python -m unittest discover -s tests -v
```

The suite tests the UI boundary, acquisition, identity gates and validation.
Optional native tests use installed vision dependencies and prepared weights;
they skip when unavailable and never download models automatically.
For a visual check, run preview and exercise start, stop, restart, completion,
theme reload, disconnect, and reconnect. Real camera/inference verification
requires a webcam and model weights.

The UI opens at 1280 x 1000 with a minimum size of 1080 x 900. A page scrollbar
keeps controls accessible when content exceeds the available height. The result
box scrolls independently. Capture controls are above the camera view and the
care notice remains fixed below the scrollable page. The paired workflow uses the ratio delta
contract, which remains clinically unvalidated.
