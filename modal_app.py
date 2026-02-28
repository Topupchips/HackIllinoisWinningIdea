"""Deploy PharmaRisk API on Modal."""

import modal

app = modal.App("pharmarisk")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
)


@app.function(
    image=image,
    mounts=[
        modal.Mount.from_local_dir("api", remote_path="/root/api"),
        modal.Mount.from_local_dir("data/processed", remote_path="/root/data/processed"),
        modal.Mount.from_local_dir("model", remote_path="/root/model"),
    ],
    secrets=[modal.Secret.from_name("openai-secret", required=False)],
)
@modal.asgi_app()
def web():
    from api.main import app as fastapi_app
    return fastapi_app
