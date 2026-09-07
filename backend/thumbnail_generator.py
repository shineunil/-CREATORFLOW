import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageStat

from ml_scorer import calculate_brightness, calculate_contrast, calculate_colorfulness

# Black Han Sans: 한글/영문/숫자를 모두 지원하는 볼드 디스플레이 폰트 (OFL 라이선스).
# 이 앱의 주 사용자층이 한국 크리에이터라, 한글이 깨지지 않는 폰트를 기본으로 쓴다.
# (참고: Anton은 라틴 문자 전용이라 한글 헤드라인이 네모(tofu)로 깨졌었음)
FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "fonts", "BlackHanSans-Regular.ttf")

# ml_scorer.analyze_thumbnail이 만점을 주는 구간에 맞춘 목표치
TARGET_BRIGHTNESS = 150
TARGET_CONTRAST = 70
TARGET_COLORFULNESS = 65

THUMBNAIL_SIZE = (1280, 720)  # YouTube 권장 해상도 (16:9)


def _auto_enhance(img: Image.Image) -> Image.Image:
    """ml_scorer가 정의한 이상적인 명도/대비/채도 타깃 쪽으로 이미지를 보정한다."""
    stat = ImageStat.Stat(img)
    brightness = calculate_brightness(stat)
    if brightness > 0:
        factor = max(0.7, min(1.4, TARGET_BRIGHTNESS / brightness))
        img = ImageEnhance.Brightness(img).enhance(factor)

    stat = ImageStat.Stat(img)
    contrast = calculate_contrast(stat)
    if contrast > 0:
        factor = max(0.9, min(1.6, TARGET_CONTRAST / contrast))
        img = ImageEnhance.Contrast(img).enhance(factor)

    colorfulness = calculate_colorfulness(img)
    if colorfulness > 0:
        factor = max(1.0, min(1.4, TARGET_COLORFULNESS / max(colorfulness, 1)))
        img = ImageEnhance.Color(img).enhance(factor)

    return img


def _fit_to_thumbnail(img: Image.Image, size=THUMBNAIL_SIZE) -> Image.Image:
    """가운데 기준으로 크롭해 16:9 비율로 맞춘 뒤 목표 해상도로 리사이즈한다."""
    target_ratio = size[0] / size[1]
    w, h = img.size
    current_ratio = w / h

    # 매우 극단적인 종횡비(예: 가로 1px짜리 크롭)의 베이스 이미지는 new_w/new_h가 0으로
    # 반올림될 수 있는데, 0 높이/너비 이미지를 resize()하면 Pillow가 예외를 던진다.
    # 항상 최소 1px은 남도록 clamp한다.
    if current_ratio > target_ratio:
        new_w = max(1, int(h * target_ratio))
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = max(1, int(w / target_ratio))
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    return img.resize(size, Image.LANCZOS)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_with_outline(draw, position, text, font, fill, outline_fill, outline_width):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx * dx + dy * dy <= outline_width * outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_fill)
    draw.text(position, text, font=font, fill=fill)


def generate_thumbnail(base_image_path: str, headline: str, output_path: str) -> dict:
    """
    베이스 이미지를 16:9 유튜브 썸네일 규격으로 정리하고, 명도/대비/채도를
    ml_scorer 이상적 기준에 맞춰 자동 보정한 뒤, 헤드라인 문구를 큰 볼드체로 얹는다.
    외부 AI 이미지 생성 API를 사용하지 않으므로 호출당 비용이 없다.
    """
    with Image.open(base_image_path) as img:
        img = img.convert("RGB")
        img = _fit_to_thumbnail(img)
        img = _auto_enhance(img)

        draw = ImageDraw.Draw(img)
        w, h = img.size

        font_size = int(h * 0.14)
        font = ImageFont.truetype(FONT_PATH, font_size)

        max_text_width = int(w * 0.9)
        lines = _wrap_text(headline.upper(), font, max_text_width, draw)

        # 3줄을 넘으면 폰트를 줄여가며 다시 줄바꿈 (최소 크기까지)
        while len(lines) > 3 and font_size > 28:
            font_size -= 4
            font = ImageFont.truetype(FONT_PATH, font_size)
            lines = _wrap_text(headline.upper(), font, max_text_width, draw)

        line_height = int(font_size * 1.15)
        total_text_height = line_height * len(lines)
        y = h - total_text_height - int(h * 0.06)
        outline_width = max(3, font_size // 18)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x = (w - line_width) // 2
            _draw_text_with_outline(
                draw, (x, y), line, font,
                fill=(255, 255, 255), outline_fill=(0, 0, 0), outline_width=outline_width
            )
            y += line_height

        img.save(output_path, "JPEG", quality=92)

    return {"width": w, "height": h, "lines": lines, "font_size": font_size}
