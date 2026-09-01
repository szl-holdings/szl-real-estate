# SPDX-License-Identifier: Apache-2.0
# GCR pin — Docker Hub python: and public.ecr.aws are factory exit 128.
FROM mirror.gcr.io/library/python:3.12-slim
WORKDIR /app
RUN python -m pip install --no-cache-dir "https://github.com/szl-holdings/szl-substrate/archive/ad2e04374717ef79dbf7dbb91aea5a8480ed10c3.tar.gz"
COPY szl_re ./szl_re
COPY app.py index.html szl_space_brain.py ./
EXPOSE 7860
ENV PORT=7860
CMD ["python", "app.py"]
