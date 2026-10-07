# Stroke rehabilitation video subset

This directory is prepared for a 30-clip subset of the public dataset:

- Source: [An upper limb stroke rehabilitation exercise video dataset](https://data.mendeley.com/datasets/49h9dcwx5v/1)
- License: CC BY 4.0
- Source contents: volunteer rehabilitation exercises, labelled `complete` or `incomplete`

Important: these are not recordings of acute stroke symptoms or a clinical stroke cohort. They must not be described as clinical stroke-positive videos or used as evidence of diagnostic accuracy.

## Expected layout

Preserve the layout `source/<exercise>/<Complete|Incomplete>/<Train|Test>/<video>.mp4`.
Then run:

```powershell
py -3.12 datasets/stroke_rehab/prepare_dataset.py `
  --source datasets/stroke_rehab/source `
  --output datasets/stroke_rehab/clips `
  --count 30 --seed 42
```

The script creates exactly 30 MP4 clips, each approximately 5 seconds long
(rounded to the nearest frame), plus `metadata.csv` and `checksums.sha256`.
It samples round-robin across exercise, source split and completion status,
shuffling videos within each group using the seed. With the current 16 groups,
each contributes 1–2 clips and each completion status contributes 15 clips.
Metadata retains exercise, original split, filename subject prefix and seed.
Do not train on the combined subset as if it were a new independent Train/Test
split; preserve the source split and group all clips from one person together.

The output directory must not already exist. Choose a new name for a new
selection; the script never overwrites previous clips. It stages a complete set
before publishing, and fails on selected videos shorter than 5 seconds or on
decode errors instead of padding them with fabricated motion.

## Labels

The source labels are retained as `complete` and `incomplete`. The metadata also records `source_type=volunteer_rehabilitation`, so downstream evaluation cannot accidentally present this as a patient dataset.

## Train and predict

Train the motion-aware baseline, reserving whole people from the original Train
split for validation. Subject IDs are parsed from the dataset's numeric filename
prefix. The script rejects overlap between source Train and Test. The default
seed on the current source holds out subject `04` for validation (84 clips),
leaving 327 training clips and the original 80 Test clips. Review this filename
convention before substituting another dataset.

```powershell
python datasets/stroke_rehab/train_classifier.py `
  --root datasets/stroke_rehab/source `
  --output models/stroke_rehab_classifier_validated_split.pt `
  --epochs 12 --batch-size 32 --frames 8 --size 48
```

Run one video through the saved checkpoint:

```powershell
python datasets/stroke_rehab/predict_classifier.py `
  --model models/stroke_rehab_classifier_validated_split.pt `
  --video "datasets/stroke_rehab/source/1_Lifting an Object/Complete/Test/07_01_01_01.mp4"
```

The classifier predicts rehabilitation exercise identity and completion status only. It is not connected to the application's facial asymmetry/arm-drift screening result and is not a stroke diagnosis model.

Checkpoint selection uses validation status accuracy. Test is evaluated only
once after the checkpoint is selected. The metrics JSON includes the subject
split, validation history and test confusion matrices (rows = actual, columns =
predicted, ordered as `CLASSES` and `STATUSES` in the training script).
An existing checkpoint/metrics path is rejected; use a new output name.
Video sampling preserves uniformly spaced frame indices even for short clips;
decode failures are reported instead of silently repeating the final good frame.
Cached tensors are invalidated when source size/mtime, sampling version or
frame/image settings change.

The existing `stroke_rehab_classifier_full.metrics.json` was produced by the old
training loop, which selected its best epoch using Test. Its 68.75% status score
is therefore not an untouched holdout estimate. Existing weights/reports have
been retained for provenance; retraining is required for the revised protocol.
