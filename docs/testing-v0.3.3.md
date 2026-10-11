# v0.3.3 verification, October 11, 2026

The public linux/amd64 image built successfully in GitHub Actions run 38110401076, source commit 249b807. Its manifest and all 41 image layers were accessible anonymously. A fresh A40 Pod used that version, 50 GB system RAM and 100 GB container disk, with no author-owned volume.

## Completed checks

* 24 regression tests and real CPU service startup checks ran in the container build, including dependency consistency, both interfaces, authenticated Jupyter access, invalid prompt routes, missing GPU errors, workspace preservation and failure reporting.
* 19 live Jupyter/API checks passed: missing and incorrect token rejection, authenticated contents/download/upload, a valid notebook, onboarding files, seven common model folders, four saved workflows and native checkpoint filename discovery.
* 13 live GPU checks passed: 512 square generation, real eight-step progress, active cancellation inside the Turbo node with no saved canceled output, successful next request at 1024×768, editing a generated input from a red mug to a blue mug, portrait generation at 768×1024 with a Unicode prompt, and service health afterward.
* Real browser login through the RunPod proxy, notebook execution and checkpoint save, model-folder browsing, file chooser upload and Jupyter terminal commands passed. ComfyUI opened in the browser; its saved image-edit graph loaded successfully.
* A deliberate SIGTERM to ComfyUI produced a failed-service message on port 8080. Jupyter still reloaded and displayed files and the terminal. There is no automatic restart or additional GPU rental.
* PNG originals, prompt/seed/timing JSON, RGB previews, the executed notebook, resolved dependency list and logs were copied to the local verification bundle before stopping the Pod.

All three revision test Pods were read back as EXITED. Temporary test credentials and the temporarily registered SSH public key were removed.

## Observed timings

Elapsed time from queue submission to completed history, including proxy polling: red mug 46.80 seconds, landscape after cancellation 36.17 seconds, blue-mug input-image edit 32.23 seconds, portrait 33.36 seconds. The edit metadata records 30.716 seconds of inference. Active cancellation returned after 2.641 seconds and saved no canceled output. These are examples on this host, not latency guarantees or a controlled comparison with regular Qwen.

## Bugs found and patched

1. Recursive workspace-copy exclusions incorrectly omitted ComfyUI's internal `comfy_api/input` source. Exclusions now apply only to the intended workspace folders; a regression test protects internal source.
2. Jupyter's notebook checkpoint route intercepted the model directory named `checkpoints`. A narrow authenticated contents route allows the actual model directory, without replacing normal notebook checkpoint handling.
3. RunPod forwards an internal Host while the browser sends its public proxy Origin. Jupyter login rejected that combination. v0.3.3 permits only the current Pod's exact Jupyter proxy origin and retains token authentication and CSRF checks. The browser login and unrelated-origin rejection were tested.

## User's supplied failure evidence

The supplied log excerpt covers approximately 12 seconds of image extraction and container start for v0.2.6. It does not contain application startup logs or establish total load duration. The screenshot shows ComfyUI's proxy returning HTTP 403. That old Pod no longer resolved on this account when inspected. The old template also advertised an unused Gradio port, which could remain Initializing.

On the new Pod, a default Python HTTP client received Cloudflare error 1010 while a browser signature received 200 for the same endpoint. The actual browser opened ComfyUI and Jupyter. This reproduced client-signature filtering but does not prove the exact cause of the user's previous Chrome 403. Platform proxy denials remain distinct from application readiness and Jupyter token errors.

## Limits

Disk-full, permissions, download failure and OOM paths were simulated in unit tests. Physical disk exhaustion and real GPU OOM were not deliberately induced. A synthetic checkpoint file tested upload and filename discovery, not inference using another model. Additional user models/custom nodes require compatible workflows and dependencies. ComfyUI-Manager is not bundled.

Persistent storage across real stop/redeployment, other GPU types, multi-image edits and masked inpainting were not validated. The template is public and its container is anonymously pullable; a separate person's account deployment and Community Hub search listing are not confirmed. Use the direct public template link.

Official Qwen weights download lazily on the first queued Turbo request. They are not embedded in the container or shared from the author's volume.
