# Ground-truth provenance

The source rows in `source/` are copied from the seven matching recording folders in
IndustReal v2 `val_p1.zip`:

- dataset DOI: `10.4121/b008dd74-020d-4ea4-a8ba-7bb60769d224.v2`
- archive URL: `https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/bb336949-248c-4ae6-82ef-107dbe61d10f`
- archive SHA256: `20bd1e3089123b5b28ccfe57647f8b0a2822d4a3565830db4ef87d0182ebc248`

Each `.raw.csv` is the published `PSR_labels_raw.csv`: a timestamped 11-component
state vector where `-1`, `0`, and `1` mean incorrectly installed, absent, and
correctly installed. Each `.events.csv` is the corresponding published
`PSR_labels_with_errors.csv` used as an independent consistency check.

These are the dataset's canonical structured PSR records, not task-author labels.
The task therefore uses the `machine-truth` tier from the AgenticVBench Spec Card.
The builder does not infer transition times from the videos and does not apply manual
timestamp corrections.

`build.py` converts every raw state row after the initial condition into one
checkpoint. It copies the complete post-transition state vector, derives all changed
step IDs, converts 10 fps frame numbers to seconds, and anonymizes recordings as `A`
through `G`. For transitions represented by the published event labels, the builder
asserts exact equality with those labels. It additionally represents
`incorrect -> absent` as a removal because this task audits every raw state change.
The result is 47 checkpoints written to the verifier and oracle copies of
`ground_truth.json`. Run:

```bash
python3 ground_truth/build.py --check
```

The published frame is the assembly-state transition frame, not the end of the
surrounding hand action. `time_s` is that frame number divided by 10 on the original
video timeline. The state at frame zero is an initial condition, not a checkpoint.

The two checked-in JSON files are deliberately identical but live in separate Harbor
mounts: the agent never receives either the oracle solution or verifier answer key.
