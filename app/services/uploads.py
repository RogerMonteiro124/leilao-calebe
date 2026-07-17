import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.settings import settings


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def save_image(upload: UploadFile | None) -> str | None:
    if not upload or not upload.filename:
        return None
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS or upload.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie uma imagem JPG, PNG ou WEBP")

    data = await upload.read()
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imagem excede o limite permitido")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{secrets.token_urlsafe(18)}{ext}"
    path = settings.upload_dir / filename
    path.write_bytes(data)
    return f"/static/uploads/{filename}"
