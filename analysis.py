import cv2
import csv
import math
import numpy as np
import mediapipe as mp

from mediapipe.tasks.python import vision
from mediapipe.tasks import python


TRUNK_RED_TH = 50
HEEL_RED_TH = 20


def to_pixel(x_norm, y_norm, w, h):
    x = min(max(x_norm, 0.0), 1.0)
    y = min(max(y_norm, 0.0), 1.0)
    return int(x * w), int(y * h)


def angle_relative_horizontal(dx, dy):
    return float(math.degrees(math.atan2(abs(dy), abs(dx))))


def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    dot = np.dot(ba, bc)
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)

    if norm_ba == 0 or norm_bc == 0:
        return 0.0

    cos_theta = dot / (norm_ba * norm_bc)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    return float(np.degrees(np.arccos(cos_theta)))


def avg_list(values):
    if len(values) == 0:
        return 0.0
    return sum(values) / len(values)


def classify_trunk(avg_trunk):
    if avg_trunk < 15:
        return "Good"
    elif avg_trunk < 25:
        return "Acceptable"
    else:
        return "Needs Improvement"


def classify_heel(avg_heel):
    if avg_heel >= 35:
        return "Good"
    elif avg_heel >= 20:
        return "Moderate"
    else:
        return "Insufficient"


def load_full_csv(full_csv_path):
    rows = []

    with open(full_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    return rows


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except:
        return default


def safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except:
        return default


def generate_pdf_report(pdf_path, pdf_records, total_reps, current_diff, ts):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("STS Heavy Model Diagnostic Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    trunk_values = [r["trunk"] for r in pdf_records if r["stage"] in ["down1", "down2", "up"]]
    heel_values = [r["heel"] for r in pdf_records if r["stage"] == "up"]
    score_values = [r["score"] for r in pdf_records if r["stage"] == "up"]

    avg_trunk = avg_list(trunk_values)
    avg_heel = avg_list(heel_values)
    avg_score = avg_list(score_values)

    trunk_level = classify_trunk(avg_trunk)
    heel_level = classify_heel(avg_heel)

    summary_data = [
        ["Item", "Value"],
        ["Date / Time", ts],
        ["Difficulty", current_diff],
        ["Model", "MediaPipe Pose Landmarker Heavy"],
        ["Total Repetitions", str(total_reps)],
        ["Average Score", f"{avg_score:.1f}"],
        ["Average Trunk Lean Angle", f"{avg_trunk:.1f}"],
        ["Trunk Lean Level", trunk_level],
        ["Average Heel Raise Angle", f"{avg_heel:.1f}"],
        ["Heel Raise Level", heel_level],
    ]

    summary_table = Table(summary_data, colWidths=[210, 280])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(Paragraph("1. Summary", styles["Heading2"]))
    elements.append(summary_table)
    elements.append(Spacer(1, 18))

    elements.append(Paragraph("2. Movement Records", styles["Heading2"]))

    if len(pdf_records) == 0:
        elements.append(Paragraph("No movement records were collected.", styles["Normal"]))
    else:
        table_data = [["Rep", "Time", "Stage", "Hip", "Knee", "Trunk", "Heel", "Score"]]

        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]

        for i, r in enumerate(pdf_records, start=1):
            table_data.append([
                r["counter"],
                f'{r["time"]:.2f}',
                r["stage"],
                f'{r["hip"]:.1f}',
                f'{r["knee"]:.1f}',
                f'{r["trunk"]:.1f}',
                f'{r["heel"]:.1f}',
                f'{r["score"]:.1f}',
            ])

            if r["trunk"] >= TRUNK_RED_TH:
                table_style.append(("TEXTCOLOR", (5, i), (5, i), colors.red))

            if r["heel"] < HEEL_RED_TH and r["stage"] == "up":
                table_style.append(("TEXTCOLOR", (6, i), (6, i), colors.red))

        record_table = Table(table_data, colWidths=[45, 55, 55, 55, 55, 65, 65, 60])
        record_table.setStyle(TableStyle(table_style))
        elements.append(record_table)

    elements.append(Spacer(1, 18))

    elements.append(Paragraph("3. Diagnostic Notes", styles["Heading2"]))

    notes = []

    if len(pdf_records) == 0:
        notes.append("No exercise records were detected.")
    else:
        notes.append(f"Trunk forward lean level: {trunk_level}.")
        notes.append(f"Heel raise level: {heel_level}.")

        if trunk_level == "Needs Improvement":
            notes.append("Trunk forward lean was high. Improve trunk control.")
        elif trunk_level == "Acceptable":
            notes.append("Trunk forward lean was acceptable. Keep practicing.")
        else:
            notes.append("Good trunk control was observed. Maintain this pattern.")

        if heel_level == "Insufficient":
            notes.append("The heel raise angle was insufficient and did not reach the target level. Please continue training.")
        elif heel_level == "Moderate":
            notes.append("The heel raise performance was acceptable. Please continue training to achieve better results.")
        else:
            notes.append("The heel raise performance was good.")

    for n in notes:
        elements.append(Paragraph("- " + n, styles["Normal"]))
        elements.append(Spacer(1, 6))

    doc.build(elements)


def analyze_video_with_heavy(
    raw_video_path,
    full_csv_path,
    output_csv_path,
    output_pdf_path,
    total_reps,
    current_diff,
    ts
):
    print("Start heavy analysis:", raw_video_path)

    full_rows = load_full_csv(full_csv_path)
    full_rows_by_frame = {
        safe_int(row.get("frame_idx", -1)): row
        for row in full_rows
    }


    base_options = python.BaseOptions(
        model_asset_path="pose_landmarker_heavy.task"
    )

    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        min_tracking_confidence=0.5,
        min_pose_detection_confidence=0.5,
        running_mode=vision.RunningMode.VIDEO
    )

    cap = cv2.VideoCapture(raw_video_path)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {raw_video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 1:
        fps = 30

    heavy_pdf_records = []

    last_stage_for_pdf = None
    current_pdf_idx = None

    stage_trunk_values = []
    stage_heel_values = []
    stage_score_values = []

    with open(output_csv_path, "w", newline="", encoding="utf-8") as csv_f:
        csv_w = csv.writer(csv_f)

        csv_w.writerow([
            "frame_idx",
            "video_time_ms",
            "stage",
            "rep",
            "hip_angle_heavy",
            "knee_angle_heavy",
            "trunk_vert_heavy",
            "heel_angle_heavy",
            "score_full"
        ])

        frame_idx = 0

        with vision.PoseLandmarker.create_from_options(options) as landmarker:
            while cap.isOpened():
                ret, frame = cap.read()

                if not ret:
                    break

                h_img, w_img, _ = frame.shape
                video_time_ms = int((frame_idx / fps) * 1000)

                full_row = full_rows_by_frame.get(frame_idx)

                if full_row is not None:
                    stage = full_row.get("stage", "")
                    rep = safe_int(full_row.get("rep", 0))
                    score = safe_float(full_row.get("score", 0.0))
                else:
                    stage = ""
                    rep = 0
                    score = 0.0

                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=image_rgb
                )

                results = landmarker.detect_for_video(mp_image, video_time_ms)

                if results.pose_landmarks:
                    landmarks = results.pose_landmarks[0]

                    shoulder_r = to_pixel(landmarks[12].x, landmarks[12].y, w_img, h_img)
                    shoulder_l = to_pixel(landmarks[11].x, landmarks[11].y, w_img, h_img)

                    hip_r = to_pixel(landmarks[24].x, landmarks[24].y, w_img, h_img)
                    hip_l = to_pixel(landmarks[23].x, landmarks[23].y, w_img, h_img)

                    knee_r = to_pixel(landmarks[26].x, landmarks[26].y, w_img, h_img)
                    knee_l = to_pixel(landmarks[25].x, landmarks[25].y, w_img, h_img)

                    ankle_r = to_pixel(landmarks[28].x, landmarks[28].y, w_img, h_img)
                    ankle_l = to_pixel(landmarks[27].x, landmarks[27].y, w_img, h_img)

                    heel_r = to_pixel(landmarks[30].x, landmarks[30].y, w_img, h_img)
                    toes_r = to_pixel(landmarks[32].x, landmarks[32].y, w_img, h_img)

                    shoulder = (
                        (shoulder_r[0] + shoulder_l[0]) // 2,
                        (shoulder_r[1] + shoulder_l[1]) // 2
                    )

                    hip = (
                        (hip_r[0] + hip_l[0]) // 2,
                        (hip_r[1] + hip_l[1]) // 2
                    )

                    knee = (
                        (knee_r[0] + knee_l[0]) // 2,
                        (knee_r[1] + knee_l[1]) // 2
                    )

                    ankle = (
                        (ankle_r[0] + ankle_l[0]) // 2,
                        (ankle_r[1] + ankle_l[1]) // 2
                    )

                    heel_dx = heel_r[0] - toes_r[0]
                    heel_dy = heel_r[1] - toes_r[1]
                    angle_heel = angle_relative_horizontal(heel_dx, heel_dy)

                    trunk_dx = shoulder[0] - hip[0]
                    trunk_dy = shoulder[1] - hip[1]
                    trunk_vert = 90 - angle_relative_horizontal(trunk_dx, trunk_dy)

                    angle_hip = calculate_angle(shoulder, hip, knee)
                    angle_knee = calculate_angle(hip, knee, ankle)

                    csv_w.writerow([
                        frame_idx,
                        video_time_ms,
                        stage,
                        rep,
                        angle_hip,
                        angle_knee,
                        trunk_vert,
                        angle_heel,
                        score
                    ])

                    # 用 full 的 stage / rep / score，加上 heavy 的角度，產生 PDF 紀錄
                    if stage not in ["", "None", None]:
                        record_time = video_time_ms / 1000

                        if last_stage_for_pdf is None:
                            heavy_pdf_records.append({
                                "counter": int(rep),
                                "time": float(record_time),
                                "stage": str(stage),
                                "hip": float(angle_hip),
                                "knee": float(angle_knee),
                                "trunk": float(trunk_vert),
                                "heel": float(angle_heel),
                                "score": float(score),
                            })

                            current_pdf_idx = len(heavy_pdf_records) - 1
                            last_stage_for_pdf = stage

                            stage_trunk_values = []
                            stage_heel_values = []
                            stage_score_values = []

                        elif stage != last_stage_for_pdf:
                            if current_pdf_idx is not None:
                                if len(stage_trunk_values) > 0:
                                    heavy_pdf_records[current_pdf_idx]["trunk"] = float(max(stage_trunk_values))
                                if len(stage_heel_values) > 0:
                                    heavy_pdf_records[current_pdf_idx]["heel"] = float(max(stage_heel_values))
                                if len(stage_score_values) > 0:
                                    heavy_pdf_records[current_pdf_idx]["score"] = float(max(stage_score_values))

                            heavy_pdf_records.append({
                                "counter": int(rep),
                                "time": float(record_time),
                                "stage": str(stage),
                                "hip": float(angle_hip),
                                "knee": float(angle_knee),
                                "trunk": float(trunk_vert),
                                "heel": float(angle_heel),
                                "score": float(score),
                            })

                            current_pdf_idx = len(heavy_pdf_records) - 1
                            last_stage_for_pdf = stage

                            stage_trunk_values = []
                            stage_heel_values = []
                            stage_score_values = []

                        stage_trunk_values.append(trunk_vert)
                        stage_heel_values.append(angle_heel)
                        stage_score_values.append(score)

                else:
                    csv_w.writerow([
                        frame_idx,
                        video_time_ms,
                        stage,
                        rep,
                        "",
                        "",
                        "",
                        "",
                        score
                    ])

                frame_idx += 1

    cap.release()

    # 補最後一段 stage 的最大值
    if current_pdf_idx is not None:
        if len(stage_trunk_values) > 0:
            heavy_pdf_records[current_pdf_idx]["trunk"] = float(max(stage_trunk_values))
        if len(stage_heel_values) > 0:
            heavy_pdf_records[current_pdf_idx]["heel"] = float(max(stage_heel_values))
        if len(stage_score_values) > 0:
            heavy_pdf_records[current_pdf_idx]["score"] = float(max(stage_score_values))

    print("Heavy CSV saved:", output_csv_path)

    generate_pdf_report(
        pdf_path=output_pdf_path,
        pdf_records=heavy_pdf_records,
        total_reps=total_reps,
        current_diff=current_diff,
        ts=ts
    )

    print("Heavy PDF saved:", output_pdf_path)
