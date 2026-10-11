FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404
LABEL org.opencontainers.image.title="Turbo Image Studio for RunPod"
LABEL org.opencontainers.image.source="https://github.com/xerox7777777/runpod-turbo-image-studio"
ENV PYTHONUNBUFFERED=1 HF_HOME=/workspace/.cache/huggingface OUTPUT_DIR=/workspace/outputs
WORKDIR /app
RUN git clone https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI && cd /opt/ComfyUI && git checkout 7f7fd918ed0815c5d5ef2ccfe44bfc8e72cfd217
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt -r /opt/ComfyUI/requirements.txt && python -m pip check
COPY . /app/
RUN ln -s /app/custom_nodes/turbo_official /opt/ComfyUI/custom_nodes/turbo_official && chmod +x /app/start_app.sh && python -m ipykernel install --sys-prefix --name python3 --display-name "Python (Pod environment)"
RUN bash -n /app/start_app.sh && python -m unittest discover -s tests -v && python tests/smoke.py && python -m pip freeze > /app/installed-dependencies.txt
EXPOSE 22 8080 8188 8888
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD ["python", "/app/healthcheck.py"]
CMD ["/app/start_app.sh"]
