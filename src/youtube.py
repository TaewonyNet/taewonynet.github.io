import os
import re
import json
import logging
import datetime
import subprocess
import sys
import platform
import shutil

# FFmpeg 자동 설치
def download_ffmpeg_windows():
    """
    Windows에서 FFmpeg를 직접 다운로드하여 설치합니다.
    URL: https://github.com/BtbN/FFmpeg-Builds/releases
    """
    import urllib.request
    import zipfile
    
    ffmpeg_dir = os.path.dirname(__file__)
    os.makedirs(ffmpeg_dir, exist_ok=True)
    
    ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
    if os.path.exists(ffmpeg_path):
        return True
    
    print("FFmpeg를 GitHub에서 다운로드하고 있습니다 (약 2-3분 소요)...")
    
    try:
        # BtbN's FFmpeg 빌드에서 다운로드 (최신 버전)
        url = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
        zip_path = os.path.join(ffmpeg_dir, 'ffmpeg.zip')
        
        print(f"다운로드 중: {url}")
        urllib.request.urlretrieve(url, zip_path)
        print("FFmpeg 다운로드 완료, 압축 풀이 중...")
        
        # 압축 해제
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        # ffmpeg.exe와 ffprobe.exe 찾기 및 이동
        found_ffmpeg = False
        for root, dirs, files in os.walk(ffmpeg_dir):
            for file in files:
                if file in ['ffmpeg.exe', 'ffprobe.exe']:
                    src = os.path.join(root, file)
                    dst = os.path.join(ffmpeg_dir, file)
                    if src != dst:
                        shutil.move(src, dst)
                        found_ffmpeg = True
                        print(f"설치됨: {file}")
        
        # 임시 파일 정리
        if os.path.exists(zip_path):
            os.remove(zip_path)
        
        # 불필요한 폴더 삭제
        for item in os.listdir(ffmpeg_dir):
            item_path = os.path.join(ffmpeg_dir, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
        
        if found_ffmpeg and os.path.exists(ffmpeg_path):
            print(f"FFmpeg를 {ffmpeg_dir}에 설치했습니다.")
            return True
        else:
            print("FFmpeg 설치 중 문제가 발생했습니다.")
            return False
        
    except Exception as e:
        print(f"FFmpeg 다운로드 중 오류 발생: {e}")
        print("수동으로 다운로드하세요: https://github.com/BtbN/FFmpeg-Builds/releases")
        return False

def ensure_ffmpeg_installed():
    """
    FFmpeg와 ffprobe가 설치되어 있는지 확인하고, 없으면 자동 설치를 시도합니다.
    Windows: 시스템 설치 → Chocolatey → 직접 다운로드
    macOS: Homebrew
    Linux: apt 또는 yum
    """
    # 이미 설치되어 있는지 확인
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):
        print("FFmpeg가 이미 설치되어 있습니다.")
        return True
    
    # 현재 디렉토리의 ffmpeg 폴더에서 찾기
    local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
    local_ffprobe = os.path.join(os.path.dirname(__file__), 'ffprobe.exe')
    if os.path.exists(local_ffmpeg) and os.path.exists(local_ffprobe):
        print(f"로컬 FFmpeg를 발견했습니다: {local_ffmpeg}")
        return True
    
    print("FFmpeg를 설치하고 있습니다...")
    system = platform.system()
    
    try:
        if system == 'Windows':
            # 방법 1: Chocolatey 시도
            try:
                print("방법 1: Chocolatey를 사용하여 설치 중...")
                subprocess.check_call(['choco', 'install', 'ffmpeg', '-y'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                print("FFmpeg를 Chocolatey로 설치했습니다.")
                return True
            except (FileNotFoundError, subprocess.CalledProcessError):
                print("Chocolatey 설치 실패, 직접 다운로드 방식으로 진행합니다...")
            
            # 방법 2: 직접 다운로드
            return download_ffmpeg_windows()
                
        elif system == 'Darwin':  # macOS
            print("방법 1: Homebrew를 사용하여 설치 중...")
            try:
                subprocess.check_call(['brew', 'install', 'ffmpeg'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                print("FFmpeg를 Homebrew로 설치했습니다.")
                return True
            except FileNotFoundError:
                print("Homebrew를 찾을 수 없습니다.")
                print("Homebrew 설치: https://brew.sh")
                return False
            except subprocess.CalledProcessError as e:
                print(f"Homebrew 설치 실패: {e}")
                return False
                
        elif system == 'Linux':
            # Ubuntu/Debian 계열
            try:
                print("방법 1: apt를 사용하여 설치 중...")
                subprocess.check_call(['sudo', 'apt-get', 'update'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subprocess.check_call(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                print("FFmpeg를 apt로 설치했습니다.")
                return True
            except FileNotFoundError:
                pass
            
            # RHEL/CentOS/Fedora 계열
            try:
                print("방법 2: yum을 사용하여 설치 중...")
                subprocess.check_call(['sudo', 'yum', 'install', '-y', 'ffmpeg'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                print("FFmpeg를 yum으로 설치했습니다.")
                return True
            except FileNotFoundError:
                pass
            
            print("패키지 관리자를 찾을 수 없습니다. 수동으로 FFmpeg를 설치해주세요.")
            print("Ubuntu/Debian: sudo apt-get install ffmpeg")
            print("CentOS/RHEL: sudo yum install ffmpeg")
            return False
    
    except Exception as e:
        print(f"FFmpeg 설치 중 오류 발생: {e}")
        return False
    
    return False

# yt-dlp 자동 설치
try:
    import yt_dlp
except ImportError:
    print("yt-dlp를 설치하고 있습니다...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "yt-dlp[default]"])
    import yt_dlp

# FFmpeg 설치 확인
ensure_ffmpeg_installed()

class YouTubeDownloader:
    """
    YouTube 동영상 및 오디오 다운로더 클래스.
    
    yt-dlp를 이용하여 YouTube 동영상과 음원을 다운로드하고,
    메타데이터를 JSON으로 관리하며, 다운로드 상태를 추적합니다.
    """
    
    DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
    DEFAULT_CONFIG_FILE = 'YoutubeDown.json'
    
    # 기본 다운로드 포맷 (우선순위 순서)
    DEFAULT_FORMATS = {
        '1080p': 'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/best[height=1080][ext=mp4]/best[height=1080]',
        '720p': 'bestvideo[height=720][ext=mp4]+bestaudio[ext=m4a]/best[height=720][ext=mp4]/best[height=720]',
        'best': 'best[height<=720]'
    }
    
    def __init__(self, data_dir=None, config_file=None, 
                 format_preference='best', download_subtitles=True, 
                 extract_audio=True, audio_format='mp3', cookies_file=None):
        """
        YouTube 다운로더 초기화.
        
        Args:
            data_dir (str, optional): 다운로드 파일 및 로그 저장 디렉토리.
                                     미지정시 './data'
            config_file (str, optional): 메타데이터 JSON 파일명.
                                        미지정시 'YoutubeDown.json'
            format_preference (str, optional): 화질 선택.
                                             'best'(기본), '1080p', '720p'
            download_subtitles (bool, optional): 자막 다운로드 여부. 기본값: True
            extract_audio (bool, optional): 음원 추출 여부. 기본값: True
            audio_format (str, optional): 오디오 포맷. 기본값: 'mp3'
            cookies_file (str, optional): 쿠키 파일 경로. 미지정시 None
        """
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self.config_filename = config_file or self.DEFAULT_CONFIG_FILE
        self.json_file_path = os.path.join(self.data_dir, self.config_filename)
        self.log_file_path = os.path.join(self.data_dir, 'download.log')
        self.cookies_file = cookies_file
        
        self.format_preference = format_preference
        self.download_subtitles = download_subtitles
        self.extract_audio = extract_audio
        self.audio_format = audio_format
        
        # 디렉토리 생성
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 로거 설정
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """로거를 설정하고 반환합니다."""
        logger = logging.getLogger(f"YouTubeDownloader_{id(self)}")
        logger.handlers = []  # 기존 핸들러 제거
        logger.setLevel(logging.INFO)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _get_download_format(self):
        """
        포맷 선택 설정에 따라 yt-dlp 포맷 문자열을 반환합니다.
        
        주의: bestvideo+bestaudio 조합 사용 시 임시 파일(f###.mp4)이 생성될 수 있습니다.
              이를 방지하려면:
              1. 'mergeall' 옵션 사용 (권장)
              2. 단일 포맷 사용 ('best[height<=720]')
        """
        return self.DEFAULT_FORMATS.get(self.format_preference, self.DEFAULT_FORMATS['best'])

    def load_json_data(self):
        """
        JSON 메타데이터 파일을 로드하고 반환합니다.
        
        Returns:
            dict: 로드된 JSON 데이터. 파일이 없거나 손상되면 기본 구조 반환.
        """
        if os.path.exists(self.json_file_path):
            try:
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("JSON 파일 손상 감지, 새로 생성")
                return {'videos': {}}
        return {'videos': {}}

    def save_json_data(self, data):
        """
        JSON 메타데이터를 파일로 저장합니다.
        
        Args:
            data (dict): 저장할 JSON 데이터.
        """
        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def is_download_complete(self, video_info):
        """
        동영상 파일의 완료 여부를 확인합니다.
        
        Args:
            video_info (dict): 비디오 정보 (title, uploader, upload_date 포함).
        
        Returns:
            bool: 동영상 또는 오디오 파일이 1MB 이상이면 True.
        """
        title = video_info.get('title', 'Unknown')
        uploader = video_info.get('uploader', 'Unknown')
        upload_date = video_info.get('upload_date', 'NA')

        base_pattern = os.path.join(self.data_dir, uploader, f"{upload_date}_{title}")
        video_path = base_pattern + '.mp4'
        audio_path = base_pattern + f'.{self.audio_format}'

        video_exists = os.path.exists(video_path) and os.path.getsize(video_path) > 1024*1024
        audio_exists = os.path.exists(audio_path) and os.path.getsize(audio_path) > 1024*1024

        return video_exists or audio_exists

    def download_video_and_subtitle(self, youtube_video_list):
        """
        YouTube 동영상 및 자막을 다운로드합니다.
        
        Args:
            youtube_video_list (list): 다운로드할 YouTube URL 리스트.
        """
        resub = re.compile(r'[\\/:*?"<>|]+')
        download_path = os.path.join(self.data_dir, '%(uploader)s/%(upload_date>%Y%m%d)s_%(title)s.%(ext)s')

        json_data = self.load_json_data()

        # 다운로드 옵션 구성
        postprocessors = []
        if self.extract_audio:
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.audio_format,
                'preferredquality': '192'
            })

        # FFmpeg 경로 자동 감지
        ffmpeg_location = None
        if shutil.which('ffmpeg'):
            ffmpeg_location = shutil.which('ffmpeg')
        else:
            local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg.exe')
            if os.path.exists(local_ffmpeg):
                ffmpeg_location = local_ffmpeg

        ydl_opts = {
            'format': self._get_download_format(),
            'outtmpl': download_path,
            'writesubtitles': self.download_subtitles,
            'writeautomaticsub': self.download_subtitles,
            'subtitleslangs': ['ko'],
            'writethumbnail': True,
            'keepvideo': self.extract_audio,
            'postprocessors': postprocessors,
            'ignoreerrors': True,
            'nooverwrites': False,
            'concurrent_fragment_downloads': 10,
            'retries': 1,
            'cookiefile': self.cookies_file,
            'logger': self.logger,
            'merge_output_format': 'mp4',  # 포맷ID(f###) 제거를 위해 명시적으로 지정
        }
        
        # FFmpeg 경로가 있으면 추가
        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for video_url in youtube_video_list:
                try:
                    # 플레이리스트/단일 비디오 메타데이터 추출
                    info = ydl.extract_info(video_url, download=False)
                    videos = info.get('entries', [info]) if info else []

                    # 메타데이터 저장
                    for video in videos:
                        if not video:
                            continue
                        vid = video['id']
                        title = resub.sub(' ', video.get('title', 'Unknown'))
                        uploader = video.get('uploader', 'Unknown')
                        upload_date = video.get('upload_date', 'NA')

                        json_data['videos'].setdefault(vid, {
                            'title': title,
                            'uploader': uploader,
                            'url': video.get('webpage_url'),
                            'upload_date': upload_date,
                            'completed': False
                        })

                    self.save_json_data(json_data)

                    # 개별 다운로드 및 완료 검증
                    for video in videos:
                        if not video:
                            continue
                        vid = video['id']
                        entry = json_data['videos'][vid]

                        # 이미 완료된 경우 파일 존재 여부 재확인
                        if entry.get('completed'):
                            if self.is_download_complete(entry):
                                self.logger.info(f"이미 완료 및 파일 확인됨: {video.get('title', vid)} ({vid})")
                                continue
                            else:
                                self.logger.warning(f"JSON에 완료 표시지만 파일 없음 → 재다운로드: {vid}")
                                entry['completed'] = False

                        try:
                            ydl.download([video['webpage_url']])

                            # 다운로드 후 파일 존재 여부 확인
                            if self.is_download_complete(entry):
                                entry['completed'] = True
                                entry['completed_at'] = datetime.datetime.now().isoformat()
                                self.logger.info(f"다운로드 및 검증 완료: {video.get('title', vid)} ({vid})")
                            else:
                                self.logger.error(f"다운로드 실패 또는 파일 손상 → 미완료 처리: {vid}")
                                entry['completed'] = False
                                # 불완전 파일 삭제
                                base = os.path.join(self.data_dir, entry['uploader'], 
                                                   f"{entry['upload_date']}_{entry['title']}")
                                for ext in ['.mp4', f'.{self.audio_format}', '.part', '.f4v', '.m4a']:
                                    frag = base + ext
                                    if os.path.exists(frag):
                                        try:
                                            os.remove(frag)
                                            self.logger.info(f"불완전 파일 삭제: {frag}")
                                        except Exception as e:
                                            self.logger.warning(f"파일 삭제 실패 {frag}: {e}")

                            self.save_json_data(json_data)

                        except Exception as e:
                            self.logger.error(f"다운로드 중 예외 발생 {vid}: {e}")
                            entry['completed'] = False
                            self.save_json_data(json_data)

                except Exception as e:
                    self.logger.error(f"메타데이터 추출 오류 {video_url}: {e}")
    
    def get_download_status(self):
        """
        다운로드 상태 요약을 반환합니다.
        
        Returns:
            dict: 전체/완료/미완료 동영상 수 포함.
        """
        json_data = self.load_json_data()
        videos = json_data.get('videos', {})
        completed = sum(1 for v in videos.values() if v.get('completed'))
        return {
            'total': len(videos),
            'completed': completed,
            'pending': len(videos) - completed
        }




# 실행 예제
if __name__ == "__main__":
    # 기본 설정으로 다운로더 생성 (data 폴더 사용)
    downloader = YouTubeDownloader()
    
    # 또는 커스텀 설정으로 생성
    # downloader = YouTubeDownloader(
    #     data_dir='/path/to/downloads',
    #     config_file='custom_config.json',
    #     format_preference='720p',  # '1080p', '720p', 'best'
    #     download_subtitles=True,
    #     extract_audio=True,
    #     audio_format='mp3'
    # )
    
    # 다운로드할 URL 리스트
    youtube_video_list = [
        'https://www.youtube.com/watch?v=wVahylWPK18&list=PLLoamEZ5bJuFsqzWgrPOAAUA2XnAoXqyK'
    ]
    
    # 다운로드 실행
    downloader.download_video_and_subtitle(youtube_video_list)
    
    # 다운로드 상태 확인
    status = downloader.get_download_status()
    print(f"\n다운로드 상태: 전체 {status['total']}개, 완료 {status['completed']}개, 대기 {status['pending']}개")
