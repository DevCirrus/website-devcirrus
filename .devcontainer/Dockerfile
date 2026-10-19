# Official release manifests pinned by digest. Update only by reviewed PR.
FROM hashicorp/terraform:1.16.6@sha256:bfffc1ded5fbf0a17beaaf22eb4793980abdb19d0761ff6a3a0efb2ab4d9b316 AS terraform
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:589.0.0-stable@sha256:ee2115362cc5e05064ace2398593dc2489444fda581db3f61410a84c318f3066 AS gcloud
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
COPY --from=gcloud /usr/lib/google-cloud-sdk /opt/google-cloud-sdk
ENV PATH="/opt/google-cloud-sdk/bin:${PATH}" \
    CLOUDSDK_PYTHON="/usr/bin/python3" \
    CLOUDSDK_CORE_DISABLE_FILE_LOGGING="true" \
    CLOUDSDK_CORE_DISABLE_PROMPTS="1" \
    TF_IN_AUTOMATION="1"
USER vscode
# No cloud login, secrets, project creation, dependency scripts or source copied
# into the image. Codespaces mounts the reviewed checkout at runtime.
RUN terraform version -json && gcloud version && python3 --version && git --version
