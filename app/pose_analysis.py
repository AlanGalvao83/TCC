import cv2
import numpy as np
import math
import os
from pathlib import Path
import urllib.request
import mediapipe as mp
import uuid
try:
    import imageio
    _HAS_IMAGEIO = True
except Exception:
    _HAS_IMAGEIO = False
try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False
mp_pose = None
try:
    from mediapipe import solutions as mp_solutions
    mp_pose = mp_solutions.pose
except Exception:
    try:
        mp_pose = mp.solutions.pose
    except Exception:
        mp_pose = None
try:
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
except Exception:
    mp_python = None
    mp_vision = None

_TARGETS = {
    "trunk": {"min": 4.0, "max": 8.0, "ideal": 6.0, "label": "inclinação do tronco"},
    "knee": {"min": 150.0, "max": 170.0, "ideal": 160.0, "label": "ângulo do joelho"},
    "hip": {"min": 165.0, "max": 175.0, "ideal": 170.0, "label": "ângulo do quadril"},
    "ankle": {"min": 80.0, "max": 100.0, "ideal": 90.0, "label": "ângulo do tornozelo"},
}

def _angle(a, b, c):
    ab = np.array([a[0] - b[0], a[1] - b[1]])
    cb = np.array([c[0] - b[0], c[1] - b[1]])
    nab = ab / (np.linalg.norm(ab) + 1e-8)
    ncb = cb / (np.linalg.norm(cb) + 1e-8)
    cosang = np.clip(np.dot(nab, ncb), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))

def _angle_to_vertical(p1, p2):
    v = np.array([p2[0] - p1[0], p2[1] - p1[1]])
    nv = v / (np.linalg.norm(v) + 1e-8)
    vertical = np.array([0.0, -1.0])
    cosang = np.clip(np.dot(nv, vertical), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))

def _get_point(lms, idx):
    lm = lms[idx]
    return (lm.x, lm.y)

def _compute_frame_metrics_solutions(lms):
    left_shoulder = _get_point(lms, mp_pose.PoseLandmark.LEFT_SHOULDER.value)
    right_shoulder = _get_point(lms, mp_pose.PoseLandmark.RIGHT_SHOULDER.value)
    left_hip = _get_point(lms, mp_pose.PoseLandmark.LEFT_HIP.value)
    right_hip = _get_point(lms, mp_pose.PoseLandmark.RIGHT_HIP.value)
    left_knee = _get_point(lms, mp_pose.PoseLandmark.LEFT_KNEE.value)
    right_knee = _get_point(lms, mp_pose.PoseLandmark.RIGHT_KNEE.value)
    left_ankle = _get_point(lms, mp_pose.PoseLandmark.LEFT_ANKLE.value)
    right_ankle = _get_point(lms, mp_pose.PoseLandmark.RIGHT_ANKLE.value)
    left_foot = _get_point(lms, mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value)
    right_foot = _get_point(lms, mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value)
    left_trunk = _angle_to_vertical(left_hip, left_shoulder)
    right_trunk = _angle_to_vertical(right_hip, right_shoulder)
    left_knee_ang = _angle(left_hip, left_knee, left_ankle)
    right_knee_ang = _angle(right_hip, right_knee, right_ankle)
    left_hip_ang = _angle(left_shoulder, left_hip, left_knee)
    right_hip_ang = _angle(right_shoulder, right_hip, right_knee)
    left_ankle_ang = _angle(left_knee, left_ankle, left_foot)
    right_ankle_ang = _angle(right_knee, right_ankle, right_foot)
    return {
        "left": {
            "trunk": left_trunk,
            "knee": left_knee_ang,
            "hip": left_hip_ang,
            "ankle": left_ankle_ang,
        },
        "right": {
            "trunk": right_trunk,
            "knee": right_knee_ang,
            "hip": right_hip_ang,
            "ankle": right_ankle_ang,
        },
    }
def _compute_frame_metrics_tasks(lms):
    left_shoulder = _get_point(lms, 11)
    right_shoulder = _get_point(lms, 12)
    left_hip = _get_point(lms, 23)
    right_hip = _get_point(lms, 24)
    left_knee = _get_point(lms, 25)
    right_knee = _get_point(lms, 26)
    left_ankle = _get_point(lms, 27)
    right_ankle = _get_point(lms, 28)
    left_foot = _get_point(lms, 31)
    right_foot = _get_point(lms, 32)
    left_trunk = _angle_to_vertical(left_hip, left_shoulder)
    right_trunk = _angle_to_vertical(right_hip, right_shoulder)
    left_knee_ang = _angle(left_hip, left_knee, left_ankle)
    right_knee_ang = _angle(right_hip, right_knee, right_ankle)
    left_hip_ang = _angle(left_shoulder, left_hip, left_knee)
    right_hip_ang = _angle(right_shoulder, right_hip, right_knee)
    left_ankle_ang = _angle(left_knee, left_ankle, left_foot)
    right_ankle_ang = _angle(right_knee, right_ankle, right_foot)
    return {
        "left": {
            "trunk": left_trunk,
            "knee": left_knee_ang,
            "hip": left_hip_ang,
            "ankle": left_ankle_ang,
        },
        "right": {
            "trunk": right_trunk,
            "knee": right_knee_ang,
            "hip": right_hip_ang,
            "ankle": right_ankle_ang,
        },
    }

def _aggregate(metrics_list):
    keys = ["trunk", "knee", "hip", "ankle"]
    sides = ["left", "right"]
    agg = {"left": {}, "right": {}}
    for side in sides:
        for k in keys:
            vals = [m[side][k] for m in metrics_list if not math.isnan(m[side][k])]
            agg[side][k] = float(np.median(vals)) if vals else float("nan")
    return agg

def _frame_score(metrics):
    score = 0.0
    for side in ["left", "right"]:
        for k in ["trunk", "knee", "hip", "ankle"]:
            val = metrics[side][k]
            if math.isnan(val):
                score += 999.0
            else:
                score += abs(val - _TARGETS[k]["ideal"])
    return float(score)

def _norm(v):
    n = np.linalg.norm(v)
    if n < 1e-8:
        return np.array([0.0, 0.0], dtype=float)
    return v / n

def _rot(v, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([v[0]*c - v[1]*s, v[0]*s + v[1]*c], dtype=float)

def _extract_points_solutions(lms, width, height):
    return {
        "left": {
            "shoulder": (int(lms[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x * width), int(lms[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y * height)),
            "hip": (int(lms[mp_pose.PoseLandmark.LEFT_HIP.value].x * width), int(lms[mp_pose.PoseLandmark.LEFT_HIP.value].y * height)),
            "knee": (int(lms[mp_pose.PoseLandmark.LEFT_KNEE.value].x * width), int(lms[mp_pose.PoseLandmark.LEFT_KNEE.value].y * height)),
            "ankle": (int(lms[mp_pose.PoseLandmark.LEFT_ANKLE.value].x * width), int(lms[mp_pose.PoseLandmark.LEFT_ANKLE.value].y * height)),
            "foot": (int(lms[mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value].x * width), int(lms[mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value].y * height)),
        },
        "right": {
            "shoulder": (int(lms[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x * width), int(lms[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y * height)),
            "hip": (int(lms[mp_pose.PoseLandmark.RIGHT_HIP.value].x * width), int(lms[mp_pose.PoseLandmark.RIGHT_HIP.value].y * height)),
            "knee": (int(lms[mp_pose.PoseLandmark.RIGHT_KNEE.value].x * width), int(lms[mp_pose.PoseLandmark.RIGHT_KNEE.value].y * height)),
            "ankle": (int(lms[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x * width), int(lms[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y * height)),
            "foot": (int(lms[mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value].x * width), int(lms[mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value].y * height)),
        },
    }

def _extract_points_tasks(lms, width, height):
    return {
        "left": {
            "shoulder": (int(lms[11].x * width), int(lms[11].y * height)),
            "hip": (int(lms[23].x * width), int(lms[23].y * height)),
            "knee": (int(lms[25].x * width), int(lms[25].y * height)),
            "ankle": (int(lms[27].x * width), int(lms[27].y * height)),
            "foot": (int(lms[31].x * width), int(lms[31].y * height)),
        },
        "right": {
            "shoulder": (int(lms[12].x * width), int(lms[12].y * height)),
            "hip": (int(lms[24].x * width), int(lms[24].y * height)),
            "knee": (int(lms[26].x * width), int(lms[26].y * height)),
            "ankle": (int(lms[28].x * width), int(lms[28].y * height)),
            "foot": (int(lms[32].x * width), int(lms[32].y * height)),
        },
    }

def _ideal_chain_points(p):
    shoulder = np.array(p["shoulder"], dtype=float)
    hip = np.array(p["hip"], dtype=float)
    knee = np.array(p["knee"], dtype=float)
    ankle = np.array(p["ankle"], dtype=float)
    foot = np.array(p["foot"], dtype=float)
    trunk_len = np.linalg.norm(shoulder - hip)
    sx = 1.0 if (shoulder[0] - hip[0]) >= 0 else -1.0
    trunk_dir = _norm(np.array([sx * math.sin(math.radians(_TARGETS["trunk"]["ideal"])), -math.cos(math.radians(_TARGETS["trunk"]["ideal"]))], dtype=float))
    shoulder_i = hip + trunk_dir * trunk_len
    u_hip = _norm(shoulder - hip)
    v_curr_hip = _norm(knee - hip)
    base_hip = -u_hip
    hip_off = 180.0 - _TARGETS["hip"]["ideal"]
    sign_hip = 1.0 if (base_hip[0] * v_curr_hip[1] - base_hip[1] * v_curr_hip[0]) >= 0 else -1.0
    knee_i = hip + _rot(base_hip, sign_hip * hip_off) * np.linalg.norm(knee - hip)
    u_knee = _norm(hip - knee)
    v_curr_knee = _norm(ankle - knee)
    base_knee = -u_knee
    knee_off = 180.0 - _TARGETS["knee"]["ideal"]
    sign_knee = 1.0 if (base_knee[0] * v_curr_knee[1] - base_knee[1] * v_curr_knee[0]) >= 0 else -1.0
    ankle_i = knee + _rot(base_knee, sign_knee * knee_off) * np.linalg.norm(ankle - knee)
    u_ankle = _norm(knee - ankle)
    v_curr_ankle = _norm(foot - ankle)
    sign_ankle = 1.0 if (u_ankle[0] * v_curr_ankle[1] - u_ankle[1] * v_curr_ankle[0]) >= 0 else -1.0
    foot_i = ankle + _rot(u_ankle, sign_ankle * _TARGETS["ankle"]["ideal"]) * np.linalg.norm(foot - ankle)
    return hip, shoulder_i, knee_i, ankle_i, foot_i

def _draw_ideal_lines(frame, pts_by_side, color=(0, 220, 255), thickness=2):
    for side in ["left", "right"]:
        p = pts_by_side[side]
        hip, shoulder_i, knee_i, ankle_i, foot_i = _ideal_chain_points(p)
        cv2.line(frame, tuple(hip.astype(int)), tuple(shoulder_i.astype(int)), color, max(3, thickness))
        cv2.line(frame, tuple(hip.astype(int)), tuple(knee_i.astype(int)), color, max(3, thickness))
        cv2.line(frame, tuple(knee_i.astype(int)), tuple(ankle_i.astype(int)), color, max(3, thickness))
        cv2.line(frame, tuple(ankle_i.astype(int)), tuple(foot_i.astype(int)), color, max(3, thickness))
        for pt in [shoulder_i, hip, knee_i, ankle_i, foot_i]:
            cv2.circle(frame, tuple(pt.astype(int)), 5, color, -1)
    return frame

def _draw_best_frame(frame, pts_by_side):
    out = frame.copy()
    yellow = (0, 220, 255)
    green = (80, 220, 120)
    for side in ["left", "right"]:
        p = pts_by_side[side]
        for k in ["shoulder", "hip", "knee", "ankle", "foot"]:
            cv2.circle(out, p[k], 5, green, -1)
    _draw_ideal_lines(out, pts_by_side, color=yellow, thickness=2)
    cv2.rectangle(out, (10, 10), (520, 38), (0, 0, 0), -1)
    cv2.putText(out, "Verde: lido | Amarelo: postura ideal", (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, yellow, 2, cv2.LINE_AA)
    return out

def _evaluate(angles):
    targets = _TARGETS
    sides = ["left", "right"]
    out = {"left": {"issues": [], "corrections": {}}, "right": {"issues": [], "corrections": {}}}
    for side in sides:
        for k, t in targets.items():
            val = angles[side][k]
            if math.isnan(val):
                out[side]["issues"].append(f"{t['label']} não detectado")
                continue
            if val < t["min"]:
                diff = round(t["min"] - val, 1)
                out[side]["issues"].append(f"{t['label']} abaixo do ideal")
                out[side]["corrections"][k] = {"valor": round(val, 1), "corrigir": diff, "direção": "aumentar"}
            elif val > t["max"]:
                diff = round(val - t["max"], 1)
                out[side]["issues"].append(f"{t['label']} acima do ideal")
                out[side]["corrections"][k] = {"valor": round(val, 1), "corrigir": diff, "direção": "reduzir"}
            else:
                out[side]["corrections"][k] = {"valor": round(val, 1), "corrigir": 0.0, "direção": "adequado"}
    summary = {"postura_ok": all(
        (not out[s]["issues"]) or all(c["corrigir"] == 0.0 for c in out[s]["corrections"].values())
        for s in sides
    )}
    return {"summary": summary, "sides": out, "angles": angles}

def process_video(path):
    cap = cv2.VideoCapture(path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
    base_dir = Path(__file__).resolve().parent.parent
    annotated_dir = base_dir / "public" / "annotated"
    annotated_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    mp4_name = f"annot_{uid}.mp4"
    webm_name = f"annot_{uid}.webm"
    gif_name = f"annot_{uid}.gif"
    best_name = f"best_{uid}.png"
    mp4_path = str(annotated_dir / mp4_name)
    webm_path = str(annotated_dir / webm_name)
    gif_path = str(annotated_dir / gif_name)
    best_path = str(annotated_dir / best_name)
    writer_cv = None
    writer_mp4 = None
    writer_webm = None
    gif_frames = []
    gif_every = 4
    gif_limit = 80
    best_score = float("inf")
    best_frame = None
    best_points = None
    if _HAS_IMAGEIO:
        try:
            writer_mp4 = imageio.get_writer(mp4_path, fps=fps_in, codec="libx264", quality=8, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"])
        except Exception:
            writer_mp4 = None
        try:
            writer_webm = imageio.get_writer(webm_path, fps=fps_in, codec="libvpx-vp9", quality=8)
        except Exception:
            writer_webm = None
    if writer_mp4 is None and writer_webm is None:
        fourcc_primary = cv2.VideoWriter_fourcc(*"avc1")
        writer_cv = cv2.VideoWriter(mp4_path, fourcc_primary, fps_in, (width, height))
        if not writer_cv.isOpened():
            fourcc_fallback = cv2.VideoWriter_fourcc(*"mp4v")
            writer_cv = cv2.VideoWriter(mp4_path, fourcc_fallback, fps_in, (width, height))
    metrics = []
    if mp_pose is not None:
        with mp_pose.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = pose.process(image)
                overlay = frame.copy()
                if res.pose_landmarks:
                    lms = res.pose_landmarks.landmark
                    m = _compute_frame_metrics_solutions(lms)
                    metrics.append(m)
                    score = _frame_score(m)
                    pts_side = _extract_points_solutions(lms, width, height)
                    if score < best_score:
                        best_score = score
                        best_frame = overlay.copy()
                        best_points = pts_side
                    pts = [(int(l.x*width), int(l.y*height)) for l in lms]
                    color = (37, 99, 235)
                    for i in range(len(pts)):
                        cv2.circle(overlay, pts[i], 3, (255,255,255), -1)
                    try:
                        for a,b in mp_pose.POSE_CONNECTIONS:
                            pa, pb = pts[a], pts[b]
                            cv2.line(overlay, pa, pb, color, 2)
                    except Exception:
                        pass
                    _draw_ideal_lines(overlay, pts_side, color=(0, 220, 255), thickness=2)
                    txtL = f"L: tronco {round(m['left']['trunk'],1)} joelho {round(m['left']['knee'],1)} quadril {round(m['left']['hip'],1)} tornozelo {round(m['left']['ankle'],1)}"
                    txtR = f"R: tronco {round(m['right']['trunk'],1)} joelho {round(m['right']['knee'],1)} quadril {round(m['right']['hip'],1)} tornozelo {round(m['right']['ankle'],1)}"
                    cv2.rectangle(overlay,(10,10),(width-10,60),(0,0,0),-1)
                    cv2.putText(overlay, txtL, (20,35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
                    cv2.putText(overlay, txtR, (20,55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
                    cv2.putText(overlay, "Amarelo: postura ideal", (20, height-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,220,255), 2, cv2.LINE_AA)
                frame_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
                if writer_mp4 is not None:
                    writer_mp4.append_data(frame_rgb)
                if writer_webm is not None:
                    writer_webm.append_data(frame_rgb)
                if writer_cv is not None:
                    writer_cv.write(overlay)
                if len(gif_frames) < gif_limit and (frame_count % gif_every == 0):
                    gif_frames.append(frame_rgb)
                if len(metrics) >= 300:
                    pass
    else:
        if mp_python is None or mp_vision is None:
            cap.release()
            if writer_cv is not None:
                writer_cv.release()
            if writer_mp4 is not None:
                writer_mp4.close()
            if writer_webm is not None:
                writer_webm.close()
            return {"summary": {"postura_ok": False}, "sides": {"left": {"issues": ["mediapipe não disponível"], "corrections": {}}, "right": {"issues": ["mediapipe não disponível"], "corrections": {}}}, "angles": {"left": {}, "right": {}}}
        models_dir = base_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        model_path = str(models_dir / "pose_landmarker_full.task")
        if not os.path.exists(model_path):
            urls = [
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
                "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
            ]
            last_err = None
            for u in urls:
                try:
                    urllib.request.urlretrieve(u, model_path)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
            if last_err is not None and not os.path.exists(model_path):
                cap.release()
                if writer_cv is not None:
                    writer_cv.release()
                if writer_mp4 is not None:
                    writer_mp4.close()
                if writer_webm is not None:
                    writer_webm.close()
                return {"summary": {"postura_ok": False}, "sides": {"left": {"issues": ["modelo não baixado"], "corrections": {}}, "right": {"issues": ["modelo não baixado"], "corrections": {}}}, "angles": {"left": {}, "right": {}}, "error": str(last_err)}
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.3,
            min_pose_presence_confidence=0.3,
            min_tracking_confidence=0.3,
            num_poses=1,
        )
        landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        fps = fps_in
        frame_index = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_index += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts = int(1000 * frame_index / fps)
            res = landmarker.detect_for_video(mp_image, ts)
            overlay = frame.copy()
            if res and res.pose_landmarks and len(res.pose_landmarks):
                lms = res.pose_landmarks[0]
                m = _compute_frame_metrics_tasks(lms)
                metrics.append(m)
                score = _frame_score(m)
                pts_side = _extract_points_tasks(lms, width, height)
                if score < best_score:
                    best_score = score
                    best_frame = overlay.copy()
                    best_points = pts_side
                pts = [(int(p.x*width), int(p.y*height)) for p in lms]
                color = (37, 99, 235)
                for i in range(len(pts)):
                    cv2.circle(overlay, pts[i], 3, (255,255,255), -1)
                connections = [(11,12),(11,23),(12,24),(23,24),(23,25),(25,27),(24,26),(26,28),(27,31),(28,32)]
                for a,b in connections:
                    pa, pb = pts[a], pts[b]
                    cv2.line(overlay, pa, pb, color, 2)
                _draw_ideal_lines(overlay, pts_side, color=(0, 220, 255), thickness=2)
                txtL = f"L: tronco {round(m['left']['trunk'],1)} joelho {round(m['left']['knee'],1)} quadril {round(m['left']['hip'],1)} tornozelo {round(m['left']['ankle'],1)}"
                txtR = f"R: tronco {round(m['right']['trunk'],1)} joelho {round(m['right']['knee'],1)} quadril {round(m['right']['hip'],1)} tornozelo {round(m['right']['ankle'],1)}"
                cv2.rectangle(overlay,(10,10),(width-10,60),(0,0,0),-1)
                cv2.putText(overlay, txtL, (20,35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
                cv2.putText(overlay, txtR, (20,55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)
                cv2.putText(overlay, "Amarelo: postura ideal", (20, height-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,220,255), 2, cv2.LINE_AA)
            frame_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
            if writer_mp4 is not None:
                writer_mp4.append_data(frame_rgb)
            if writer_webm is not None:
                writer_webm.append_data(frame_rgb)
            if writer_cv is not None:
                writer_cv.write(overlay)
            if len(gif_frames) < gif_limit and (frame_index % gif_every == 0):
                gif_frames.append(frame_rgb)
            if len(metrics) >= 300:
                pass
    cap.release()
    if writer_cv is not None:
        writer_cv.release()
    if writer_mp4 is not None:
        writer_mp4.close()
    if writer_webm is not None:
        writer_webm.close()
    gif_saved = False
    if gif_frames:
        duration = max(0.05, float(gif_every) / float(fps_in))
        if _HAS_PIL:
            try:
                pil_frames = [PILImage.fromarray(f) for f in gif_frames]
                pil_frames[0].save(
                    gif_path,
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=int(duration * 1000),
                    loop=0,
                    optimize=False,
                    disposal=2,
                )
                gif_saved = True
            except Exception:
                pass
        if (not gif_saved) and _HAS_IMAGEIO:
            try:
                imageio.mimsave(gif_path, gif_frames, format="GIF", duration=duration, loop=0)
                gif_saved = True
            except Exception:
                pass
    gif_url = f"/static/annotated/{gif_name}" if (gif_saved and os.path.exists(gif_path) and os.path.getsize(gif_path) > 0) else None
    best_url = None
    if best_frame is not None and best_points is not None:
        try:
            best_img = _draw_best_frame(best_frame, best_points)
            cv2.imwrite(best_path, best_img)
            if os.path.exists(best_path) and os.path.getsize(best_path) > 0:
                best_url = f"/static/annotated/{best_name}"
        except Exception:
            best_url = None
    if not metrics:
        return {"summary": {"postura_ok": False}, "sides": {"left": {"issues": ["postura não detectada"], "corrections": {}}, "right": {"issues": ["postura não detectada"], "corrections": {}}}, "angles": {"left": {}, "right": {}}, "overlay_url": f"/static/annotated/{mp4_name}", "overlay_alt_url": f"/static/annotated/{webm_name}" if _HAS_IMAGEIO else None, "overlay_gif_url": gif_url, "best_frame_url": best_url}
    agg = _aggregate(metrics)
    res = _evaluate(agg)
    res["overlay_url"] = f"/static/annotated/{mp4_name}"
    res["overlay_alt_url"] = f"/static/annotated/{webm_name}" if _HAS_IMAGEIO else None
    res["overlay_gif_url"] = gif_url
    res["best_frame_url"] = best_url
    return res
