# Threshold validation protocol and tools

For the university project's provisional demonstration rules and corrected
interpretation of the cited literature, see [LITERATURE_BASELINES.md](LITERATURE_BASELINES.md).
Use `--research` explicitly to enable that mode. It does not activate a clinical
policy. The evaluator now defaults to the project's 0.86 tuning sensitivity
goal and reports the 0.77 held-out floor separately; both are targets, not
established performance. [YFP evaluation](../datasets/yfp/README.md) is a separate
single-video facial-asymmetry task and cannot validate the paired stroke workflow.

No labeled customer data or clinically approved cutoff has been supplied. The
application therefore leaves its delta threshold **unconfigured**. Unit tests
use synthetic geometry and scores solely to verify software behavior.

The collection workflow, draft Thai consent language, blinded adjudication CSV,
label merge tool and subject-level splitter are in
[`validation/study`](study/COLLECTION_PROTOCOL_TH.md). These materials are study
scaffolding and require institutional/clinical review before participant use.

## Intended population and endpoint

The recheck is initiated only after a customer reports an abnormal symptom.
Evaluate the delta rule in this population, with both independently adjudicated
positive and negative outcomes. Symptomatic customers without the prespecified
target condition are essential negative cases. Asymptomatic controls alone do
not establish specificity for this workflow. Do not derive outcome labels from
the model score, the customer's report alone, or staff impressions of the video.

Specify the clinical target outcome, adjudication process, enrollment criteria,
sample size, acceptable sensitivity, uncertainty bounds and subgroup analyses
with qualified clinical/statistical reviewers before collecting study data.
Clinical care must proceed independently of research measurements.

## Feature and score contract

Schema: `mesh478-ipd-ratios-pose17-v2` (changed 2026-09-11). All features are
dimensionless, not millimeters. See [ratio definitions and identity gate](RATIO_IDENTITY.md).

| Feature | Definition |
| --- | --- |
| `neutral_mouth_ratio` | Median regional mouth S, using IPD-normalized lateral and height distances |
| `neutral_brow_ratio` | Median regional brow S, using IPD-normalized lateral and height distances |
| `neutral_eyelid_ratio` | Median regional eyelid S, using IPD-normalized lateral distances and apertures |
| `smile_mouth_ratio` | Median regional mouth S during the final portion of the smile hold |
| `closed_eyelid_ratio` | Median regional eyelid S during the final portion of gentle eye closure |
| `left_arm_drift`, `right_arm_drift` | Maximum downward wrist movement after initial lift, relative to its shoulder and normalized by shoulder span |
| `arm_lift_skew` | Left initial normalized lift minus right initial normalized lift |

For every feature, store its signed `post - pre` delta. The decision score is:

```text
face_delta = max(abs(delta) over all five facial ratio features)
arm_delta  = max(0, delta(left_arm_drift), delta(right_arm_drift),
                abs(delta(arm_lift_skew)))
score      = face_delta + arm_delta
alert      = score > approved_threshold
```

This is an engineering candidate score, not a validated clinical biomarker. Its
components have different distributions despite being dimensionless. Changing
features, weights, aggregation or models requires a new schema/study. Symmetric
ratios do not preserve the affected side. Reduced arm drift alone does
not increase the drift score. Equality to the threshold does not exceed it.

Completed facial stages and ongoing maximum arm drift can trigger an early delta
alert when an approved threshold exists. The available-component score is a lower bound on the final
score. Early alerts stay visible even if later acquisition fails, except that
identity mismatch clears the rejected attempt's comparison. The care notice
persists in either case. No early or
final low score clears reported symptoms. Eye closure advances on visible,
stable landmarks even if an eye does not close; the inability is measured.

## Collect and export

Use `python desktop.py` to collect a pre-massage baseline, then a symptomatic
recheck for the same customer and visit. Only complete feature records are
persisted. Export an unlabeled dataset with:

```powershell
python export_feature_pairs.py data/features/visits.sqlite3 data/unlabeled-pairs.jsonl
```

The output path must not already exist. Exported rows contain:

```json
{
  "pair_id": "pseudonymous-pair-reference",
  "subject_key": "keyed-customer-reference",
  "symptoms_reported": true,
  "label": null,
  "before": {"schema": "mesh478-ipd-ratios-pose17-v2", "features": {}, "setup": {}, "context": {}},
  "after": {"schema": "mesh478-ipd-ratios-pose17-v2", "features": {}, "setup": {}, "context": {}}
}
```

This is a structural illustration: the empty objects must contain the complete
numeric records produced by the exporter. `label: null` is deliberately
rejected by validation. Link independent clinical adjudication through an
approved study process and set label to integer `0` or `1`. Preserve the actual
symptom-report status. The application only exports symptomatic rechecks;
optional asymptomatic study controls require a separate research data source.

Split by customer into tuning and untouched holdout files **before tuning**.
Every visit from a customer must stay in one split. The tool rejects overlapping
customer keys, pair IDs, incompatible pipelines, mismatched capture setups,
missing values, nonfinite features and cohorts missing either outcome class.
Across installations with different HMAC keys, reconcile study subject IDs
under the study protocol before splitting; local keys cannot detect that the
same person visited two shops.

## Run the offline evaluation

```powershell
python validate_threshold.py data/tuning.jsonl data/holdout.jsonl --minimum-sensitivity 0.95 --output validation/research-report.json
```

`0.95` illustrates command syntax, **not a recommended clinical target**. Supply
the prespecified study target. The tool uses only symptomatic tuning cases to
choose the positive cutoff with highest specificity meeting that target. It
then evaluates the locked cutoff on symptomatic holdout cases, reporting:

- ROC points (FPR/TPR/threshold), tuning AUC and selected operating point.
- Holdout TP, FP, TN, FN, sensitivity, specificity, PPV and NPV.
- Wilson 95% intervals, subject/sample counts and whether the holdout point
  estimate meets the tuning sensitivity target.
- A separate asymptomatic holdout summary, if provided; these cases are never
  mixed into symptomatic tuning or holdout metrics.
- Input hashes, pipeline fingerprint, feature schema and scoring definition.

Wilson intervals here assume independent observations. Repeated visits need
a prespecified subject-clustered uncertainty analysis. Account for deployment
prevalence when interpreting predictive values. Add prospective external and
subgroup validation for camera quality, lighting, site, age, skin tone, glasses,
facial hair, pre-existing asymmetry and other relevant conditions. A point
estimate passing this script is not evidence of adequate sample size or safety.

## Deployment remains disabled

The report and companion `*-candidate.json` always have
`deployment_approved: false`. The command never writes the active policy. After
independent validation and clinical review, a responsible operator may create
`validation/deployment_threshold.json` using the reviewed candidate, a policy
ID, a clinical review reference and the report hash, with explicit deployment
approval. This is a provenance declaration; the software cannot verify the
quality or authenticity of a clinical review.

The live loader rejects unapproved, wrong-cohort, wrong-schema, wrong-pipeline,
nonfinite or nonpositive thresholds and missing holdout outcome classes. An
invalid policy leaves the result unconfigured and explains why. Model assets,
package versions, acquisition settings and feature code are fingerprinted; do
not edit the fingerprint to bypass revalidation after a change.

## Sources and measurement limits

[MediaPipe Face Mesh documentation](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/face_mesh.md)
describes 468 estimated facial landmarks, optional iris refinement (used here),
and normalized screen coordinates. This does
not establish sub-millimeter accuracy on an ordinary webcam. Camera calibration
and independent measurement validation would be needed for physical accuracy
claims. Face Mesh is a legacy API here, pinned to MediaPipe 0.10.14; newer
Face Landmarker APIs use a different model/output contract.

[Scikit-learn's threshold-tuning guidance](https://scikit-learn.org/stable/modules/classification_threshold.html)
explains why threshold selection needs data separate from final evaluation.
Our offline implementation uses the standard library, not a new scikit-learn
runtime dependency.

[CDC stroke guidance](https://www.cdc.gov/stroke/signs-symptoms/index.html) calls
for immediate emergency help for sudden stroke signs. AI measurements are
additional observations, not confirmation required before seeking care.
