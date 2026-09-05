from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class VariationCreate(BaseModel):
    name: str = Field(..., max_length=100)
    title_text: str = Field(..., max_length=200)  # 유튜브 제목 최대 100자이나 여유분 포함
    is_control: bool = False
    # 썸네일을 변경하지 않고 제목만 변경할 수도 있으므로 None 허용
    thumbnail_image_url: Optional[str] = Field(None, max_length=500)

class ABTestCreate(BaseModel):
    youtube_video_id: str = Field(..., min_length=5, max_length=20)  # 유튜브 video ID는 11자
    swap_interval_minutes: int = Field(..., ge=30, le=10080)  # 최소 30분, 최대 7일
    duration_hours: int = Field(24, ge=1, le=720)  # 최소 1시간, 최대 30일
    variations: List[VariationCreate] = Field(..., min_length=2, max_length=5)

    @field_validator('youtube_video_id')
    @classmethod
    def validate_video_id(cls, v: str) -> str:
        # 유튜브 video ID는 영문자, 숫자, 하이픈, 언더스코어만 허용
        import re
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('유효하지 않은 YouTube Video ID 형식입니다.')
        return v

class ABTestResponse(BaseModel):
    id: int
    status: str
    message: str
