import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import cv2, csv
import mediapipe as mp
import numpy as np
import time
import datetime
import math
import random
from mediapipe.tasks.python import vision
from mediapipe.tasks import python
from collections import deque

CALIB_MS = 10000 
HYST_DOWN_RATIO = 0.25  
HYST_UP_RATIO = 0.75    
MIN_RANGE_DEG = 30      

# ==========================================
# --- 1. 遊戲化設定：一二三木頭人 ---
# ==========================================
DIFFICULTY_SETTINGS = {
    "easy": {"green_time": (9.0, 12.0), "red_time": (2.0, 3.0), "arm_tol": 30},
    "normal": {"green_time": (6.0, 9.0), "red_time": (1.5, 2.5), "arm_tol": 25},
    "difficult": {"green_time": (3.0, 6.0), "red_time": (1.0, 1.5), "arm_tol":20}
}
#將其可以順利分成三關卡
current_diff = "normal" 
settings = DIFFICULTY_SETTINGS[current_diff]


GOAL_DISTANCE = 1000.0
counter = 0

returning_to_seat = False
stage = None
game_state = "GREEN"
state_duration = random.uniform(* settings["green_time"])
player_distance = 0.0
is_failed = False
fail_msg = ""
score_reset_start = None
rep_rewarded = False
game_start_time = None
calibrating = False
calib_start_ms = None

sts_state = 9
down_th = 110.0
up_th = 150.0
sit_knee_th = 120
stand_knee_th = 160
trunk_delta = 5
hip_delta = 20
hip_stop_change = 3
init_px_y = None
init_trunk_vert = None
prev_hip_px_y = None
hip_change = 0.0

hip_y_sit_max = 0.0  
SAFE_Y_OFFSET = 40   # 若干單位 (像素)，允許的小幅度晃動範圍
hip_min_cal = float("inf")
hip_max_cal = float("-inf")
heel_max_cal = float("-inf")
trunk_max = 0.0
#knee_score = 0.0
trunk_score = 0.0
heel_score = 0.0
score = 0
knee_min = 180.0

phase = "FACE"          # FACE: 抓臉, CALIB: 姿勢校正, GAME: 遊戲中
FACE_MS = 5000          # 抓臉階段 5 秒
face_start_ms = None
player_face_img = None

# ==========================================
# --- PDF 報告用 ---
# ==========================================
pdf_records = []
last_stage_for_pdf = None

TRUNK_RED_TH = 50     # trunk_vert >= 40：軀幹前傾較明顯，PDF 標紅
HEEL_RED_TH = 20      # angle_heel < 20：足跟抬起不足，PDF 標紅

# 額外加分與分數差額用，先初始化避免尚未坐下前變數未定義
last_score = 0
heel_last_senconds = 0
additional_score = False
add_rewarded1 = False
add_rewarded2 = False

# ==========================================
# --- 平滑化濾波設定：Moving Average Filter ---
# ==========================================
SMOOTH_N = 5  # 平均最近5幀

hip_px_y_buf = deque(maxlen=SMOOTH_N)
angle_hip_buf = deque(maxlen=SMOOTH_N)
angle_knee_buf = deque(maxlen=SMOOTH_N)
trunk_vert_buf = deque(maxlen=SMOOTH_N)
angle_heel_buf = deque(maxlen=SMOOTH_N)

def smooth_value(value, buffer):
    buffer.append(float(value))
    return sum(buffer) / len(buffer)

def angle_relative_horizontal(dx, dy):
  return float(math.degrees(math.atan2(abs(dy), abs(dx))))

def trunk_score_caculate(trunk_max):
    if trunk_max <= 15:
        return 100
    elif trunk_max >= 35:
        return 30
    else:
        return 30 + (35-trunk_max) * ( 69 /19 )

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
    angle = np.degrees(np.arccos(cos_theta))
    return angle


POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8), (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20), (11, 23),
    (12, 24), (23, 24), (23, 25), (24, 26), (25, 27), (26, 28), (27, 29),
    (28, 30), (29, 31), (30, 32), (27, 31), (28, 32)
]

def to_pixel(x_norm, y_norm, w, h):
    x = min(max(x_norm, 0.0), 1.0)
    y = min(max(y_norm, 0.0), 1.0)
    return int(x * w), int(y * h)

def draw_custom_landmarks(image, landmarks):
    h, w, _ = image.shape
    for connection in POSE_CONNECTIONS:
        start_idx, end_idx = connection[0], connection[1]
        start_point = to_pixel(landmarks[start_idx].x, landmarks[start_idx].y, w, h)
        end_point = to_pixel(landmarks[end_idx].x, landmarks[end_idx].y, w, h)
        cv2.line(image, start_point, end_point, (255, 255, 255), 2)

    for landmark in landmarks:
        x, y = int(landmark.x * w), int(landmark.y * h)
        cv2.circle(image, (x, y), 5, (0, 255, 255), -1)

def paste_circle_avatar(display_image, avatar_img, center, radius):
    h_img, w_img, _ = display_image.shape

    cx, cy = center
    x1, x2 = cx - radius, cx + radius
    y1, y2 = cy - radius, cy + radius

    # 超出畫面就不貼
    if x1 < 0 or y1 < 0 or x2 > w_img or y2 > h_img:
        return False

    size = radius * 2
    avatar = cv2.resize(avatar_img, (size, size))

    roi = display_image[y1:y2, x1:x2]

    mask = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(mask, (radius, radius), radius, 255, -1)

    mask_3 = cv2.merge([mask, mask, mask])

    roi[:] = np.where(mask_3 == 255, avatar, roi)

    # 白色圓形外框
    cv2.circle(display_image, center, radius, (255, 255, 255), 2)

    return True

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


def generate_pdf_report(pdf_path, pdf_records, total_reps, current_diff, ts):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("STS Diagnostic Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    trunk_values = [r["trunk"] for r in pdf_records if r["stage"] in ["down1", "down2", "up"]]
    heel_values = [r["heel"] for r in pdf_records if r["stage"] == "up"]
    score_values = [r["score"] for r in pdf_records if r["stage"] == "up"]

    avg_trunk = avg_list(trunk_values)
    avg_heel = avg_list(heel_values)
    avg_score = avg_list(score_values)

    trunk_level = classify_trunk(avg_trunk)
    heel_level = classify_heel(avg_heel)

    # ===== Summary =====
    summary_data = [
        ["Item", "Value"],
        ["Date / Time", ts],
        ["Difficulty", current_diff],
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

    # ===== Movement Records =====
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

    # ===== Diagnostic Notes =====
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


# --- Tasks API 設定 ---
base_options = python.BaseOptions(model_asset_path='pose_landmarker_full.task')
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    min_tracking_confidence=0.5,
    min_pose_detection_confidence=0.5,
    running_mode=vision.RunningMode.VIDEO
)

# --- 啟動鏡頭 ---
cap = cv2.VideoCapture(0)

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480 
fps_out = cap.get(cv2.CAP_PROP_FPS)
if not fps_out or fps_out <= 1:
    fps_out = 30

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs("records", exist_ok=True)

pdf_path = f"records/report_{ts}.pdf"

raw_video_path = f"records/raw_{ts}.mp4"
ann_video_path = f"records/ann_{ts}.mp4"
heavy_csv_path = f"records/metrics_heavy_{ts}.csv"
heavy_pdf_path = f"records/report_heavy_{ts}.pdf"

raw_writer = cv2.VideoWriter(raw_video_path, fourcc, fps_out, (w, h))
ann_writer = cv2.VideoWriter(ann_video_path, fourcc, fps_out, (w, h))
full_csv_path = f"records/metrics_{ts}.csv"

csv_f = open(full_csv_path, "w", newline="", encoding="utf-8")
csv_w = csv.writer(csv_f)
csv_w.writerow([
    "frame_idx", "video_time_ms",
    "t_ms", "calib",
    "phase", "game_state",
    "stage", "rep",
    "hip_angle", "knee_angle",
    "trunk_vert", "trunk_max",
    "down_th", "up_th",
    "score"
])
frame_idx = 0

try:
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            display_image = frame.copy()
            h_img, w_img, _ = display_image.shape
            t_ms = int(time.perf_counter() * 1000)

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)

            results = landmarker.detect_for_video(mp_image, t_ms)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks[0]
                # 取得各關節座標
                shoulder_px_right = to_pixel(landmarks[12].x, landmarks[12].y, w_img, h_img)
                shoulder_px_left = to_pixel(landmarks[11].x, landmarks[11].y, w_img, h_img)
                hip_px_right = to_pixel(landmarks[24].x, landmarks[24].y, w_img, h_img)
                hip_px_left = to_pixel(landmarks[23].x, landmarks[23].y, w_img, h_img)
                knee_px_right = to_pixel(landmarks[26].x, landmarks[26].y, w_img, h_img) 
                knee_px_left = to_pixel(landmarks[25].x, landmarks[25].y, w_img, h_img)
                ankle_px_right = to_pixel(landmarks[28].x, landmarks[28].y, w_img, h_img)
                ankle_px_left = to_pixel(landmarks[27].x, landmarks[27].y, w_img, h_img)
                wrist_px_right = to_pixel(landmarks[16].x, landmarks[16].y, w_img, h_img)
                wrist_px_left = to_pixel(landmarks[15].x, landmarks[15].y, w_img, h_img)

                heel_px_right = to_pixel(landmarks[30].x, landmarks[30].y, w_img, h_img)
                heel_px_left = to_pixel(landmarks[29].x, landmarks[29].y, w_img, h_img)
                toes_px_right = to_pixel(landmarks[32].x, landmarks[32].y, w_img, h_img)
                toes_px_left = to_pixel(landmarks[31].x, landmarks[31].y, w_img, h_img)

                shoulder_px = ((shoulder_px_right[0] + shoulder_px_left[0]) // 2, (shoulder_px_right[1] + shoulder_px_left[1]) // 2)
                hip_px = ((hip_px_left[0] + hip_px_right[0]) // 2, (hip_px_left[1] + hip_px_right[1]) // 2)
                hip_px_y_raw = (hip_px_right[1]+hip_px_left[1])//2
                hip_px_y = smooth_value(hip_px_y_raw, hip_px_y_buf)
                last_valid_hip_y = hip_px_y
                # 計算髖部 Y 軸速度
                # OpenCV 座標：往上 y 會變小
                # hip_change 接近 0，代表髖部幾乎停止變動
                if prev_hip_px_y is None:
                    hip_change = 0.0
                else:
                    hip_change = hip_px_y - prev_hip_px_y
                    hip_px_y = last_valid_hip_y

                prev_hip_px_y = hip_px_y

                #toes
                Knee_px = ((knee_px_left[0] + knee_px_right[0]) // 2, (knee_px_left[1] + knee_px_right[1]) // 2)
                ankle_px = ((ankle_px_left[0] + ankle_px_right[0]) // 2, (ankle_px_left[1] + ankle_px_right[1]) // 2)
                dx1 = heel_px_right[0] - toes_px_right[0]
                dy1 = heel_px_right[1] - toes_px_right[1]
                angle_heel_raw = angle_relative_horizontal(dx1,dy1)
                             
                trunk_dx = shoulder_px[0] - hip_px[0]
                trunk_dy = shoulder_px[1] - hip_px[1]
                trunk_vert_raw = 90-angle_relative_horizontal(trunk_dx, trunk_dy)
                
                angle_hip_raw  = calculate_angle(shoulder_px, hip_px, Knee_px)
                angle_knee_raw = calculate_angle(hip_px, Knee_px, ankle_px)

                #moving average filter
                angle_heel = smooth_value(angle_heel_raw, angle_heel_buf)
                trunk_vert = smooth_value(trunk_vert_raw, trunk_vert_buf)
                angle_hip  = smooth_value(angle_hip_raw, angle_hip_buf)
                angle_knee = smooth_value(angle_knee_raw, angle_knee_buf)


                raise_right_dx = shoulder_px[0] - wrist_px_right[0]
                raise_right_dy = shoulder_px[1] - wrist_px_right[1]   
                raise_left_dx = shoulder_px[0] - wrist_px_left[0]
                raise_left_dy = shoulder_px[1] - wrist_px_left[1]                
                raise_right_horz = angle_relative_horizontal(raise_right_dx, raise_right_dy)
                raise_left_horz = angle_relative_horizontal(raise_left_dx, raise_left_dy)

                
                # ==========================================
                # --- 第一階段：抓玩家臉部頭像 ---
                # ==========================================
                if phase == "FACE":
                    if face_start_ms is None:
                        face_start_ms = t_ms

                    nose_px = to_pixel(landmarks[0].x, landmarks[0].y, w_img, h_img)

                    face_size = 60
                    y1 = max(0, nose_px[1] - face_size - 20)
                    y2 = min(h_img, nose_px[1] + face_size - 20)
                    x1 = max(0, nose_px[0] - face_size)
                    x2 = min(w_img, nose_px[0] + face_size)

                    if y2 > y1 and x2 > x1:
                        face_crop = frame[y1:y2, x1:x2]
                        player_face_img = cv2.resize(face_crop, (80, 80))

                        # 在畫面上預覽目前抓到的臉
                        cv2.rectangle(display_image, (x1, y1), (x2, y2), (0, 255, 255), 2)

                    # 3 秒後進入姿勢校正
                    if (t_ms - face_start_ms) >= FACE_MS:
                        phase = "CALIB"
                        calibrating = True

                        calib_start_ms = t_ms
                        hip_min_cal = float("inf")
                        hip_max_cal = float("-inf")
                        heel_max_cal = float("-inf")


                # ==========================================
                # --- 第二階段：姿勢校正 ---
                # ==========================================
                elif phase == "CALIB":
                    draw_custom_landmarks(display_image, landmarks)

                    hip_min_cal = min(hip_min_cal, angle_hip)
                    hip_max_cal = max(hip_max_cal, angle_hip)
                    heel_max_cal = max(heel_max_cal, angle_heel)

                    if results.pose_landmarks:
                    # --- 新增：記錄校正期間髖部最靠近地面的 Y 座標 ---
                        if hip_px_y > hip_y_sit_max:
                            hip_y_sit_max = hip_px_y
                    

                    if (t_ms - calib_start_ms) >= CALIB_MS:
                        calibrating = False
                        phase = "GAME"

                        rng = hip_max_cal - hip_min_cal

                        if rng < MIN_RANGE_DEG:
                            down_th, up_th = 110.0, 150.0
                        else:
                            down_th = hip_min_cal + HYST_DOWN_RATIO * rng
                            up_th = hip_min_cal + HYST_UP_RATIO * rng

                        if heel_max_cal <= 20 or heel_max_cal > 50:
                            inti_heel = 20
                        else:
                            inti_heel = heel_max_cal * 0.7

                        #stage = "up"
                        game_start_time = time.perf_counter()
                        last_state_change = time.perf_counter()

                    
                         
                if phase == "GAME":
                    if stage!="up":
                        heeltime = 0
                    current_time_sec = time.perf_counter()
                    elapsed_time = int(current_time_sec - game_start_time)
                    
                    if not is_failed and player_distance < GOAL_DISTANCE:
                        if sts_state == 3 and rep_rewarded:
                            returning_to_seat = True
                        
                        if returning_to_seat:
                            if game_state == "WARNING":
                                if (current_time_sec - last_state_change) > state_duration:
                                    game_state = "RED"
                                    state_duration = random.uniform(*settings["red_time"])
                                    last_state_change = current_time_sec
                            elif game_state == "RED":
                                if (current_time_sec - last_state_change) > state_duration:
                                    if sts_state == 0: 
                                        returning_to_seat = False
                                        game_state = "GREEN"
                            elif game_state == "GREEN" and rep_rewarded:
                                game_state = "WARNING"
                                state_duration = random.uniform(4.0,5.0)
                                last_state_change = current_time_sec

                        # 情況 2：一般模式 (正常起立過程中)
                        #else:
                            # 只有在非撤退模式下，sts_state < 3 才會強制綠燈
                        #    if sts_state < 3 or (sts_state == 3 and not rep_rewarded):
                        #        if game_state != "GREEN":
                        #            game_state = "GREEN"
                
                        
                        if  game_state == "WARNING":
                            safe_line_y = int(hip_y_sit_max - SAFE_Y_OFFSET)
                            cv2.line(display_image, (0, safe_line_y), (w_img, safe_line_y), (0, 0, 255), 2)
                            cv2.putText(display_image, "SAFE LINE", (10, safe_line_y - 5), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                        if  game_state == "RED":                       
                            
                            if hip_px_y < (hip_y_sit_max - SAFE_Y_OFFSET):
                                is_failed = True
                                fail_msg = "Please Stay Seated!"

                            safe_line_y = int(hip_y_sit_max - SAFE_Y_OFFSET)
                            cv2.line(display_image, (0, safe_line_y), (w_img, safe_line_y), (0, 0, 255), 2)
                            cv2.putText(display_image, "SAFE LINE", (10, safe_line_y - 5), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                            

                        # 狀態 0：坐下靜止
                        if angle_hip < down_th and angle_knee < sit_knee_th and abs(hip_change) < hip_stop_change:                        
                            if sts_state == 3 or sts_state == 9: 
                                sts_state = 0
                                stage = "down"
                                score = 0
                                #本次初始基準
                                init_px_y = hip_px_y
                                init_trunk_vert = trunk_vert
                                
                                trunk_max = 0.0
                                trunk_score = 0
                                heel_score = 0
                                heel_max_cal = 0.0
                                rep_rewarded = False
                                last_score = 0
                                heel_last_senconds = 0
                                additional_score = False
                                add_rewarded1 = False
                                add_rewarded2 = False

                             # 狀態 0 → 狀態 1：軀幹開始前傾
                            if init_trunk_vert is not None:
                                trunk_max = max(trunk_max, trunk_vert)
                                trunk_score = trunk_score_caculate(trunk_max)
                                if  sts_state == 0 and (trunk_vert-init_trunk_vert) > trunk_delta:
                                    sts_state = 1
                                    stage = "down1"

                        # 狀態 1 → 狀態 2：髖部上升
                        if sts_state==0 or sts_state==1:
                            if (init_px_y - hip_px_y) > hip_delta:
                                sts_state = 2
                                stage = "down2"

                        # 狀態 2 → 狀態 3：站立完成
                        #if sts_state == 2:
                        if angle_knee > stand_knee_th and abs(hip_change) < hip_stop_change:
                            if sts_state == 9:
                                cv2.putText(display_image, "Please sit down and we'll start your training.", 
                                (w_img//2 - 180, h_img//2 + 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 15, 255), 2, cv2.LINE_AA)
                            elif sts_state==0 or sts_state==2:    
                                sts_state = 3
                                stage = "up"
                               

                        if sts_state ==3:
                            heel_max_cal = max(heel_max_cal, angle_heel)

                            if heel_max_cal > inti_heel:
                                if heel_max_cal >= 35:
                                    heel_score = 100
                                elif heel_max_cal > 15 and heel_max_cal < 35:
                                    heel_score = 30+(abs((heel_max_cal - 15) * (68 / 19)))
                                else:
                                    heel_score = 30  
                            last_score = score              
                            score = (heel_score + trunk_score) / 2
                            
                           
                        
                        if stage == "up":
                            if not rep_rewarded and game_state in ["GREEN", "WARNING"]:
                                reward_distance = max(30, score)   
                                player_distance += reward_distance
                                rep_rewarded = True
                                counter += 1
                            elif rep_rewarded:
                                player_distance += max(0,(score-last_score))
                                if angle_heel_raw >=20:
                                    heel_seconds = time.perf_counter()
                                    if additional_score == False:                            
                                        additional_score = True
                                        heel_last_senconds = heel_seconds
                                    heeltime = int(heel_seconds - heel_last_senconds)
                                    #if heeltime >= 1 and add_rewarded1 == False:
                                     #   player_distance += (math.pow(score, 1.05)-score)
                                      #  add_rewarded1 = True
                                    if heeltime >= 2 and add_rewarded2 == False: 
                                        player_distance += (math.pow(score, 1.1)-score) 
                                        add_rewarded2 = True
                                elif angle_heel_raw < 20:
                                    additional_score = False      
                                    heel_last_senconds = 0  
                                    heeltime = 0  
              
                                


                            score_reset_start = time.perf_counter() 

                        if  score_reset_start is not None:
                            if time.perf_counter() -  score_reset_start >= 10:
                                score = 0
                                score_reset_start = None

                        # ==========================
                        # PDF 紀錄：進入 stage 時先新增一列
                        # 離開 stage 時再把最大值寫回該列
                        # ==========================

                        if stage is not None:
                            if last_stage_for_pdf is None:
                                record_time = current_time_sec - game_start_time
                                pdf_records.append({
                                    "counter": int(counter),
                                    "time": float(record_time),
                                    "stage": str(stage),
                                    "hip": float(angle_hip),
                                    "knee": float(angle_knee),
                                    "trunk": float(trunk_vert),
                                    "heel": float(angle_heel),
                                    "score": float(score),
                                })
                                current_pdf_idx = len(pdf_records) - 1
                                last_stage_for_pdf = stage

                                stage_trunk_values = []
                                stage_heel_values = []
                                stage_score_values = []


                            # 如果 stage 改變，代表上一個 stage 結束
                            elif stage != last_stage_for_pdf:
                                if current_pdf_idx is not None:
                                    if len(stage_trunk_values) > 0:
                                        pdf_records[current_pdf_idx]["trunk"] = float(max(stage_trunk_values))
                                    if len(stage_heel_values) > 0:
                                        pdf_records[current_pdf_idx]["heel"] = float(max(stage_heel_values))
                                    if len(stage_score_values) > 0:
                                        pdf_records[current_pdf_idx]["score"] = float(max(stage_score_values))
                                record_time = current_time_sec - game_start_time
                                pdf_records.append({
                                    "counter": int(counter),
                                    "time": float(record_time),
                                    "stage": str(stage),
                                    "hip": float(angle_hip),
                                    "knee": float(angle_knee),
                                    "trunk": float(trunk_vert),
                                    "heel": float(angle_heel),
                                    "score": float(score),
                                })
                                current_pdf_idx = len(pdf_records) - 1
                                last_stage_for_pdf = stage
                                stage_trunk_values = []
                                stage_heel_values = []
                                stage_score_values = []

                            stage_trunk_values.append(trunk_vert)
                            stage_heel_values.append(angle_heel)
                            stage_score_values.append(score)

            # ==========================================
            # --- 純遊戲化 UI 繪圖區塊 ---
            # ==========================================   

            if phase == "FACE":
                remain = max(0, (FACE_MS - (t_ms - face_start_ms)) // 1000) if face_start_ms is not None else 0

                cv2.rectangle(display_image, (0, 0), (w_img, 70), (0, 0, 0), -1)
                cv2.putText(display_image, f'FACE CAPTURE... Look at camera. ({remain}s left)',
                            (40, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)

                if player_face_img is not None:
                    paste_circle_avatar(display_image, player_face_img, (80, 140), 40)


            elif phase == "CALIB":
                remain = max(0, (CALIB_MS - (t_ms - calib_start_ms)) // 1000)

                cv2.rectangle(display_image, (0, 0), (w_img, 60), (0, 0, 0), -1)
                cv2.putText(display_image, f'CALIBRATING... Please do 1 Squat. ({remain}s left)',
                            (50, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)

                cv2.putText(display_image, str(int(angle_hip)), (hip_px[0] + 15, hip_px[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 12, 255), 3, cv2.LINE_AA)


            elif phase == "GAME":
                # 你原本 else 裡面的遊戲 UI 全部放這裡       
          
                # 顯示分數與難度
                cv2.putText(display_image, f"Score: {int(score)}", (w_img - 220, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 15, 255), 3, cv2.LINE_AA)
                cv2.putText(display_image, f"Diff: {current_diff}", (w_img - 220, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 15, 255), 2, cv2.LINE_AA)
                cv2.putText(display_image, f"Time: {elapsed_time}s", (w_img - 220, 130),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 15, 255), 2, cv2.LINE_AA)
                cv2.putText(display_image, f"Heel time: {heeltime}s", (w_img - 220, 170),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 15, 255), 2, cv2.LINE_AA)
                # 顯示次數與階段
                cv2.putText(display_image, f"Reps: { counter}", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3, cv2.LINE_AA)
                cv2.putText(display_image, f"Stage: { stage}", (20, 90), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 15, 255), 2, cv2.LINE_AA)
                cv2.putText(display_image, f"Hip_change: {hip_change:.2f}", (20, 125), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.putText(display_image, f"heel_max: {heel_max_cal:.2f}", (20, 165), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.putText(display_image, f"angle_knee: {angle_knee:.2f}", (20, 205), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)



                # 繪製遊戲地板
                ground_y = h_img - 50
                cv2.line(display_image, (0, ground_y), (w_img, ground_y), (255, 255, 255), 4)

                # 計算玩家位置
                start_x = 80
                end_x = w_img - 150
                progress_ratio = min(1.0,  player_distance /  GOAL_DISTANCE)
                player_x = int(start_x + progress_ratio * (end_x - start_x))

                # 繪製玩家 (藍色圓形)
                
                avatar_drawn = False

                if player_face_img is not None:
                    avatar_drawn = paste_circle_avatar(
                        display_image,
                        player_face_img,
                        (player_x, ground_y - 40),
                        40
                    )

                if not avatar_drawn:
                    cv2.circle(display_image, (player_x, ground_y - 40), 40, (255, 150, 0), -1)
                    cv2.putText(display_image, "P1", (player_x - 20, ground_y - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)
                

                # 繪製大頭娃娃 (鬼)
                ghost_x = w_img - 80
                ghost_y = ground_y - 70
                ghost_radius = 60

                if  game_state == "GREEN":
                    cv2.circle(display_image, (ghost_x, ghost_y), ghost_radius, (100, 200, 100), -1)
                    cv2.putText(display_image, "SAFE", (ghost_x - 30, ghost_y - 75), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                elif  game_state == "WARNING":
                    cv2.circle(display_image, (ghost_x, ghost_y), ghost_radius, (0, 200, 255), -1)
                    cv2.putText(display_image, "sit", (ghost_x - 35, ghost_y - 85), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 255), 2)
                    #cv2.putText(display_image, "OUT!", (ghost_x - 30, ghost_y - 65), 
                                #cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 255), 2)
                                
                elif  game_state == "RED":
                    cv2.circle(display_image, (ghost_x, ghost_y), ghost_radius, (0, 0, 200), -1)
                    cv2.circle(display_image, (ghost_x - 20, ghost_y - 15), 12, (255, 255, 255), -1)
                    cv2.circle(display_image, (ghost_x + 20, ghost_y - 15), 12, (255, 255, 255), -1)
                    cv2.circle(display_image, (ghost_x - 20, ghost_y - 15), 5, (0, 0, 0), -1)
                    cv2.circle(display_image, (ghost_x + 20, ghost_y - 15), 5, (0, 0, 0), -1)
                    cv2.putText(display_image, "FREEZE!", (ghost_x - 40, ghost_y - 75), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                # 失敗或成功畫面
                if  is_failed:
                    overlay = display_image.copy()
                    cv2.rectangle(overlay, (0, 0), (w_img, h_img), (0, 0, 150), -1)
                    cv2.addWeighted(overlay, 0.4, display_image, 0.6, 0, display_image)
                    cv2.putText(display_image, "逮到你囉!", (w_img//2 - 180, h_img//2 - 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 255), 8, cv2.LINE_AA)
                    cv2.putText(display_image,  fail_msg, (w_img//2 - 190, h_img//2 + 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)
                    cv2.putText(display_image, "Press raise your hand to Try Again", (w_img//2 - 180, h_img//2 + 80), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2, cv2.LINE_AA)
                    
                elif  player_distance >=  GOAL_DISTANCE:
                    cv2.putText(display_image, "YOU WIN!", (w_img//2 - 180, h_img//2 - 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 255, 255), 8, cv2.LINE_AA)
                    cv2.putText(display_image, "Press 'R' to Play Again", (w_img//2 - 180, h_img//2 + 60), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            cv2.imshow('AI Fitness Trainer (Gamified)', display_image)
            raw_writer.write(frame)
            ann_writer.write(display_image)
            
            video_time_ms = int((frame_idx / fps_out) * 1000)
            csv_w.writerow([
                frame_idx, video_time_ms, t_ms, 
                int(calibrating), phase, game_state,
                stage, counter, angle_hip, angle_knee,
                trunk_vert, trunk_max,
                down_th,  up_th,
                score
            ])
            frame_idx += 1

            if (wrist_px_right[1]+50 < shoulder_px_right[1]) or (wrist_px_left[1]+50 < shoulder_px_left[1]):
                if is_failed or player_distance >= GOAL_DISTANCE:
                    GOAL_DISTANCE = 1000.0
                    counter = 0

                    pdf_records = []
                    last_stage_for_pdf = None
                    sts_state=9
                    game_state = "GREEN"
                    phase = "FACE"
                    calibrating = False
                    face_start_ms = None
                    calib_start_ms = None
                    player_face_img = None
                    last_state_change = time.perf_counter()
                    state_duration = random.uniform(*settings["green_time"])
                    player_distance = 0.0
                    is_failed = False
                    fail_msg = ""
                    calib_start_ms = None
                    score = 0 
                    score_reset_start = None
                    rep_rewarded = False
                    returning_to_seat = False
                    stage = None
                    last_score = 0
                    heel_last_senconds = 0
                    additional_score = False
                    add_rewarded1 = False
                    add_rewarded2 = False
                    hip_y_sit_max = 0.0
                    elapsed_time = 0
                    heeltime = 0  
                    game_start_time = time.perf_counter()

            # 鍵盤控制
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

except Exception as e:
    print(f"Error occurred: {e}")

finally:
    print("CWD =", os.getcwd())
    cap.release()
    cv2.destroyAllWindows()
    raw_writer.release()
    ann_writer.release()
    csv_f.close()

    try:
        generate_pdf_report(
            pdf_path=pdf_path,
            pdf_records=pdf_records,
            total_reps=counter,
            current_diff=current_diff,
            ts=ts
        )
        print("PDF report saved:", pdf_path)
    except Exception as pdf_e:
        print("PDF report failed:", pdf_e)
        print("If reportlab is not installed, run: pip install reportlab")

    # 2. 再把 raw video 丟給 heavy 模型分析
    try:
        from analysis import analyze_video_with_heavy

        analyze_video_with_heavy(
            raw_video_path=raw_video_path,
            full_csv_path=full_csv_path,
            output_csv_path=heavy_csv_path,
            output_pdf_path=heavy_pdf_path,
            total_reps=counter,
            current_diff=current_diff,
            ts=ts
        )

        print("Heavy analysis finished.")
        print("Heavy CSV saved:", heavy_csv_path)
        print("Heavy PDF saved:", heavy_pdf_path)

    except Exception as heavy_e:
        print("Heavy analysis failed:", heavy_e)
