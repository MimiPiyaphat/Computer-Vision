# University research baseline parameters

This profile makes the demonstration runnable without claiming clinical
validation. Start it with `python desktop.py --research`. The normal mode still
requires an approved clinical delta policy. The two modes use different stores
and capture-protocol fingerprints, so a demo baseline is not silently reused
as a clinical baseline.

Edit `research_parameters.json`, then reconnect the camera (restart the app to
refresh the initial banner). F5 reloads UI styling, not decision rules. The UI
displays the rules actually loaded by the connected worker.

## Parameters and what the sources actually establish

| Project setting | Initial value | Interpretation |
| --- | --- | --- |
| Projected arm-angle delta rule | **28.9 degrees** | User-selected, unvalidated 2D demonstration rule; not a pronation measurement or a study-derived drift cutoff |
| Alternative arm-angle delta rule | **33.0 degrees** | Manually selectable by editing the active rule; it is not an upper clamp and does not delay alerts at 28.9 |
| Paired facial-delta rule | **0.10** | Explicit engineering placeholder in normalized units, not a literature-derived threshold or a fitted result |
| Facial sensitivity target | **0.878** | Project objective based on the cited paramedic benchmark |
| Facial specificity target | **0.993** | Project objective based on the cited paramedic benchmark |
| Overall sensitivity floor | **0.77** | Acceptance target to evaluate on labeled paired symptomatic cases |
| Overall sensitivity stretch | **0.86** | Project stretch objective, not a demonstrated performance guarantee |

### Arm study correction

The [iPronator study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3404034/) reports
28.9 degrees and 33.0 degrees for pronation summary measures; 3.8 degrees is the
control pronation summary. The reported group values are medians of per-person
metrics. Its average-drift summary was 26.8 degrees. None of these group
summaries is a validated diagnostic decision threshold. The authors explicitly
state that sensitivity and specificity could not be determined from their
selected patient sample.

That study used forearm-mounted accelerometers. Our YOLO shoulder/wrist points
cannot measure rotation about the forearm axis. The research demo instead
measures **camera-plane angular descent**: arms start down and then extend out
to the sides at shoulder height. This is deliberately a different acquisition
protocol, not a reproduction of the clinical pronator drift test. Angular
values are absent when the arms are foreshortened or no raised reference was
captured. Do not reinterpret an absent angle as zero.

The proxy removes shoulder-line roll and computes the shoulder-to-wrist vector
angle using `atan2(downward component, absolute outward component)`. It tracks
maximum descent from the raised reference in each session. The research rule
compares `max(0, post_maximum - pre_maximum)` across both arms with **28.9**.
Equality does not exceed the rule. Degrees are never added to the normalized
facial or arm-drift scores.

### Facial study correction

In [Aldridge et al., Frontiers in Neurology (2022)](https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2022.878282/full),
87.8% sensitivity and 99.3% specificity were the **paramedics'** results. The
computer-vision algorithm reported 90.3% sensitivity and 87.5% specificity.
Neither result specifies a threshold for this project's MediaPipe features.

We retain 0.878 and 0.993 as simultaneous project targets. There is no valid
formula converting these percentages directly to a geometric cutoff. The
0.10 facial-delta placeholder only exercises the decision path. Threshold
tuning requires labeled positives and negatives; an unmet target must remain
unmet in the report. The separate YFP benchmark uses a single-video absolute
asymmetry score, not this pre/post delta, so its fitted cutoff cannot be copied
into `face_delta_threshold`.

### FAST meta-analysis correction

[The FAST/BEFAST meta-analysis](https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2021.765069/full)
reports pooled FAST sensitivity of 0.77, with a 95% confidence interval of
0.64-0.86, and specificity of 0.60. Thus 0.86 is the upper bound of that
particular interval, not a guaranteed minimum. Our implementation lacks the
Speech component and serves a different population, so FAST's performance
does not transfer automatically. The numeric floor and stretch target are
project acceptance criteria to test, not performance obtained by setting a
configuration value.

## Demonstration and evaluation commands

Run the actual camera-based university prototype:

```powershell
python desktop.py --research
```

Collect a baseline and a symptom-triggered recheck as described in the main
README. Research records go to `data/features-research/`; raw camera media are
not saved. A research alert is raised when **either** the provisional facial
delta rule or the projected arm-angle delta rule is exceeded. Incomplete data
are inconclusive; all reported symptoms retain the immediate care notice.

For a reproducible submission demonstration without camera/model dependencies:

```powershell
python research_demo.py --output validation/research-demo.json
```

This runs four explicitly synthetic scenarios through the real research rule
function. The generated artifact reports no sensitivity/specificity and states
that YFP was not evaluated. It is a functional demo, not empirical evidence.

For labeled research-mode pairs, evaluate the **actual face/angle OR-rule**:

```powershell
python export_feature_pairs.py data/features-research/visits.sqlite3 data/research-unlabeled.jsonl
# Obtain independent labels and isolate the held-out cohort before evaluation.
python evaluate_research_pairs.py data/research-holdout.jsonl --output validation/research-or-report.json --check-project-targets
```

This evaluator uses the active provisional rules, preserves acquisition failures
in the denominator, and tests the 0.77 sensitivity floor and 0.86 stretch target.
It never adjusts cutoffs on the holdout. Exit code 3 means the floor is unmet or
unevaluable. These acceptance checks cannot guarantee clinical performance.

For the existing **normalized combined-score** experiment, use:

```powershell
python validate_threshold.py data/tuning.jsonl data/holdout.jsonl --output validation/research-report.json --check-project-targets
```

The default tuning sensitivity target is now the project's **0.86** stretch
objective; an explicit `--minimum-sensitivity` overrides it. The held-out report
checks the **0.77** floor separately. Exit code 3 means the project floor was
not met; it does not silently retune on the holdout. This command validates
the existing normalized combined score, **not** the new OR-combination of
provisional angle and face rules. Neither rule's overall clinical sensitivity
has been measured. A future paired study must evaluate the complete demo
decision rule, including acquisition failures and the symptom gate; use the
OR-rule evaluator above for that dataset.

## Current evidence status for the submission

- Native Face Mesh and YOLO code and synthetic decision paths can be tested.
- Literature references and benchmark targets are recorded with corrected meanings.
- No numerical cutoff here has been clinically validated.
- No YFP performance is claimed until authorized data are obtained and processed.
- Overall clinical sensitivity cannot be inferred from a facial-only dataset.

See [YFP integration](../datasets/yfp/README.md) for access and evaluation steps.
