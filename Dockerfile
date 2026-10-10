FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

LABEL org.opencontainers.image.title="Turbo Image Studio for RunPod"
LABEL org.opencontainers.image.source="https://github.com/xerox7777777/runpod-turbo-image-studio"
LABEL org.opencontainers.image.description="Pod UI for text-to-image and image editing with the official Qwen Image 2.1 Turbo checkpoint"

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/workspace/.cache/huggingface \
    OUTPUT_DIR=/workspace/outputs \
    PORT=7860

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY app.py /app/app.py
COPY start_app.sh /start_app.sh
RUN chmod +x /start_app.sh

EXPOSE 22 7860
CMD ["/start_app.sh"]
