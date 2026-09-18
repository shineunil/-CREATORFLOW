import os
import logging
import asyncio
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TokenRevokedError(Exception):
    """저장된 refresh_token이 만료되었거나 유저가 연동을 철회해 더 이상 사용할 수 없을 때 발생합니다."""
    pass

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

    except RefreshError as e:
        raise TokenRevokedError(str(e))
    except Exception as e:
        logger.error(f"YouTube API Error (get_video_views): {e}")
        return 0

async def update_youtube_thumbnail(youtube_video_id: str, image_file_path: str, refresh_token: str) -> bool:
    try:
        import os as _os
        file_size = _os.path.getsize(image_file_path) if _os.path.exists(image_file_path) else -1
        logger.info(f"[Thumbnail] 업로드 시작 → video={youtube_video_id} file={image_file_path} size={file_size}bytes")

        youtube = get_youtube_client(refresh_token)
        # 실제 확장자가 아닌 파일 뒤에 _id 가 붙을 수 있으므로 MIME은 jpeg 기본
        ext = image_file_path.lower().split('.')[-1]
        mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
        media_body = MediaFileUpload(image_file_path, mimetype=mime_type, chunksize=-1, resumable=True)

        request = youtube.thumbnails().set(videoId=youtube_video_id, media_body=media_body)
        response = await asyncio.to_thread(request.execute)

        # response 구조 안전하게 파싱 (items 없어도 성공으로 처리)
        try:
            thumb_url = response.get('items', [{}])[0].get('default', {}).get('url', '')
            logger.info(f"[Thumbnail] ✅ 업로드 성공 → {thumb_url or '(url 없음)'}")
        except Exception:
            logger.info(f"[Thumbnail] ✅ 업로드 성공 (응답 파싱 실패, raw={response})")
        return True

    except RefreshError as e:
        raise TokenRevokedError(str(e))
    except HttpError as e:
        logger.error(f"[Thumbnail] ❌ YouTube API HttpError {e.resp.status}: {e.content.decode('utf-8', errors='replace')}")
        return False
    except Exception as e:
        logger.error(f"[Thumbnail] ❌ 예외 발생: {type(e).__name__}: {e}", exc_info=True)
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

    except RefreshError as e:
        raise TokenRevokedError(str(e))
    except Exception as e:
        logger.error(f"YouTube API Error (update_youtube_title): {e}")
        return False

async def get_recent_videos(refresh_token: str, max_results: int = 200) -> list:
    try:
        youtube = get_youtube_client(refresh_token)
        channel_req = youtube.channels().list(part="contentDetails", mine=True)
        channel_res = await asyncio.to_thread(channel_req.execute)

        if not channel_res.get('items'):
            return []

        uploads_playlist_id = channel_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos = []
        next_page_token = None

        while len(videos) < max_results:
            fetch_count = min(50, max_results - len(videos))
            kwargs = dict(part="snippet", playlistId=uploads_playlist_id, maxResults=fetch_count)
            if next_page_token:
                kwargs["pageToken"] = next_page_token

            playlist_req = youtube.playlistItems().list(**kwargs)
            playlist_res = await asyncio.to_thread(playlist_req.execute)

            for item in playlist_res.get('items', []):
                snippet = item['snippet']
                videos.append({
                    "id": snippet['resourceId']['videoId'],
                    "title": snippet['title'],
                    "thumbnail_url": snippet['thumbnails'].get('high', {}).get('url', '')
                })

            next_page_token = playlist_res.get('nextPageToken')
            if not next_page_token:
                break

        return videos

    except RefreshError as e:
        raise TokenRevokedError(str(e))
    except Exception as e:
        logger.error(f"YouTube API Error (get_recent_videos): {e}")
        return []
