# The pooled scorer

`judge.py` here is the ledger's scorer as it stood when the 1 s runs in `calibration/rollouts/`
were made. It matches entries exactly as the shipped judge does and pools every entry into one
F1, where the shipped judge averages each class's F1 over the classes in the key.
`calibration/verify_scores.py` grades every 1 s run with it and checks that the two match the
same entries.
