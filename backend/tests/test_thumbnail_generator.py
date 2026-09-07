import os
import tempfile

from PIL import Image, ImageDraw, ImageFont

from thumbnail_generator import generate_thumbnail, THUMBNAIL_SIZE, FONT_PATH


def make_base_image(path, size=(600, 900), color=(90, 110, 130)):
    Image.new("RGB", size, color=color).save(path, "JPEG")


def test_generate_thumbnail_produces_correct_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        base_path = os.path.join(tmp, "base.jpg")
        out_path = os.path.join(tmp, "out.jpg")
        make_base_image(base_path)

        result = generate_thumbnail(base_path, "Short Title", out_path)

        assert result["width"], result["height"] == THUMBNAIL_SIZE
        with Image.open(out_path) as img:
            assert img.size == THUMBNAIL_SIZE
            assert img.format == "JPEG"


def test_generate_thumbnail_wraps_long_headline_into_multiple_lines():
    with tempfile.TemporaryDirectory() as tmp:
        base_path = os.path.join(tmp, "base.jpg")
        out_path = os.path.join(tmp, "out.jpg")
        make_base_image(base_path)

        result = generate_thumbnail(base_path, "This Is A Very Long Headline That Should Wrap Onto Several Lines", out_path)

        assert len(result["lines"]) > 1
        assert len(result["lines"]) <= 3


def test_generate_thumbnail_handles_portrait_and_landscape_inputs():
    with tempfile.TemporaryDirectory() as tmp:
        for size in [(600, 900), (1600, 900), (1000, 1000)]:
            base_path = os.path.join(tmp, f"base_{size[0]}x{size[1]}.jpg")
            out_path = os.path.join(tmp, f"out_{size[0]}x{size[1]}.jpg")
            make_base_image(base_path, size=size)

            generate_thumbnail(base_path, "Test", out_path)

            with Image.open(out_path) as img:
                assert img.size == THUMBNAIL_SIZE


def test_generate_thumbnail_wraps_korean_headline_without_error():
    """한글 문구가 예외 없이 여러 줄로 감싸지는지 확인 (Anton처럼 라틴 전용 폰트로 회귀하면 깨짐)."""
    with tempfile.TemporaryDirectory() as tmp:
        base_path = os.path.join(tmp, "base.jpg")
        out_path = os.path.join(tmp, "out.jpg")
        make_base_image(base_path)

        result = generate_thumbnail(base_path, "진짜 게이밍 PC 만들었다", out_path)

        assert len(result["lines"]) >= 1
        with Image.open(out_path) as img:
            assert img.size == THUMBNAIL_SIZE


def test_font_actually_supports_hangul_glyphs():
    """
    회귀 방지: 폰트가 한글 코드포인트에 대해 진짜 글리프를 갖고 있는지 확인한다.
    지원하지 않는 폰트(예: Anton)는 한글을 .notdef(네모 tofu) 글리프로 대체하는데,
    이 경우 실제 글리프가 있는 문자와 렌더링 크기가 동일해진다.
    """
    font = ImageFont.truetype(FONT_PATH, 80)
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)

    hangul_bbox = draw.textbbox((0, 0), "가", font=font)
    notdef_bbox = draw.textbbox((0, 0), "￿", font=font)  # 어떤 폰트에도 할당되지 않는 코드포인트

    hangul_width = hangul_bbox[2] - hangul_bbox[0]
    notdef_width = notdef_bbox[2] - notdef_bbox[0]

    assert hangul_width > 0
    assert hangul_width != notdef_width
