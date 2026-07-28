# Scripted shortcut diagnostics

These deterministic diagnostics are supplementary to the strong-model ablations.

## 742-way face recognition, video only

OpenCV YuNet detected faces at one frame per second. SFace matched each face against
all 742 official portraits. Consecutive observations were grouped into turns.
Without audio, the baseline used the global modal language code (`en`).

| predicted turns | true positives | F1 |
|---:|---:|---:|
| 60 | 1 | 0.013699 |

## Offline language identification

The pinned SpeechBrain VoxLingua107 model was restricted to the task's 21 language
codes and run on each full turn after removing two seconds at both boundaries.

| turns | correct | accuracy |
|---:|---:|---:|
| 86 | 82 | 0.953488 |

Per-turn predictions are in `language_observability.json`.

## Full perception plus semantic-card matching

The final offline diagnostic combines energy VAD, 742-way YuNet/SFace matching,
the pinned VoxLingua model, the shipped Whisper-base model over each full predicted
turn, and maximum-weight one-to-one card assignment using TF-IDF cosine,
character-trigram Jaccard, and word Jaccard. It never reads ground truth.

The perception stages alone place 39 of 74 predicted turns on the exact identity,
language, and both-boundary tuple, an event-F1 headroom of 0.4875 if every card
were known. A deterministic split exposed 19 exact-turn translations during
authoring and held out 20. Card matching reduces the final result to five true
positives: one development and four held-out.

| predicted turns | perception-exact turns | final true positives | final F1 | strong-agent threshold |
|---:|---:|---:|---:|---:|
| 74 | 39 | 5 | 0.062500 | < 0.10 |

Five earlier card versions were rejected, including a fresh held-out summary set
that scored 0.1625. The final cards state source-supported counterfactuals,
implications, falsifiable policy-logic tests, or premise/outcome tensions instead
of restating speech content. Cross-model qualification and all hashes are in
`semantic_card_qualification.json`.

Independent ceiling controls matched the final cards to 86 independently shuffled
complete official transcripts (multilingual, no identity or order metadata):
GPT-5.6 Sol and Gemini 3.1 Pro each scored **86/86, 1.0**. Thus the inferential target is semantically recoverable
even though lexical ASR matching stays below the strong-agent threshold.

These controls bracket rather than prove the strong-agent outcome. On the
untouched translation split, lexical card matching is 4/20; extrapolating that
rate across the 39 perception-exact turns gives about 7.8 true positives, or
event F1 near 0.0975, with wide uncertainty. Only the required fresh strong-agent
runs establish whether the task actually satisfies the `< 0.10` gate.

Post-result decomposition shows where difficulty actually binds. Opus localizes
47 turns and gets both language and card correct on all 47, but only 10 identities.
The scripted CV pipeline gets identity correct on 40 of 41 boundary-aligned turns
but cards correct on only six. The two halves are therefore individually solved
inside the image; the task remains hard because no measured actor combines them.
The known combined-actor headroom is `0.4875`, which future stronger agents may
approach. Card hardening is not claimed as the binding strong-agent difficulty.

`scripted_semantic_baseline.py` reproduces perception; the stronger card matcher
is `evaluate_base_semantic_baseline.py`. It uses YuNet
SHA-256 `8f2383e4...2552fa4`, SFace SHA-256 `0ba9fbfa...7c34e79`,
the pinned VoxLingua revision, and Whisper-base SHA-256
`ed3a0b6b...6326e34e`. Scoring is performed separately by the shipped verifier.
