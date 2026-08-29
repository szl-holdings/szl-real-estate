# SPDX-License-Identifier: Apache-2.0
# GCR pin — Docker Hub python: and public.ecr.aws are factory exit 128.
FROM mirror.gcr.io/library/python:3.12-slim
WORKDIR /app
COPY szl_re ./szl_re
COPY app.py index.html ./
EXPOSE 7860
ENV PORT=7860
CMD ["python", "app.py"]
