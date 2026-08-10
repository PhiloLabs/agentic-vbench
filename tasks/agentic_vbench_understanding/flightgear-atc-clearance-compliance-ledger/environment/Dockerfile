FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir faster-whisper==1.2.1

ARG ASR_REPO=Systran/faster-whisper-small.en
ARG ASR_REVISION=d1d751a5f8271d482d14ca55d9e2deeebbae577f
RUN mkdir -p /baked/asr \
 && for file in model.bin config.json tokenizer.json vocabulary.txt; do \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "https://huggingface.co/${ASR_REPO}/resolve/${ASR_REVISION}/${file}" \
        -o "/baked/asr/${file}" || exit 1; \
    done \
 && echo "62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a  /baked/asr/model.bin" | sha256sum -c - \
 && echo "666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae  /baked/asr/config.json" | sha256sum -c - \
 && echo "929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df  /baked/asr/tokenizer.json" | sha256sum -c - \
 && echo "ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf  /baked/asr/vocabulary.txt" | sha256sum -c - \
 && test -s /baked/asr/model.bin

COPY transcribe.py /usr/local/bin/transcribe
RUN chmod +x /usr/local/bin/transcribe

ARG MATERIALS_URL=https://huggingface.co/datasets/Jordan8717/flightgear-atc-clearance-compliance-ledger/resolve/9f301d7fb4b81ceaa73ae98268679aae75fd03d0/flight.mp4
ARG MATERIALS_SHA256=a696502dc07cad2ac6e403027e3003f38c9508e527d6f37df2f6bb3b88eeab51
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/flight.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/flight.mp4" | sha256sum -c - \
 && test -s /baked/flight.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
