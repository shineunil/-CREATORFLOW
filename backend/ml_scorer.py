import os
from PIL import Image, ImageStat
import math
from messages import msg

def calculate_brightness(stat):
    # R, G, B 평균으로 명도 계산
    r, g, b = stat.mean[:3]
    return math.sqrt(0.299 * r**2 + 0.587 * g**2 + 0.114 * b**2)

def calculate_contrast(stat):
    # R, G, B 표준편차의 평균으로 대비 추정
    r_std, g_std, b_std = stat.stddev[:3]
    return (r_std + g_std + b_std) / 3

def calculate_colorfulness(image):
    # 단순한 색채 풍부도 계산 (이미지 리사이즈 후 연산량 축소)
    img = image.resize((50, 50))
    pixels = list(img.getdata())
    rg = [abs(p[0] - p[1]) for p in pixels]
    yb = [abs(0.5 * (p[0] + p[1]) - p[2]) for p in pixels]
    
    rg_mean = sum(rg) / len(rg)
    yb_mean = sum(yb) / len(yb)
    
    rg_std = math.sqrt(sum((x - rg_mean)**2 for x in rg) / len(rg))
    yb_std = math.sqrt(sum((x - yb_mean)**2 for x in yb) / len(yb))
    
    std_root = math.sqrt(rg_std**2 + yb_std**2)
    mean_root = math.sqrt(rg_mean**2 + yb_mean**2)
    
    return std_root + (0.3 * mean_root)

def analyze_thumbnail(image_path: str) -> dict:
    """
    이미지를 분석하여 머신러닝 예측 기반(Heuristic) 썸네일 점수와 피드백을 반환합니다.
    """
    try:
        if not os.path.exists(image_path):
            return {"score": 50, "feedback": msg("score_image_missing")}

        with Image.open(image_path) as img:
            img = img.convert('RGB')
            stat = ImageStat.Stat(img)
            
            brightness = calculate_brightness(stat)
            contrast = calculate_contrast(stat)
            colorfulness = calculate_colorfulness(img)
            
            # 가중치 점수 계산 (목표치 기준)
            # 1. Brightness (Ideal: 120-180) -> Max 30 pts
            b_score = 30 - min(abs(brightness - 150), 50) * (30/50)
            
            # 2. Contrast (Ideal: > 60) -> Max 40 pts
            c_score = min(contrast, 80) * (40/80)
            
            # 3. Colorfulness (Ideal: > 50) -> Max 30 pts
            col_score = min(colorfulness, 100) * (30/100)
            
            total_score = max(min(int(b_score + c_score + col_score), 100), 10)
            
            # 피드백 생성
            feedback = []
            if total_score >= 80:
                feedback.append(msg("score_great"))
            elif total_score >= 60:
                feedback.append(msg("score_ok"))
            else:
                feedback.append(msg("score_weak"))

            if brightness < 90:
                feedback.append(msg("score_too_dark"))
            elif brightness > 220:
                feedback.append(msg("score_too_bright"))

            if colorfulness > 80:
                feedback.append(msg("score_colorful"))
                
            return {
                "score": total_score,
                "feedback": " ".join(feedback),
                "metrics": {
                    "brightness": round(brightness, 1),
                    "contrast": round(contrast, 1),
                    "colorfulness": round(colorfulness, 1)
                }
            }
    except Exception as e:
        return {"score": 0, "feedback": msg("score_error", error=e)}
