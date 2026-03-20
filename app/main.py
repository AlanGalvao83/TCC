from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uuid
import shutil
import os
from .pose_analysis import process_video

base_dir = Path(__file__).resolve().parent.parent
uploads_dir = base_dir / "uploads"
public_dir = base_dir / "public"
annotated_dir = public_dir / "annotated"
uploads_dir.mkdir(parents=True, exist_ok=True)
public_dir.mkdir(parents=True, exist_ok=True)
annotated_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Verificador de Postura de Corridas")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(public_dir)), name="static")

@app.get("/")
def index():
    index_path = public_dir / "index.html"
    return FileResponse(str(index_path))

@app.post("/analyze")
async def analyze_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower() or ".mp4"
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    tmp_path = uploads_dir / tmp_name
    with tmp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        result = process_video(str(tmp_path))
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
