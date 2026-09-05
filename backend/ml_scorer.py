import os
from PIL import Image, ImageStat
import math

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
            return {"score": 50, "feedback": "이미지를 찾을 수 없습니다."}

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
                feedback.append("전반적으로 시선을 사로잡는 매우 훌륭한 썸네일입니다!")
            elif total_score >= 60:
                feedback.append("무난한 썸네일이지만 조금 더 대비를 주면 눈에 띌 수 있습니다.")
            else:
                feedback.append("어둡거나 눈에 띄지 않아 스크롤 시 묻힐 확률이 높습니다.")
                
            if brightness < 90:
                feedback.append("명도가 너무 낮아(어두움) 모바일에서 잘 안 보일 수 있습니다. 밝기를 올리세요.")
            elif brightness > 220:
                feedback.append("명도가 너무 높아 눈이 부십니다. 톤다운이 필요합니다.")
                
            if colorfulness > 80:
                feedback.append("색채가 화려하여 시선을 끌기 좋습니다.")
                
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
        return {"score": 0, "feedback": f"분석 중 오류 발생: {e}"}
