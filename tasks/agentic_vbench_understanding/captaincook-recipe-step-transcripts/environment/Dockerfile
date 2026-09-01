FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the 22 recordings. Pillow and numpy
# are here because the calibration runs used them to build contact sheets, and the
# family's rule is that a local calibration is only valid in an environment carrying the
# image's exact libraries. The grader itself is pure stdlib and needs neither. Pinned to
# the versions the calibration environment actually carries.
RUN pip install --no-cache-dir pillow==11.1.0 numpy==2.4.3

# Bake the 22 recordings at build time from pinned URLs, each verified by SHA256, the
# same pattern the v1.0 families (PR #10 / #37) and the understanding worked example use.
# The bake step strips container metadata, chapters and any data or subtitle stream so
# the image carries no recording identifiers, and asserts the result is clean.
#
# WHAT IS PINNED AND WHY IT IS NOT THE PUBLISHER'S OWN OBJECT. CaptainCook4D publishes
# each recording as a 3840x2160 HEVC file at about 45 Mbit/s. The 22 of them are
# 92 GiB, which is not a sane thing to pull and transcode inside an image build, so
# what is pinned here is a derivative: the same recording scaled to 1080p with the audio
# dropped, 12.3 GiB in total. CaptainCook4D is released under the Apache License 2.0,
# which permits redistributing a derivative with attribution, and NOTICE carries that
# attribution. Nothing is cropped, cut or reordered; only the resolution changes.
#
# The publisher's own URL and the SHA256 of the publisher's own object are recorded for
# every letter in provenance/media_manifest.json, so a reviewer can download the 4K
# original, confirm our source was the real one, and rerun
# provenance/data_setup/02_prepare_media.sh to reproduce the derivative.
#
# Source: CaptainCook4D (arXiv:2312.14556), https://captaincook4d.github.io/captain-cook/
# Annotations pinned by commit in provenance/data_setup/01_download_annotations.sh.
#
# A = 3_36     Microwave Mug Pizza      946.45 s     678 MiB
# B = 3_46     Microwave Mug Pizza      694.36 s     498 MiB
# C = 3_49     Microwave Mug Pizza      779.91 s     559 MiB
# D = 4_30     Ramen                    783.18 s     561 MiB
# E = 4_36     Ramen                   1044.34 s     748 MiB
# F = 4_40     Ramen                    652.08 s     468 MiB
# G = 4_43     Ramen                    809.74 s     581 MiB
# H = 4_44     Ramen                    608.41 s     436 MiB
# I = 5_27     Coffee                  1149.62 s     824 MiB
# J = 5_35     Coffee                   837.37 s     600 MiB
# K = 5_37     Coffee                   770.44 s     552 MiB
# L = 5_42     Coffee                   676.51 s     485 MiB
# M = 5_44     Coffee                  1020.72 s     732 MiB
# N = 7_48     Breakfast Burritos       602.97 s     432 MiB
# O = 7_50     Breakfast Burritos       687.55 s     493 MiB
# P = 7_135    Breakfast Burritos       928.89 s     666 MiB
# Q = 10_42    Pinwheels                748.81 s     536 MiB
# R = 10_46    Pinwheels                709.24 s     508 MiB
# S = 10_48    Pinwheels                649.75 s     466 MiB
# T = 13_38    Butter Corn Cup          816.22 s     585 MiB
# U = 13_41    Butter Corn Cup          914.61 s     656 MiB
# V = 13_44    Butter Corn Cup          766.03 s     549 MiB

ARG BASE=https://huggingface.co/datasets/Maxine668/captaincook-recipe-step-transcripts/resolve/cd30776102ba9096e924ac8e1850ce08c469f092
ARG A_URL=${BASE}/A.mp4
ARG A_SHA256=1de77631a7e77baa830a25ffbac43a150d1447eb41bb1574d30aaf36c2b9e7de
ARG B_URL=${BASE}/B.mp4
ARG B_SHA256=b725dd264d3cef39d071dfcf8626ee09de8c214dc55172a461d2b0f469be4ceb
ARG C_URL=${BASE}/C.mp4
ARG C_SHA256=f27e67264aca713c844bca30dcf3c62d19a843678d891b3072d8ae7a96353624
ARG D_URL=${BASE}/D.mp4
ARG D_SHA256=ce072ea191d7fe95d2a0638f9b57f7ed3647280bdc1aa4921869f0a83d82715d
ARG E_URL=${BASE}/E.mp4
ARG E_SHA256=a2ef11fcac4210412ab8fc7662dfdbf64adad509835fcd4281cadfa38c18dfcc
ARG F_URL=${BASE}/F.mp4
ARG F_SHA256=0b9b5aa3b3b46a0e2fc9782332d2815bd56beb97efc0b290642fadc7c6f8c916
ARG G_URL=${BASE}/G.mp4
ARG G_SHA256=4ea95abd980f743188704cc4f6995e011b43a8d3ef6be734754d1d0afd4dfdeb
ARG H_URL=${BASE}/H.mp4
ARG H_SHA256=49405b70f1f69f26e8594ea726674780030fa91fa2c3056721682dc72fc84c6b
ARG I_URL=${BASE}/I.mp4
ARG I_SHA256=1ece0545b80fff180026d887524b4a8fd4eb4d4b36b7f259d3da5730e1562969
ARG J_URL=${BASE}/J.mp4
ARG J_SHA256=d10de97457b479bf2adac26e8c4acbc21b78357b7f9bf75dbdd525cdc8914dcc
ARG K_URL=${BASE}/K.mp4
ARG K_SHA256=d7adcfcf7516416dd92f5d5df262f7d1b7fa05b58039ef3c9ba32e541ac187c2
ARG L_URL=${BASE}/L.mp4
ARG L_SHA256=701449ad1dc32cf839804773d65e97820407dbca7fb9c5afd727cda33359203f
ARG M_URL=${BASE}/M.mp4
ARG M_SHA256=cd96a70a7a9661c9535b7352f2384e4b2fc8d7f0ee49d8c7cb9741c2da1937f8
ARG N_URL=${BASE}/N.mp4
ARG N_SHA256=cd3682cf1c9f9eb781bedca73e161db5dd2a745ef587abe511740ccbd7c9a406
ARG O_URL=${BASE}/O.mp4
ARG O_SHA256=df227e3e8b928badb1908c041b2c72189005e23c7bf62388200f557e16cb042d
ARG P_URL=${BASE}/P.mp4
ARG P_SHA256=68f19ff29ef03a7bcc315e08118a3d7333a9f0f740948842e1f4a63cfb714dda
ARG Q_URL=${BASE}/Q.mp4
ARG Q_SHA256=ecc3b2eb170e2ca392d5a4beee29f7dad4c0983b89a52e08cdae949b35f404d0
ARG R_URL=${BASE}/R.mp4
ARG R_SHA256=707f57379c1e451b3a9280fb5c51fb3ee23762b3ad35730457facb9ba571667e
ARG S_URL=${BASE}/S.mp4
ARG S_SHA256=d1e33ee9e0e9b986b991671da7b89124a0fc14a6e9fb53fafc6c99afa3d2b802
ARG T_URL=${BASE}/T.mp4
ARG T_SHA256=b4034f6a26ec3bb6ca2e9d5102cd05827f8cdfd5a03ad54fd5d88618d522cbc6
ARG U_URL=${BASE}/U.mp4
ARG U_SHA256=f7760be1b7397e1c6b3fd8fe686c355632d243c40bd5d32e01856af0d6493059
ARG V_URL=${BASE}/V.mp4
ARG V_SHA256=a1facab2e10a721674298ff32430049c6696912675e63d895d0300fee4a3c69a

COPY bake.sh /tmp/bake.sh
RUN chmod +x /tmp/bake.sh \
 && /tmp/bake.sh A "$A_URL" "$A_SHA256" \
 && /tmp/bake.sh B "$B_URL" "$B_SHA256" \
 && /tmp/bake.sh C "$C_URL" "$C_SHA256" \
 && /tmp/bake.sh D "$D_URL" "$D_SHA256" \
 && /tmp/bake.sh E "$E_URL" "$E_SHA256" \
 && /tmp/bake.sh F "$F_URL" "$F_SHA256" \
 && /tmp/bake.sh G "$G_URL" "$G_SHA256" \
 && /tmp/bake.sh H "$H_URL" "$H_SHA256" \
 && /tmp/bake.sh I "$I_URL" "$I_SHA256" \
 && /tmp/bake.sh J "$J_URL" "$J_SHA256" \
 && /tmp/bake.sh K "$K_URL" "$K_SHA256" \
 && /tmp/bake.sh L "$L_URL" "$L_SHA256" \
 && /tmp/bake.sh M "$M_URL" "$M_SHA256" \
 && /tmp/bake.sh N "$N_URL" "$N_SHA256" \
 && /tmp/bake.sh O "$O_URL" "$O_SHA256" \
 && /tmp/bake.sh P "$P_URL" "$P_SHA256" \
 && /tmp/bake.sh Q "$Q_URL" "$Q_SHA256" \
 && /tmp/bake.sh R "$R_URL" "$R_SHA256" \
 && /tmp/bake.sh S "$S_URL" "$S_SHA256" \
 && /tmp/bake.sh T "$T_URL" "$T_SHA256" \
 && /tmp/bake.sh U "$U_URL" "$U_SHA256" \
 && /tmp/bake.sh V "$V_URL" "$V_SHA256" \
 && rm -f /tmp/bake.sh \
 && test "$(find /baked -name '*.mp4' -size +0c | wc -l)" -eq 22

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
