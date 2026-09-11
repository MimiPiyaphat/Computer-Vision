# YFP facial-asymmetry benchmark

Source: [AvLab-CV/YouTube-Facial-Palsy-Database](https://github.com/AvLab-CV/YouTube-Facial-Palsy-Database).
The repository describes 32 videos, sampled into image sequences at 6 FPS.
Its README inconsistently lists 21 and 22 people; use the authors' subject
metadata when constructing folds. Several people have multiple clips.

## Access status

**The actual dataset is not included in the GitHub repository or this project.**
The authors require an application from a university email address to obtain
the archive password. See the repository's access form and restrictions.
Research use and redistribution restrictions apply. A draft request checklist
is provided in `ACCESS_REQUEST.txt`; complete and send it through your own
university account. No access request has been sent by this project.

After obtaining authorized access, extract data under a local folder such as
`data/yfp/authorized/`, which is gitignored. Dataset files must not be committed
or included in the submission repository. Numeric derived features may also
fall under the dataset terms; keep them within the authorized research group.

Required citation from the authors: Hsu, Gee-Sern Jison; Kang, Jiunn-Horng;
Huang, Wen-Fong. **Deep hierarchical network with line segment learning for
quantitative analysis of facial palsy.** IEEE Access, 2018.

## Define the manifest from authorized metadata

The private archive layout is not assumed. Make one manifest row per video or
reviewed image sequence and map its actual relative path. Use pseudonymous
dataset subject keys, keeping every clip of the same person under the same
key. This is a structural example, not a downloadable sample:

```json
{"sample_id":"yfp-clip-01","subject_key":"yfp-person-01","source":"yfp","label":1,"split":"lopo","kind":"image_sequence","path":"actual-relative-sequence-directory"}
{"sample_id":"control-clip-01","subject_key":"control-person-01","source":"control","label":0,"split":"lopo","kind":"video","path":"actual-relative-control-video.mp4"}
```

Supported kinds are `video` and `image_sequence`; sequence filenames must sort
in temporal order. Video inputs are sampled at approximately 6 FPS; supplied
image sequences are processed as supplied. Use explicit, independently reviewed
video-level labels. YFP's local Eyes/Mouth annotations and intensity values
0.5/1.0 are not binary healthy/affected video labels. This adapter does not
invent labels from absent annotations or use the unaffected side as a healthy
control. Independently labeled healthy controls are required for specificity.

## Extract numeric single-video scores

```powershell
python yfp_benchmark.py extract --manifest data/yfp/manifest.jsonl --data-root data/yfp/authorized --output data/yfp/scores.jsonl
```

This runs the same pinned MediaPipe Face Mesh geometry, not YOLO for faces.
It resets tracking between clips, applies basic visibility/pose checks, and
aggregates each clip's frame asymmetry by its 90th percentile. Frame asymmetry
is `max(mouth_ratio, brow_ratio, eyelid_ratio)` using the v2 IPD-normalized
regional ratios. Re-extract previous v1 scores; see
[the 2026-09-11 feature changes](../../validation/RATIO_IDENTITY.md). At least three valid
frames and at least 50% valid sampled-frame coverage are required. The roll/yaw-proxy gates and aggregation are engineering
choices, not reproduced from the cited papers. No video/image copies or raw
meshes are written by the extractor.

Every manifest row appears in the score file, including failures, with sampled,
valid and rejected frame counts. Failed acquisition produces `score: null`.
Missing files and undetectable faces are not silently excluded from evaluation.

## Evaluate

With only YFP palsy cases, evaluate the **fixed, unfitted** single-video
placeholder for an exploratory sensitivity/coverage check:

```powershell
python yfp_benchmark.py evaluate --scores data/yfp/scores.jsonl --mode fixed --fixed-threshold 0.10 --output data/yfp/fixed-report.json --check-targets
```

Specificity will be unavailable without negative controls, so the joint target
check exits 3. This is the correct result, not an error to suppress.

After adding independently labeled controls, use the authors' subject-level
leave-one-person-out protocol, with all manifest entries set to `split: lopo`:

```powershell
python yfp_benchmark.py evaluate --scores data/yfp/scores.jsonl --mode lopo --output data/yfp/lopo-report.json --check-targets
```

Alternatively, assign complete subjects to `tuning` or `holdout` and use
`--mode holdout`. The tuning routine seeks **both sensitivity >= 0.878 and
specificity >= 0.993**. If infeasible, it labels the targets unmet and reports
the best available operating point; it never changes labels or claims success.
LOPO folds lacking a training class are explicitly unevaluable.

The report contains per-fold ROC points/thresholds, confusion counts, coverage,
Wilson intervals and target status. Evaluable-only metrics are separated from
failure-adjusted worst-case metrics, where unavailable positives count as misses
and unavailable negatives as false alarms. Target checks use the latter.
Intervals shown assume independent clips; repeated-person inference needs a
clustered analysis. Small samples cannot substantiate very high specificity
with narrow uncertainty even when no false positives are observed.

This benchmark detects visible facial asymmetry in individual clips. It does
not evaluate stroke diagnosis, customer-reported symptoms, pre/post changes,
arm motion, or the complete system's sensitivity. **Do not load these fitted
single-video thresholds into the paired-delta configuration.**
