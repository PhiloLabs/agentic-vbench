FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

ARG RGB_ARCHIVE_URL=https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/cf21602e-4424-42a4-b05d-9897957082ad
ARG RGB_ARCHIVE_SHA256=556357b3ae5804541d6cef75df724af43170f63df6d3cdfda7150fd175822268
ARG REFERENCE_ARCHIVE_URL=https://data.4tu.nl/file/b008dd74-020d-4ea4-a8ba-7bb60769d224/4b6641cf-0034-4875-8ebb-73e35e4a5b91
ARG REFERENCE_ARCHIVE_SHA256=59628d56cc75de40a8e408eada2e83e7006ece5e42e54bd0dc24bb3a452fe9af

RUN curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "$RGB_ARCHIVE_URL" -o /tmp/rgb.zip \
 && echo "${RGB_ARCHIVE_SHA256}  /tmp/rgb.zip" | sha256sum -c - \
 && mkdir -p /tmp/selected /baked/materials \
 && unzip -jq /tmp/rgb.zip \
        '*05_assy_0_1.mp4' '*05_assy_2_2.mp4' '*05_main_0_1.mp4' \
        '*14_assy_0_1.mp4' '*14_main_0_1.mp4' '*14_main_2_2.mp4' \
        '*14_main_2_3.mp4' -d /tmp/selected \
 && ffmpeg -v error -i /tmp/selected/05_assy_0_1.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/A.mp4 \
 && ffmpeg -v error -i /tmp/selected/05_assy_2_2.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/B.mp4 \
 && ffmpeg -v error -i /tmp/selected/05_main_0_1.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/C.mp4 \
 && ffmpeg -v error -i /tmp/selected/14_assy_0_1.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/D.mp4 \
 && ffmpeg -v error -i /tmp/selected/14_main_0_1.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/E.mp4 \
 && ffmpeg -v error -i /tmp/selected/14_main_2_2.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/F.mp4 \
 && ffmpeg -v error -i /tmp/selected/14_main_2_3.mp4 -map 0:v:0 -c copy -an -map_metadata -1 /baked/materials/G.mp4 \
 && rm -rf /tmp/rgb.zip /tmp/selected \
 && test "$(find /baked/materials -name '*.mp4' -size +0c | wc -l)" -eq 7

RUN curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "$REFERENCE_ARCHIVE_URL" -o /tmp/reference.zip \
 && echo "${REFERENCE_ARCHIVE_SHA256}  /tmp/reference.zip" | sha256sum -c - \
 && mkdir -p /baked/reference \
 && unzip -jq /tmp/reference.zip 'part_geometries/Overview of states.pdf' -d /baked/reference \
 && mv '/baked/reference/Overview of states.pdf' /baked/reference/overview-of-states.pdf \
 && rm /tmp/reference.zip \
 && test -s /baked/reference/overview-of-states.pdf

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
