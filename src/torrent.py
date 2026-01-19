import os
import re
import json
import logging
import datetime
import subprocess
import sys
import shutil
import time
import requests

# tqdm 프로그래스바 자동 설치
try:
    from tqdm import tqdm
except ImportError:
    print("tqdm을 설치하고 있습니다...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "tqdm"])
    from tqdm import tqdm

# libtorrent 자동 설치 및 DLL 오류 처리
lt = None
libtorrent_installed = False

def _try_import_libtorrent():
    """libtorrent 임포트 시도"""
    global lt
    try:
        import libtorrent as lt
        return True
    except ImportError:
        return False
    except Exception as e:
        error_msg = str(e)
        if "DLL load failed" in error_msg or "모듈을 찾을 수 없습니다" in error_msg:
            return False
        raise

# 먼저 임포트 시도
if not _try_import_libtorrent():
    # libtorrent가 없거나 DLL 오류인 경우 설치 시도
    print("libtorrent를 설치하고 있습니다...")
    
    # 시도할 패키지 목록 (우선순위 순)
    packages_to_try = [
        "libtorrent-windows-dll",  # OpenSSL DLL 포함 버전
        "python-libtorrent-bin",   # 대안 바이너리 패키지
        "libtorrent",              # 기본 패키지
    ]
    
    for package in packages_to_try:
        try:
            print(f"  {package} 설치 시도 중...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if _try_import_libtorrent():
                print(f"  ✓ {package} 설치 및 임포트 성공!")
                libtorrent_installed = True
                break
            else:
                print(f"  ✗ {package} 설치 후에도 DLL 로드 실패")
                # 설치된 패키지 제거 후 다음 시도
                try:
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "uninstall", "-y", "-q", package],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except:
                    pass
        except subprocess.CalledProcessError:
            print(f"  ✗ {package} 설치 실패")
            continue
        except Exception as e:
            print(f"  ✗ {package} 설치 중 오류: {e}")
            continue
    
    # 모든 시도 실패 시
    if not libtorrent_installed:
        print("\n" + "=" * 70)
        print("오류: libtorrent를 설치하거나 로드할 수 없습니다.")
        print("\n해결 방법:")
        print("1. Visual C++ Redistributable 설치 (필수):")
        print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("\n2. 수동으로 다음 중 하나 설치 시도:")
        print("   pip install libtorrent-windows-dll")
        print("   또는")
        print("   pip install python-libtorrent-bin")
        print("\n3. Python 버전 확인 (3.10 또는 3.11 권장):")
        print(f"   현재 버전: {sys.version}")
        print("=" * 70)
        raise ImportError(
            "libtorrent를 로드할 수 없습니다. "
            "Visual C++ Redistributable을 설치하거나 "
            "libtorrent-windows-dll 패키지를 시도해보세요."
        )


class TorrentDownloader:
    """
    토렌트 다운로더 클래스.

    libtorrent를 이용하여 토렌트 파일을 다운로드하고,
    메타데이터를 JSON으로 관리하며, 다운로드 상태를 추적합니다.
    """

    DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    DEFAULT_CONFIG_FILE = "torrent_config.json"

    def __init__(
        self, data_dir=None, config_file=None, temp_dir=None, complete_dir=None
    ):
        """
        토렌트 다운로더 초기화.

        Args:
            data_dir (str, optional): 다운로드 파일 및 로그 저장 디렉토리.
                                      미지정시 './data'
            config_file (str, optional): 메타데이터 JSON 파일명.
                                         미지정시 'torrent_config.json'
            temp_dir (str, optional): 임시 다운로드 디렉토리.
            complete_dir (str, optional): 완료 파일 이동 디렉토리.
        """
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self.config_filename = config_file or self.DEFAULT_CONFIG_FILE
        self.json_file_path = os.path.join(self.data_dir, self.config_filename)
        self.log_file_path = os.path.join(self.data_dir, "download.log")

        self.temp_path = temp_dir or os.path.join(self.data_dir, "temp")
        self.complete_path = complete_dir or os.path.join(self.data_dir, "complete")

        # 디렉토리 생성
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        os.makedirs(self.complete_path, exist_ok=True)

        # 로거 설정
        self.logger = self._setup_logger()

        # 세션 초기화
        self._init_session()

        self.RE_BLACKLIST = [
            (
                lambda download: [
                    x.path
                    for x in download.torrent_info().files()
                    if download.torrent_info()
                ],
                re.compile(
                    "2048\.info|\.apk|APP|4k2\.com|iQQTV|kcf9\.com|三国志|tanhuazu\.com|d66e\.com"
                ),
                1,
            ),
            (
                lambda download: [download.status().name if download.status().name else "Unknown"],
                re.compile("\.info|APP|【|\.xyz|^HD_"),
                0,
            ),
        ]

    def _setup_logger(self):
        logger = logging.getLogger(f"TorrentDownloader_{id(self)}")
        logger.handlers = []
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _init_session(self):
        # 세션 생성
        self.ses = lt.session()
        self.ses.listen_on(6881, 6891)
        
        # settings 딕셔너리 가져오기 및 DHT 부트스트랩 노드 추가
        settings = self._get_session_settings()
        settings["dht_bootstrap_nodes"] = (
            "router.utorrent.com:6881,router.bittorrent.com:6881,"
            "dht.transmissionbt.com:6881,dht.aelitis.com:6881"
        )
        
        # 설정 적용
        self.ses.apply_settings(settings)

        self.KST = datetime.timezone(datetime.timedelta(hours=9))
        self.regex = re.compile("urn:btih:(?P<hash>[a-zA-Z0-9]*)")
        self.re_hash = re.compile("^[0-9a-fA-F]{40}$")
        self.added_hashs = []
        self.downloads = []
        self.progress_bars = {}  # 각 다운로드의 tqdm 인스턴스 저장

        self.setting = self.load_setting()
        self.bsetting = ""
        self.bsetting = self.save_setting(self.setting, self.bsetting)

        self.params = {
            "save_path": self.temp_path,
            "storage_mode": lt.storage_mode_t(2),
        }

        self.trackers = self._get_trackers()

    def _get_session_settings(self):
        return {
            "allow_multiple_connections_per_ip": True,
            "dont_count_slow_torrents": True,
            "active_downloads": 100,
            "active_seeds": 0,
            "active_checking": -1,
            "active_limit": -1,
            "upload_rate_limit": 0,
            "download_rate_limit": 0,
            "checking_mem_usage": 1024,
            "share_mode_target": 0,
            "seed_time_limit": 0,
            "seed_time_ratio_limit": 0,
            "auto_manage_startup": 30,
            "seeding_piece_quota": 0,
        }

    def _get_trackers(self):
        track_urls = [
            "https://cf.trackerslist.com/best.txt",
            "http://ngosang.github.io/trackerslist/trackers_best.txt",
        ]
        trackrs = []
        for track_url in track_urls:
            try:
                txt_tracker = requests.get(track_url, timeout=10)
                txt_tracker.encoding = txt_tracker.apparent_encoding
                [trackrs.append("&tr=" + x) for x in txt_tracker.text.split("\n") if x]
            except Exception as e:
                self.logger.warning(f"트래커 목록 가져오기 실패 {track_url}: {e}")
        return "".join(trackrs)

    def add_blacklist(self, remove_list: str):
        remove_pattern = f"""(?i)(?:{
            "|".join(
                [
                    x.strip()
                    for x in remove_list.splitlines()
                    if x.strip() and not x.strip().startswith("#")
                ]
            )
        })"""
        self.RE_BLACKLIST.append(
            (lambda download: [download.status().name if download.status().name else "Unknown"], re.compile(remove_pattern), 1)
        )

    def load_json_data(self):
        if os.path.exists(self.json_file_path):
            try:
                with open(self.json_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("JSON 파일 손상 감지, 새로 생성")
                return {"files": []}
        return {"files": []}

    def save_json_data(self, data):
        with open(self.json_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def add_magnets(self, magnet_links):
        re_mag = re.compile("^magnet:\?xt=urn:btih:([^&]+)")
        set_files = [x["hash"].upper() for x in self.setting["files"]]
        for mg in magnet_links.split("\n"):
            magnet_link = mg.strip()
            search = re_mag.search(magnet_link)
            if magnet_link and search and search.group(1).upper() not in set_files:
                try:
                    mg_data = lt.parse_magnet_uri(magnet_link)
                    t_info = {
                        "hash": str(mg_data.info_hash).upper(),
                        "magnet_uri": magnet_link,
                        "added_time": str(
                            datetime.datetime.fromtimestamp(time.time(), self.KST)
                        ),
                        "is_complate": False,
                        "is_failed": False,
                        "size": 0,
                        "name": mg_data.name if hasattr(mg_data, "name") else "Unknown",
                    }
                    self.add_file(self.setting, t_info)
                except Exception as e:
                    self.logger.error(f"마그넷 링크 추가 실패 {magnet_link}: {e}")
        self.save_setting(self.setting, self.bsetting)

    def download_torrents(self):
        self.logger.info("토렌트 다운로드 시작...")
        self.add_download(self.downloads, self.params)
        self.run()

    def add_download(self, downloads, params, maxcount=40, maxsizeGiga=80):
        fullsize = 0
        torrents = self.ses.get_torrents()
        for file in sorted(
            self.setting["files"], key=lambda f: f["added_time"], reverse=True
        ):
            hash = file["hash"]
            if hash not in self.added_hashs and (
                not file["is_complate"]
                and len(downloads) <= maxcount
                and fullsize < maxsizeGiga * 1024 * 1024 * 1024
            ):
                try:
                    if self.re_hash.match(hash):
                        if file.get("size"):
                            fullsize += file["size"]
                        file["blacklist"] = None
                        # 최신 API: parse_magnet_uri와 add_torrent_params 사용
                        magnet_uri = file["magnet_uri"] + self.trackers
                        atp = lt.parse_magnet_uri(magnet_uri)
                        atp.save_path = params["save_path"]
                        atp.storage_mode = params["storage_mode"]
                        handle = self.ses.add_torrent(atp)
                        downloads.append(handle)
                        self.added_hashs.append(hash)
                        self.logger.info(f"토렌트 추가됨: {file.get('name', hash)}")
                    else:
                        file["is_complate"] = True
                        file["is_failed"] = True
                        self.logger.error(f"잘못된 해시: {hash}")
                        self.added_hashs.append(hash)
                except Exception as e:
                    self.logger.error(f"다운로드 추가 실패 {hash}: {e}")

    def run(self):
        while self.downloads:
            for i in range(len(self.downloads) - 1, -1, -1):
                download = self.downloads[i]
                try:
                    hash = str(download.info_hash()).lower()
                    tstatus = download.status()
                    # 최신 API: status().name 사용
                    name = tstatus.name if tstatus.name else "Unknown"
                    file = self.get_file(self.setting, hash)
                    if not file:
                        continue
                    file = file[0]

                    if not file.get("blacklist"):
                        try:
                            is_black = False
                            for exe, re_com, is_file in self.RE_BLACKLIST:
                                # 최신 API: torrent_info() 사용
                                try:
                                    ti = download.torrent_info()
                                    if is_file == 1 and (not ti or len(ti.files()) == 0):
                                        continue
                                except:
                                    continue
                                exe_list = exe(download)
                                for exe_item in exe_list:
                                    if re_com.search(exe_item):
                                        is_black = True
                                        self.logger.warning(
                                            f"블랙리스트 감지: {exe_item}"
                                        )
                                        break
                                if is_black:
                                    file["is_failed"] = True
                                    break
                            file["blacklist"] = is_black
                        except Exception as exc:
                            self.logger.warning(f"블랙리스트 확인 실패: {exc}")

                    if (tstatus.state in [tstatus.state.downloading_metadata]) and (
                        datetime.datetime.now()
                        - datetime.datetime.fromtimestamp(tstatus.added_time)
                    ).total_seconds() > 60 * 60:
                        file["blacklist"] = True
                        self.logger.warning(f"메타데이터 타임아웃: {name}")

                    # 최신 API: status().is_seeding 사용
                    if not tstatus.is_seeding and not file.get("blacklist"):
                        if not file.get("size"):
                            file["size"] = tstatus.total_wanted
                        if not file.get("name"):
                            file["name"] = name

                        # tqdm 프로그래스바 업데이트
                        total_bytes = tstatus.total_wanted
                        # total_bytes가 0이면 메타데이터 다운로드 중이므로 임시로 큰 값 사용
                        if total_bytes == 0:
                            total_bytes = 1  # 0으로 나누기 방지
                        
                        downloaded_bytes = int(total_bytes * tstatus.progress)
                        speed_bytes = tstatus.download_rate
                        state = self._get_state_string(tstatus.state)
                        
                        display_name = file.get('name', 'Unknown')
                        if len(display_name) > 50:
                            display_name = display_name[:47] + "..."
                        
                        # 프로그래스바가 없으면 생성
                        if hash not in self.progress_bars:
                            # 메타데이터 다운로드 중이면 total을 None으로 설정 (무한 프로그래스바)
                            pbar_total = None if tstatus.total_wanted == 0 else total_bytes
                            self.progress_bars[hash] = tqdm(
                                total=pbar_total,
                                unit='B',
                                unit_scale=True,
                                unit_divisor=1024,
                                desc=display_name,
                                leave=False,  # 완료 후 자동으로 사라지도록
                                ncols=100,
                                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}',
                                dynamic_ncols=True
                            )
                        
                        # 프로그래스바 업데이트
                        pbar = self.progress_bars[hash]
                        
                        # 프로그래스바가 이미 닫혔으면 딕셔너리에서 제거하고 건너뛰기
                        try:
                            # total이 변경되었으면 업데이트
                            if tstatus.total_wanted > 0 and pbar.total != tstatus.total_wanted:
                                pbar.total = tstatus.total_wanted
                            
                            # 다운로드된 바이트 수 업데이트
                            if tstatus.total_wanted > 0:
                                pbar.n = downloaded_bytes
                            else:
                                # 메타데이터 다운로드 중일 때는 진행률만 표시
                                pbar.update(0)  # 진행률만 업데이트
                            
                            pbar.set_postfix_str(f"{state} | {speed_bytes/1024:.1f} kB/s")
                            pbar.refresh()
                        except (AttributeError, ValueError):
                            # 프로그래스바가 이미 닫혔거나 손상된 경우 제거
                            if hash in self.progress_bars:
                                del self.progress_bars[hash]
                            continue
                    else:
                        # 다운로드 완료 또는 실패 시 프로그래스바 닫기
                        if hash in self.progress_bars:
                            try:
                                pbar = self.progress_bars[hash]
                                # 최신 API: status().is_seeding 사용
                                if tstatus.is_seeding and pbar.total:
                                    pbar.n = pbar.total  # 100%로 설정
                                    pbar.set_postfix_str("완료")
                                else:
                                    pbar.set_postfix_str("실패")
                                pbar.close()
                            except:
                                pass  # 이미 닫힌 프로그래스바는 무시
                            finally:
                                del self.progress_bars[hash]
                        
                        save_path = os.path.join(self.temp_path, name)
                        target_path = os.path.join(self.complete_path, name)
                        try:
                            file["is_complate"] = True
                            if file.get("blacklist", False):
                                self.logger.error(f"블랙리스트로 인한 실패: {file}")
                            else:
                                self.move(save_path, target_path)
                                self.logger.info(f"다운로드 완료: {file}")
                            file["modfy_time"] = str(
                                datetime.datetime.fromtimestamp(time.time(), self.KST)
                            )
                        except Exception as ex:
                            self.logger.error(f"완료 처리 실패: {ex}")
                        self.ses.remove_torrent(download)
                        self.downloads.remove(download)

                        self.add_download(self.downloads, self.params)

                    if str(file) != str(
                        self.get_file(self.setting, hash)[0]
                        if self.get_file(self.setting, hash)
                        else {}
                    ):
                        self.bsetting = self.save_setting(self.setting, self.bsetting)

                except Exception as e:
                    self.logger.error(f"런 루프 오류: {e}")
                    # 오류 발생 시 프로그래스바 정리
                    if hash in self.progress_bars:
                        try:
                            self.progress_bars[hash].close()
                        except:
                            pass
                        del self.progress_bars[hash]
                    if download in self.downloads:
                        self.downloads.remove(download)
            
            time.sleep(1)  # 1초마다 업데이트

    def _get_state_string(self, state):
        state_strings = [
            "queued",
            "checking",
            "downloading metadata",
            "downloading",
            "finished",
            "seeding",
            "allocating",
            "checking fastresume",
        ]
        return state_strings[state] if state < len(state_strings) else "unknown"

    def load_setting(self):
        setting = dict()
        if os.path.exists(self.json_file_path):
            with open(self.json_file_path, "r") as f:
                setting = json.loads(f.read())
        if not setting.get("files"):
            setting["files"] = list()
        return setting

    def save_setting(self, setting, bsetting):
        dsetting = json.dumps(setting)
        if bsetting != dsetting:
            with open(self.json_file_path, "w") as f:
                f.write(json.dumps(setting, indent=4, ensure_ascii=False))
        return dsetting

    def add_file(self, setting, info):
        set_files = [
            x for x in setting["files"] if x["hash"].lower() == info["hash"].lower()
        ]
        if not set_files:
            setting["files"].append(info)

    def get_file(self, setting, download):
        hash = (
            str(download.info_hash()).lower()
            if not isinstance(download, str)
            else download.lower()
        )
        return [x for x in setting["files"] if x["hash"].lower() == hash]

    def move(self, root_src_dir, root_dst_dir):
        try:
            if os.path.exists(root_dst_dir):
                dsplit = list(os.path.split(root_dst_dir))
                dsplit[-1] = "__" + dsplit[-1]
                shutil.move(root_dst_dir, os.path.join(*dsplit))
            shutil.move(root_src_dir, root_dst_dir)
        except Exception as e:
            self.logger.error(f"파일 이동 실패: {e}")

    def get_download_status(self):
        json_data = self.load_json_data()
        files = json_data.get("files", {})
        completed = sum(1 for f in files if f.get("is_complate"))
        return {
            "total": len(files),
            "completed": completed,
            "pending": len(files) - completed,
        }


# 실행 예제
if __name__ == "__main__":
    # 기본 설정으로 다운로더 생성 (data 폴더 사용)
    downloader = TorrentDownloader()

    # 또는 커스텀 설정으로 생성
    # downloader = TorrentDownloader(
    #     data_dir='/path/to/downloads',
    #     config_file='custom_config.json',
    #     temp_dir='/path/to/temp',
    #     complete_dir='/path/to/complete'
    # )

    # 마그넷 링크 추가 (예시)
    magnet_links = """
    magnet:?xt=urn:btih:6c4f9b94e6e1524abb07f3a12dd26d160152e9ac&dn=%EA%BC%AC%EB%A6%AC%EC%97%90%EA%BC%AC%EB%A6%AC%EB%A5%BC%EB%AC%B4%EB%8A%94%EA%B7%B8%EB%82%A0%EC%9D%B4%EC%95%BC%EA%B8%B0.E166.250313.1080p.H264-F1RST.mp4&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce&tr=udp%3A%2F%2Fopen.demonii.com%3A1337%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Fexplodie.org%3A6969%2Fannounce&tr=udp%3A%2F%2Fexodus.desync.com%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.ololosh.space%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker-udp.gbitt.info%3A80%2Fannounce&tr=udp%3A%2F%2Fopentracker.io%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.free-tracker.ga%3A6969%2Fannounce&tr=udp%3A%2F%2Fdiscord.heihachi.pw%3A6969%2Fannounce&tr=http%3A%2F%2Fwww.genesis-sp.org%3A2710%2Fannounce&tr=http%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce&tr=http%3A%2F%2Ftracker.ipv6tracker.org%3A80%2Fannounce&tr=http%3A%2F%2Ftracker.dmcomic.org%3A2710%2Fannounce&tr=http%3A%2F%2Ftracker.corpscorp.online%3A80%2Fannounce&tr=http%3A%2F%2Ftracker.bz%3A80%2Fannounce&tr=http%3A%2F%2Fshubt.net%3A2710%2Fannounce&tr=http%3A%2F%2Fshare.hkg-fansub.info%3A80%2Fannounce.php&tr=http%3A%2F%2Fservandroidkino.ru%3A80%2Fannounce&tr=https%3A%2F%2Ftracker.bt4g.com%3A443%2Fannounce
    """

    # 마그넷 링크 추가
    downloader.add_magnets(magnet_links)

    # 다운로드 실행
    downloader.download_torrents()

    # 다운로드 상태 확인
    status = downloader.get_download_status()
    print(
        f"\n다운로드 상태: 전체 {status['total']}개, 완료 {status['completed']}개, 대기 {status['pending']}개"
    )
