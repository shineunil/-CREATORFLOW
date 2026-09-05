import os
import logging
import asyncio
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def get_youtube_client(refresh_token: str):
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET
    )
    # 💥 (수정됨) http와 credentials를 동시에 넘기면 에러가 나므로, 타임아웃 대신 기본 인증 객체만 사용합니다.
    # 이미 모든 호출이 asyncio.to_thread로 감싸져 있어 메인 루프 데드락은 발생하지 않습니다.
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

async def get_video_views(youtube_video_id: str, refresh_token: str) -> int:
    try:
        youtube = get_youtube_client(refresh_token)
        request = youtube.videos().list(part="statistics", id=youtube_video_id)
        # Use to_thread to prevent blocking the main asyncio event loop
        response = await asyncio.to_thread(request.execute)

        if not response.get('items'):
            logger.error(f"Cannot find video: {youtube_video_id}")
            return 0
            
        view_count = int(response['items'][0]['statistics'].get('viewCount', 0))
        return view_count
        
    except Exception as e:
        logger.error(f"YouTube API Error (get_video_views): {e}")
        return 0

async def update_youtube_thumbnail(youtube_video_id: str, image_file_path: str, refresh_token: str) -> bool:
    try:
        youtube = get_youtube_client(refresh_token)
        ext = image_file_path.lower().split('.')[-1]
        mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
        media_body = MediaFileUpload(image_file_path, mimetype=mime_type, chunksize=-1, resumable=True)
        
        request = youtube.thumbnails().set(videoId=youtube_video_id, media_body=media_body)
        response = await asyncio.to_thread(request.execute)
        
        logger.info(f"Thumbnail updated: {response['items'][0].get('default', {}).get('url')}")
        return True
        
    except Exception as e:
        logger.error(f"YouTube API Error (update_youtube_thumbnail): {e}")
        return False

async def update_youtube_title(youtube_video_id: str, new_title: str, refresh_token: str) -> bool:
    try:
        youtube = get_youtube_client(refresh_token)
        list_request = youtube.videos().list(part="snippet", id=youtube_video_id)
        list_response = await asyncio.to_thread(list_request.execute)
        
        if not list_response.get('items'):
            return False
            
        old_snippet = list_response['items'][0]['snippet']
        update_snippet = {
            "title": new_title,
            "categoryId": old_snippet.get("categoryId", "22"),
            "description": old_snippet.get("description", "")
        }
        if "tags" in old_snippet:
            update_snippet["tags"] = old_snippet["tags"]
        if "defaultLanguage" in old_snippet:
            update_snippet["defaultLanguage"] = old_snippet["defaultLanguage"]
        
        update_request = youtube.videos().update(
            part="snippet",
            body={"id": youtube_video_id, "snippet": update_snippet}
        )
        await asyncio.to_thread(update_request.execute)
        
        logger.info(f"Title updated: {new_title}")
        return True
        
    except Exception as e:
        logger.error(f"YouTube API Error (update_youtube_title): {e}")
        return False

async def get_recent_videos(refresh_token: str, max_results: int = 15) -> list:
    try:
        youtube = get_youtube_client(refresh_token)
        channel_req = youtube.channels().list(part="contentDetails", mine=True)
        channel_res = await asyncio.to_thread(channel_req.execute)
        
        if not channel_res.get('items'):
            return []
            
        uploads_playlist_id = channel_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        playlist_req = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        )
        playlist_res = await asyncio.to_thread(playlist_req.execute)
        
        videos = []
        for item in playlist_res.get('items', []):
            snippet = item['snippet']
            videos.append({
                "id": snippet['resourceId']['videoId'],
                "title": snippet['title'],
                "thumbnail_url": snippet['thumbnails'].get('high', {}).get('url', '')
            })
            
        return videos
        
    except Exception as e:
        logger.error(f"YouTube API Error (get_recent_videos): {e}")
        return []
