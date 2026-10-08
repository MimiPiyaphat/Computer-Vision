# Roboflow stroke 2.0 v3 experiment

Developer-only YOLO object-detection experiment for the Roboflow Universe export
`air-a2axo/stroke-2-0-lu7ua`, version 3 (CC BY 4.0). The local archive SHA-256 is
`792ea2f54502af8f008df61a90f9309788fe2170a3060cbf70dc58eb73154ef3`.

The export contains 471 images: 326 train, 99 validation and 46 test. It labels
bounding boxes as `no stroke` and `stroke`; it is not a before/after massage
dataset and has no independently verified clinical outcomes.

Run `audit.py` before `train.py`. The audit rejects missing pairs, invalid YOLO
rows and out-of-range boxes, and records cross-split hashes/source families.
`train.py` selects the checkpoint on validation, evaluates test only afterward,
copies the best weight to `models/roboflow_stroke_yolov8n.pt`, and writes a JSON
report for the password-gated developer dashboard.

Important limitation: the published split contains source-family overlap and the
two classes have visibly different source styles. A detector can learn those
styles instead of medical signs. Keep this model disconnected from customer
results and do not present its detection metrics as diagnostic accuracy.
