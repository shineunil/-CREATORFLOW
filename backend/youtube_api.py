import os
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 구글 클라우드 콘솔에서 발급받은 환경 변수들
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def get_youtube_client(refresh_token: str):
    """
    유저의 DB에 저장된 refresh_token을 이용해 새로운 접근 권한(Access Token)을 갱신하고
    YouTube API 클라이언트 객체를 반환합니다.
    """
    credentials = Credentials(
        token=None, # access_token은 만료되었을 수 있으므로 None 처리
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

async def get_video_views(youtube_video_id: str, refresh_token: str) -> int:
    """특정 영상의 현재 실시간 조회수를 가져옵니다."""
    try:
        youtube = get_youtube_client(refresh_token)
        request = youtube.videos().list(
            part="statistics",
            id=youtube_video_id
        )
        response = request.execute()

        if not response.get('items'):
            logger.error(f"영상을 찾을 수 없습니다: {youtube_video_id}")
            return 0
            
        view_count = int(response['items'][0]['statistics'].get('viewCount', 0))
        return view_count
        
    except HttpError as e:
        logger.error(f"YouTube API 에러 (조회수 가져오기): {e}")
        return 0

async def update_youtube_thumbnail(youtube_video_id: str, image_file_path: str, refresh_token: str) -> bool:
    """지정된 이미지 파일로 유튜브 썸네일을 덮어씌웁니다."""
    try:
        youtube = get_youtube_client(refresh_token)
        
        # 윈도우 환경 등에서 mimetype을 잘못 추측하는 버그 방지를 위해 확장자로 강제 지정
        ext = image_file_path.lower().split('.')[-1]
        mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
        media_body = MediaFileUpload(image_file_path, mimetype=mime_type, chunksize=-1, resumable=True)
        
        request = youtube.thumbnails().set(
            videoId=youtube_video_id,
            media_body=media_body
        )
        response = request.execute()
        
        logger.info(f"썸네일 업데이트 성공! 반영된 이미지 URL: {response['items'][0].get('default', {}).get('url')}")
        return True
        
    except HttpError as e:
        logger.error(f"YouTube API 에러 (썸네일 업데이트 실패): {e}")
        return False

async def update_youtube_title(youtube_video_id: str, new_title: str, refresh_token: str) -> bool:
    """영상 제목을 덮어씌웁니다."""
    try:
        youtube = get_youtube_client(refresh_token)
        
        # 제목을 바꾸려면 기존 영상의 snippet 정보가 필요하므로 먼저 가져옴
        list_request = youtube.videos().list(part="snippet", id=youtube_video_id)
        list_response = list_request.execute()
        
        if not list_response.get('items'):
            return False
            
        old_snippet = list_response['items'][0]['snippet']
        
        # 업데이트할 때 읽기 전용 필드(thumbnails 등)를 포함하면 invalidVideoMetadata 에러 발생
        # 따라서 쓰기 가능한 필수/선택 필드만 추출해서 새로운 snippet 객체 생성
        update_snippet = {
            "title": new_title,
            "categoryId": old_snippet.get("categoryId", "22"), # 기본 카테고리 People & Blogs
            "description": old_snippet.get("description", "")
        }
        if "tags" in old_snippet:
            update_snippet["tags"] = old_snippet["tags"]
        if "defaultLanguage" in old_snippet:
            update_snippet["defaultLanguage"] = old_snippet["defaultLanguage"]
        
        # 업데이트 요청
        update_request = youtube.videos().update(
            part="snippet",
            body={
                "id": youtube_video_id,
                "snippet": update_snippet
            }
        )
        update_request.execute()
        
        logger.info(f"제목 업데이트 성공: {new_title}")
        return True
        
    except HttpError as e:
        logger.error(f"YouTube API 에러 (제목 업데이트 실패): {e}")
        return False

async def get_recent_videos(refresh_token: str, max_results: int = 15) -> list:
    """연동된 채널의 최근 업로드 영상을 가져옵니다."""
    try:
        youtube = get_youtube_client(refresh_token)
        
        # 1. 내 채널의 uploads 플레이리스트 ID 가져오기
        channel_req = youtube.channels().list(part="contentDetails", mine=True)
        channel_res = channel_req.execute()
        
        if not channel_res.get('items'):
            return []
            
        uploads_playlist_id = channel_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # 2. 플레이리스트에서 영상 목록 가져오기
        playlist_req = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        )
        playlist_res = playlist_req.execute()
        
        videos = []
        for item in playlist_res.get('items', []):
            snippet = item['snippet']
            videos.append({
                "id": snippet['resourceId']['videoId'],
                "title": snippet['title'],
                "thumbnail_url": snippet['thumbnails'].get('high', {}).get('url', '')
            })
            
        return videos
        
    except HttpError as e:
        logger.error(f"YouTube API 에러 (최근 영상 가져오기 실패): {e}")
        return []
