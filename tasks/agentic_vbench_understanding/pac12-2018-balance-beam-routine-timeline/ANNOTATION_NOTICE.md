# Annotation and licensing notice

A superseded development draft used FineGym v1.1 annotations to find candidate
balance-beam events in YouTube video `0LtLS9wROrk`.

- Project: FineGym
- Project page: https://sdolivia.github.io/FineGym/
- Annotation license: Creative Commons Attribution-NonCommercial 4.0
  International (CC BY-NC 4.0)
- License text: https://creativecommons.org/licenses/by-nc/4.0/

The repository is Apache-2.0 licensed, so the final scored key does not copy,
redistribute, or rely on FineGym annotation records. A second human annotator
scanned the full broadcast from the video alone, without access to the earlier
draft or FineGym, and all differences were then resolved against the original
broadcast. This clean-room result replaces the candidate-index provenance for
the final scored key.

The task does not redistribute the source broadcast. Its environment fetches the
publicly hosted video and accepts it only when its SHA-256 matches the pinned
digest. See `annotations/README.md` and `annotations/status.json` for the
release gate and evidence to retain.
