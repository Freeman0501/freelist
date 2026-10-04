#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ofiii.py — ofiii 直播/點播代理（由 ofiii.php 逐行移植的 Python 版）

功能（與 PHP 原版一致）：
  - 訪問 http://yourserver:8080/ofiii.py?token=xxxx            顯示完整 M3U 清單
  - 訪問 http://yourserver:8080/ofiii.py?token=xxxx&id=頻道ID  播放指定頻道的 M3U8 播放地址
  - 支持 ofiii 開頭的點播頻道
  - 訪問 http://yourserver:8080/ofiii.py?token=xxxx&id=頻道ID&program_id=節目ID  點播選集
  - 支持 HTTP/HTTPS/SOCKS 代理
  - 支持切片代理開關
  - 優化性能，減少卡頓（連接池 + 持久連接）
  - 自動清理過期緩存文件

純標準庫，單文件：python3 ofiii.py [--host 0.0.0.0] [--port 8080]
"""

import argparse
import hashlib
import http.client
import json
import os
import random
import re
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ============================
# 配置區域
# ============================
# 調試模式 - 設為 True 以顯示詳細錯誤信息
DEBUG_MODE = False

# 代理配置
ENABLE_PROXY = False  # 是否啟用代理：True/False
PROXY_TYPE = 'http'   # 代理類型：http, https, socks4, socks4a, socks5, socks5h（通常 SSR/Clash 是 socks5）
PROXY_SERVER = ''     # 代理服務器地址和端口，例如 '127.0.0.1:7890'
PROXY_USERNAME = ''   # 代理用戶名（如果需要）
PROXY_PASSWORD = ''   # 代理密碼（如果需要）
# 注意：socks 類型代理需要 PySocks（pip install PySocks）；未安裝時會輸出警告並以直連繼續。

# 切片代理開關 - 當開啟時，所有播放地址會自動加上 proxy=true 效果（切片走 ts_proxy）
ENABLE_SLICE_PROXY = True  # 是否啟用切片代理：True/False

# 性能優化配置
ENABLE_CACHE = True  # 啟用緩存
CACHE_TIME = 60      # 緩存時間（秒）- 用於 HTTP 緩存頭及命中判斷
ENABLE_KEEPALIVE = True  # 啟用 HTTP 持久連接（連接池）
TIMEOUT = 10         # 超時時間（秒）
CONNECT_TIMEOUT = 5  # 連接超時時間（秒）

# ============================
# 緩存自動清理配置
# ============================
ENABLE_CACHE_CLEANUP = True    # 是否啟用自動清理過期緩存文件
CACHE_CLEANUP_MAX_AGE = 120    # 緩存文件最大保留時間（秒）
CACHE_CLEANUP_PROBABILITY = 0.02  # 每次請求觸發清理的概率（2%），避免每次都掃描目錄影響性能
CACHE_CLEANUP_LOCK_TTL = 60    # 清理鎖有效期（秒），防止並發重複清理

# API 配置
BASE_URL = 'https://cdi.ofiii.com/ofiii_cdi/video/urls'
SECRET_TOKEN = 'all'  # 替換為你的實際 token

# 基礎 URL 覆寫：留空則按請求頭自動推導（支持反代 X-Forwarded-Proto/Host）；
# 若反代掛在子路徑或推導不準，可在此寫死，例如 'https://example.com/tv'
BASE_URL_OVERRIDE = ''

# 腳本名（用於生成 M3U 內的頻道 URL，與 PHP 版 ?token=…&id=… 形式保持一致）
SCRIPT_NAME = os.path.basename(__file__)

# 緩存目錄（PHP 版 __DIR__ . '/cache/'）
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')

# 默認構建 ID（取不到時使用，與 PHP 版一致）
DEFAULT_BUILD_ID = "3ssBYSd7X7F1D9hQbCOoi"

# 上游請求頭（瀏覽器 UA，與 PHP 版一致）
BROWSER_HEADERS = [
    ('accept', 'application/json, text/plain, */*'),
    ('accept-language', 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'),
    ('cache-control', 'no-cache'),
    ('content-type', 'text/plain'),
    ('origin', 'https://www.ofiii.com'),
    ('pragma', 'no-cache'),
    ('priority', 'u=1, i'),
    ('referer', 'https://www.ofiii.com/'),
    ('sec-ch-ua', '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
    ('sec-ch-ua-mobile', '?0'),
    ('sec-ch-ua-platform', '"macOS"'),
    ('sec-fetch-dest', 'empty'),
    ('sec-fetch-mode', 'cors'),
    ('sec-fetch-site', 'same-site'),
    ('user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'),
]

TS_HEADERS = [
    ('accept', '*/*'),
    ('accept-language', 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6'),
    ('cache-control', 'no-cache'),
    ('pragma', 'no-cache'),
    ('user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'),
    ('accept-encoding', 'identity'),  # 不要使用 gzip，否則 TS 檔案會損壞
]

EPG_URL = "https://raw.githubusercontent.com/myhomebox/EPG/refs/heads/main/output/ofiii.xml"


# ============================
# 頻道映射表
# ============================
# 格式: '頻道ID': ('頻道名稱', '台標URL', '分組名稱')
CHANNELS = {
    '4gtv-4gtv009': ('中天新聞台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/CTI2.png', '新聞財經'),
    '4gtv-4gtv040': ('中視', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/CTV.png', '綜合其他'),
    '4gtv-4gtv041': ('華視', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/CTS.png', '綜合其他'),
    '4gtv-4gtv052': ('華視新聞', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/CTS1.png', '新聞財經'),
    '4gtv-4gtv074': ('中視新聞', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/CTV1.png', '新聞財經'),
    '4gtv-4gtv076': ('亞洲旅遊台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/Asiatravel.png', '生活旅遊'),
    '4gtv-4gtv084': ('國會頻道1台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/guohui1.png', '綜合其他'),
    '4gtv-4gtv085': ('國會頻道2台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/guohui2.png', '綜合其他'),
    '4gtv-4gtv102': ('東森購物1台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/EBC11.png', '綜合其他'),
    '4gtv-4gtv103': ('東森購物2台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/EBC11.png', '綜合其他'),
    '4gtv-4gtv104': ('第1商業台', 'https://p-cdnstatic.svc.litv.tv/pics/logo_litv_4gtv-4gtv104_tv.png', '新聞財經'),
    '4gtv-4gtv156': ('寰宇新聞台灣台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/Global3.png', '新聞財經'),
    '4gtv-4gtv158': ('寰宇財經台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/Global4.png', '新聞財經'),
    'litv-xinchuang01': ('龍華卡通台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV9.png', '兒童卡通'),
    'litv-xinchuang02': ('龍華洋片台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV2.png', '電影戲劇'),
    'litv-xinchuang03': ('龍華電影台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV1.png', '電影戲劇'),
    'litv-xinchuang11': ('龍華日韓台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV5.png', '電影戲劇'),
    'litv-longturn14': ('寰宇新聞台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/Global2.png', '新聞財經'),
    'litv-xinchuang12': ('龍華偶像台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV6.png', '電影戲劇'),
    'litv-xinchuang18': ('龍華戲劇台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV4.png', '電影戲劇'),
    'litv-xinchuang19': ('SMART知識台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/smarttv.png', '生活旅遊'),
    'litv-xinchuang20': ('ELTV生活英語台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/ELTA7.png', '兒童卡通'),
    'litv-xinchuang21': ('龍華經典台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/LTV7.png', '電影戲劇'),
    'litv-xinchuang22': ('台灣戲劇台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/Taiwanxiju.png', '電影戲劇'),
    'litv-ftv16': ('好消息', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/GoodTV1.png', '綜合其他'),
    'litv-ftv17': ('好消息2台', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/GoodTV2.png', '綜合其他'),
    'iNEWS': ('三立新聞iNEWS', 'https://cdn.jsdelivr.net/gh/wanglindl/TVlogo@main/img/SET3.png', '新聞財經'),
}


# ============================
# 內部工具
# ============================
def _dbg(*args):
    if DEBUG_MODE:
        print('[ofiii]', *args, file=sys.stderr, flush=True)


def _unverified_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_SSL_CTX = _unverified_ssl_context()


# ---------- 持久連接池（直連模式，對應 PHP 的 keepalive） ----------
_pool = {}
_pool_lock = threading.Lock()


def _pool_get(key):
    with _pool_lock:
        conns = _pool.get(key)
        if conns:
            return conns.pop()
    return None


def _pool_put(key, conn):
    if not ENABLE_KEEPALIVE:
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        if conn.sock is None:
            return
        with _pool_lock:
            _pool.setdefault(key, []).append(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def _new_direct_conn(scheme, host, port):
    if scheme == 'https':
        conn = http.client.HTTPSConnection(host, port, timeout=CONNECT_TIMEOUT, context=_SSL_CTX)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=CONNECT_TIMEOUT)
    conn.connect()
    try:
        conn.sock.settimeout(TIMEOUT)
    except Exception:
        pass
    return conn


def _fetch_direct_raw(url, headers, max_redirects=5):
    """直連取數據（支持 301/302/303/307/308 跟隨），返回 (status, resp_headers_dict, body)。"""
    cur = url
    for _ in range(max_redirects + 1):
        parts = urllib.parse.urlsplit(cur)
        scheme = parts.scheme or 'http'
        host = parts.hostname
        port = parts.port or (443 if scheme == 'https' else 80)
        if not host:
            return None
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        key = (scheme, host, port)
        conn = _pool_get(key)
        if conn is None:
            try:
                conn = _new_direct_conn(scheme, host, port)
            except Exception as e:
                _dbg('connect failed:', cur, e)
                return None
        req_headers = dict(headers)
        req_headers.setdefault('Host', host)
        req_headers.setdefault('Connection', 'keep-alive')
        try:
            conn.request('GET', path, headers=req_headers)
            resp = conn.getresponse()
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read()
        except Exception as e:
            _dbg('request failed, retry fresh conn:', cur, e)
            try:
                conn.close()
            except Exception:
                pass
            try:
                conn = _new_direct_conn(scheme, host, port)
                conn.request('GET', path, headers=req_headers)
                resp = conn.getresponse()
                status = resp.status
                resp_headers = {k.lower(): v for k, v in resp.getheaders()}
                body = resp.read()
            except Exception as e2:
                _dbg('retry failed:', cur, e2)
                return None
        _pool_put(key, conn)
        if status in (301, 302, 303, 307, 308) and 'location' in resp_headers:
            cur = urllib.parse.urljoin(cur, resp_headers['location'])
            continue
        return status, resp_headers, body
    return None


# ---------- 代理模式（urllib） ----------
def _proxy_cfg():
    """解析代理配置，返回 dict；未啟用返回 None。"""
    if not (ENABLE_PROXY and PROXY_SERVER):
        return None
    clean = re.sub(r'^(http|https|socks4|socks5)://', '', PROXY_SERVER, flags=re.I)
    if ':' in clean:
        addr, port_s = clean.rsplit(':', 1)
        try:
            port = int(port_s)
        except ValueError:
            addr, port = clean, 8080
    else:
        addr, port = clean, 8080
    return {
        'type': PROXY_TYPE.lower(),
        'addr': addr,
        'port': port,
        'user': PROXY_USERNAME or None,
        'pass': PROXY_PASSWORD or None,
    }


def _build_proxy_opener(cfg):
    ptype = cfg['type']
    if ptype in ('http', 'https'):
        scheme = 'http' if ptype == 'http' else 'https'
        proxy_url = '%s://%s:%d' % (scheme, cfg['addr'], cfg['port'])
        if cfg['user']:
            proxy_url = '%s://%s:%s@%s:%d' % (
                scheme, urllib.parse.quote(cfg['user']),
                urllib.parse.quote(cfg['pass'] or ''), cfg['addr'], cfg['port'])
        handlers = [urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})]
    elif ptype in ('socks4', 'socks4a', 'socks5', 'socks5h'):
        try:
            import socks as _socks_mod  # PySocks
        except ImportError:
            print('[ofiii] 警告：已配置 socks 代理但未安裝 PySocks（pip install PySocks），'
                  '本次請求將以直連繼續。', file=sys.stderr, flush=True)
            return None
        type_map = {
            'socks4': (_socks_mod.SOCKS4, False),
            'socks4a': (_socks_mod.SOCKS4, True),
            'socks5': (_socks_mod.SOCKS5, False),
            'socks5h': (_socks_mod.SOCKS5, True),
        }
        stype, rdns = type_map[ptype]
        sp = {'stype': stype, 'addr': cfg['addr'], 'port': cfg['port'],
              'rdns': rdns, 'user': cfg['user'], 'pass': cfg['pass']}

        class SocksHTTPConnection(http.client.HTTPConnection):
            def connect(self):
                s = _socks_mod.socksocket()
                s.set_proxy(sp['stype'], sp['addr'], sp['port'], rdns=sp['rdns'],
                            username=sp['user'], password=sp['pass'])
                s.settimeout(self.timeout)
                s.connect((self.host, self.port))
                self.sock = s

        class SocksHTTPSConnection(http.client.HTTPSConnection):
            def connect(self):
                s = _socks_mod.socksocket()
                s.set_proxy(sp['stype'], sp['addr'], sp['port'], rdns=sp['rdns'],
                            username=sp['user'], password=sp['pass'])
                s.settimeout(self.timeout)
                s.connect((self.host, self.port))
                self.sock = self._context.wrap_socket(s, server_hostname=self.host)
            # 與 PHP 一致：不驗證上游證書
            _context = _SSL_CTX

        class SocksHTTPHandler(urllib.request.HTTPHandler):
            def http_open(self, req):
                return self.do_open(SocksHTTPConnection, req)

        class SocksHTTPSHandler(urllib.request.HTTPSHandler):
            def https_open(self, req):
                return self.do_open(SocksHTTPSConnection, req)

        handlers = [urllib.request.ProxyHandler({}), SocksHTTPHandler(), SocksHTTPSHandler()]
    else:
        proxy_url = 'http://%s:%d' % (cfg['addr'], cfg['port'])
        handlers = [urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})]
    return urllib.request.build_opener(*handlers)


def _fetch_proxy_raw(url, headers):
    cfg = _proxy_cfg()
    opener = _build_proxy_opener(cfg) if cfg else None
    if opener is None:
        # socks 缺 PySocks 等情況：退回直連
        return _fetch_direct_raw(url, headers)
    req = urllib.request.Request(url, headers=dict(headers), method='GET')
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            status = resp.status
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            body = resp.read()
        return status, resp_headers, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b''
        return e.code, {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}, body
    except Exception as e:
        _dbg('proxy fetch failed:', url, e)
        return None


def fetch_raw(url, headers):
    """取原始響應，返回 (status, headers_dict, body)；失敗返回 None。"""
    if _proxy_cfg():
        return _fetch_proxy_raw(url, headers)
    return _fetch_direct_raw(url, headers)


def fetch_url(url, headers=None):
    """對應 PHP fetchUrl：僅 200 返回 body，否則返回 None。"""
    r = fetch_raw(url, headers or [])
    if r is None:
        return None
    status, _, body = r
    return body if status == 200 else None


# ============================
# 緩存自動清理（與 PHP 版一致）
# ============================
def cleanup_expired_cache():
    if not ENABLE_CACHE_CLEANUP:
        return
    # 概率觸發，避免每次請求都掃描目錄影響性能
    if random.randint(1, 10000) > int(CACHE_CLEANUP_PROBABILITY * 10000):
        return
    if not os.path.isdir(CACHE_DIR):
        return
    # 使用鎖文件防止並發請求同時執行清理
    lock_file = os.path.join(CACHE_DIR, '.cleanup.lock')
    try:
        if os.path.exists(lock_file) and (time.time() - os.path.getmtime(lock_file) < CACHE_CLEANUP_LOCK_TTL):
            return  # 有其他請求正在清理或剛清理過，跳過
        with open(lock_file, 'w') as f:
            f.write(str(int(time.time())))
    except OSError:
        return
    now = time.time()
    try:
        files = os.listdir(CACHE_DIR)
    except OSError:
        return
    for name in files:
        # 只清理 .ts 緩存切片，puid_cache.json 及鎖文件不受影響
        if not name.endswith('.ts'):
            continue
        full = os.path.join(CACHE_DIR, name)
        try:
            if not os.path.isfile(full):
                continue
            if (now - os.path.getmtime(full)) > CACHE_CLEANUP_MAX_AGE:
                os.unlink(full)
        except OSError:
            continue


# ============================
# 基礎 URL 推導（對應 PHP getBaseUrl）
# ============================
def get_base_url(handler):
    if BASE_URL_OVERRIDE:
        return BASE_URL_OVERRIDE.rstrip('/')
    h = handler.headers
    https = False
    # 優先信任反代傳來的標頭
    fwd_proto = h.get('X-Forwarded-Proto', '')
    if fwd_proto:
        https = fwd_proto.split(',')[0].strip().lower() == 'https'
    elif h.get('X-Forwarded-Ssl', '').lower() == 'on':
        https = True
    elif h.get('Front-End-Https', '').lower() not in ('', 'off'):
        https = True
    protocol = 'https' if https else 'http'
    # 優先使用反代傳來的原始 Host（含端口）
    host = h.get('X-Forwarded-Host') or h.get('Host') or 'localhost:8080'
    return '%s://%s' % (protocol, host)


# ============================
# 設備 ID / PUID
# ============================
def generate_random_device_id():
    # 對應 PHP 的 sprintf('%04x%04x-%04x-%04x-%04x-%04x%04x%04x', ...) UUIDv4 形式
    return '%04x%04x-%04x-%04x-%04x-%04x%04x%04x' % (
        random.randint(0, 0xffff), random.randint(0, 0xffff),
        random.randint(0, 0xffff),
        random.randint(0, 0x0fff) | 0x4000,
        random.randint(0, 0x3fff) | 0x8000,
        random.randint(0, 0xffff), random.randint(0, 0xffff), random.randint(0, 0xffff),
    )


def get_cached_puid():
    cache_file = os.path.join(CACHE_DIR, 'puid_cache.json')
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except OSError:
        pass
    cached = None
    if ENABLE_CACHE and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
        except (OSError, ValueError):
            cached = None
    # 如果緩存有效（未過期），直接返回
    if isinstance(cached, dict) and cached.get('expiry') and time.time() < cached['expiry']:
        return cached['puid']
    # 否則生成新的 puid 並寫入緩存
    new_puid = generate_random_device_id()
    if ENABLE_CACHE:
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({'puid': new_puid, 'expiry': time.time() + 3600}, f)
        except OSError:
            pass
    return new_puid


# ============================
# 節目匹配（對應 PHP getProgramAssetId）
# ============================
def get_program_asset_id(programs, program_id_param):
    # 如果 URL 中有明確指定節目 ID，直接使用
    if program_id_param:
        for program in programs:
            if program.get('asset_id') == program_id_param:
                return program['asset_id']
    # 否則根據目前時間選擇節目
    current_time = int(time.time() * 1000)  # 轉換為毫秒
    for program in programs:
        start_time = program.get('p_start') or 0
        end_time = program.get('p_end')
        if end_time is None:
            end_time = 2 ** 63 - 1  # 對應 PHP_INT_MAX
        if start_time <= current_time <= end_time:
            return program.get('asset_id', '')
    # 如果沒有匹配的節目，返回第一個
    return (programs[0].get('asset_id', '') if programs else '')


# ============================
# 構建 ID（對應 PHP getBuildId）
# ============================
def get_build_id():
    url = "https://www.ofiii.com/channel/watch/litv-xinchuang22"
    headers = [
        ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'),
        ('Referer', 'https://www.ofiii.com/'),
        ('Origin', 'https://www.ofiii.com'),
    ]
    content = fetch_url(url, headers)
    if not content:
        return DEFAULT_BUILD_ID
    try:
        text = content.decode('utf-8', errors='replace')
    except Exception:
        return DEFAULT_BUILD_ID
    # 從 script 標籤中提取構建 ID
    m = re.search(r'_next/static/([^/]+)/_buildManifest\.js', text)
    if m:
        return m.group(1)
    # 從 JSON 數據中提取
    m = re.search(r'"buildId":"([^"]+)"', text)
    if m:
        return m.group(1)
    return DEFAULT_BUILD_ID


# ============================
# M3U8 處理（對應 PHP processM3u8）
# ============================
def process_m3u8(m3u8_url, headers, query, base_url):
    master_content = fetch_url(m3u8_url, headers)
    if not master_content:
        return None
    master_text = master_content.decode('utf-8', errors='replace')

    matches = re.findall(r'#EXT-X-STREAM-INF:.*?BANDWIDTH=(\d+).*?\n(.+?\.m3u8)',
                         master_text, re.S)
    if not matches:
        return None

    selected = matches[0]
    for m in matches:
        if int(m[0]) > int(selected[0]):
            selected = m

    playlist_url = selected[1].strip()
    if not playlist_url.startswith('http'):
        base = m3u8_url[:m3u8_url.rfind('/') + 1]
        playlist_url = base + playlist_url

    playlist_content = fetch_url(playlist_url, headers)
    if not playlist_content:
        return None
    playlist_text = playlist_content.decode('utf-8', errors='replace')

    # 檢查是否需要啟用切片代理
    enable_slice = False
    if query.get('proxy') == 'true':
        enable_slice = True
    if ENABLE_SLICE_PROXY:
        enable_slice = True

    if enable_slice:
        def _rewrite(m):
            ts_url = m.group(1)
            # 如果是相對路徑，需要轉換為絕對 URL
            if not ts_url.startswith('https') and not ts_url.startswith('//'):
                base = playlist_url[:playlist_url.rfind('/') + 1]
                ts_url = base + ts_url
            # 構建代理 URL
            return '%s/%s?token=%s&ts_proxy=%s' % (
                base_url, SCRIPT_NAME,
                urllib.parse.quote(SECRET_TOKEN),
                urllib.parse.quote(ts_url, safe=''),
            )
        return re.sub(r'([^\s]+\.ts[^\s]*)', _rewrite, playlist_text)

    return playlist_text


# ============================
# HTTP 請求處理
# ============================
def _parse_query(handler):
    qs = urllib.parse.urlsplit(handler.path).query
    out = {}
    for k, v in urllib.parse.parse_qsl(qs, keep_blank_values=True):
        if k not in out:
            out[k] = v
    return out


class OfiiiHandler(BaseHTTPRequestHandler):
    server_version = 'ofiii-py/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('[ofiii] %s - %s\n' % (self.address_string(), fmt % args))
        sys.stderr.flush()

    def _send_text(self, code, text, content_type='text/plain; charset=utf-8', extra=None):
        body = text.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            self._handle()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            _dbg('handler exception:', repr(e))
            try:
                detail = ('\n%r' % e) if DEBUG_MODE else ''
                self._send_text(500, '❌錯誤：內部錯誤' + detail)
            except Exception:
                pass

    def _handle(self):
        query = _parse_query(self)

        # ============================
        # 檢查 token 是否有效（所有訪問都需要 token）
        # ============================
        if 'token' not in query:
            self._send_text(403, '❌錯誤：存取被拒絕')
            return
        if query['token'] != SECRET_TOKEN:
            self._send_text(403, '❌錯誤：密碼錯誤')
            return

        # 每次請求都有機會觸發一次清理檢查（內部已做概率控制與鎖保護）
        cleanup_expired_cache()

        # ============================
        # 處理 TS 代理請求（優先處理）
        # ============================
        if 'ts_proxy' in query:
            self._handle_ts_proxy(query)
            return

        channel_id = query.get('id')
        # 兼容 PHP 頭註釋裡的寫法：?token=xxxx&<頻道ID>&program_id=…
        if not channel_id:
            for k in query:
                if k in CHANNELS:
                    channel_id = k
                    break

        base_url = get_base_url(self)

        # 無參數時返回完整 M3U 頻道清單
        if not channel_id:
            self._serve_m3u_list(base_url)
            return

        # 檢查頻道 ID 是否有效
        if channel_id not in CHANNELS:
            self._send_text(404, '❌錯誤：未找到頻道。')
            return

        # ofiii 開頭 → 點播頻道
        if channel_id.startswith('ofiii'):
            self._handle_vod(channel_id, query, base_url)
            return

        # 直播頻道
        self._handle_live(channel_id, query, base_url)

    # ---------- M3U 清單 ----------
    def _serve_m3u_list(self, base_url):
        lines = ['#EXTM3U x-tvg-url="%s"' % EPG_URL]
        for key, value in CHANNELS.items():
            name, logo, group = value[0], value[1], (value[2] if len(value) > 2 else 'ofiii')
            lines.append('#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s'
                         % (name, name, logo, group, name))
            channel_url = '%s/%s?token=%s&id=%s' % (
                base_url, SCRIPT_NAME,
                urllib.parse.quote(SECRET_TOKEN),
                urllib.parse.quote(key, safe=''),
            )
            # 如果開啟切片代理，添加 proxy=true 參數
            if ENABLE_SLICE_PROXY:
                channel_url += '&proxy=true'
            lines.append(channel_url)
        self._send_text(200, '\n'.join(lines) + '\n')

    # ---------- TS 切片代理 ----------
    def _handle_ts_proxy(self, query):
        ts_url = query['ts_proxy']

        cache_key = hashlib.md5(ts_url.encode('utf-8')).hexdigest()
        cache_file = os.path.join(CACHE_DIR, cache_key + '.ts')

        # 檢查緩存
        if ENABLE_CACHE and os.path.exists(cache_file):
            try:
                if (time.time() - os.path.getmtime(cache_file)) < CACHE_TIME:
                    self._serve_ts_cache(cache_file)
                    return
            except OSError:
                pass

        # 設置適當的 Content-Type
        content_type = 'video/MP2T' if '.ts' in ts_url else 'application/octet-stream'

        # 設置請求頭，模擬瀏覽器訪問
        headers = list(TS_HEADERS)

        # 支持 Range 請求（用於視頻播放）
        range_header = self.headers.get('Range')
        if range_header:
            headers.append(('Range', range_header))

        # 建立緩存目錄
        if ENABLE_CACHE:
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
            except OSError:
                pass

        r = fetch_raw(ts_url, headers)
        if r is None:
            self._send_text(502, '❌錯誤：代理請求失敗')
            return
        http_code, _, response = r

        cache_headers = {
            'Content-Type': content_type,
            'Cache-Control': 'public, max-age=%d' % CACHE_TIME,
            'Expires': time.strftime('%a, %d %b %Y %H:%M:%S',
                                     time.gmtime(time.time() + CACHE_TIME)) + ' UTC',
            'X-Cache': 'MISS',
        }

        # 保存到緩存
        if ENABLE_CACHE and response:
            try:
                with open(cache_file, 'wb') as f:
                    f.write(response)
            except OSError:
                pass

        self.send_response(http_code)
        self.send_header('Content-Length', str(len(response)))
        for k, v in cache_headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(response)

    def _serve_ts_cache(self, cache_file):
        try:
            filesize = os.path.getsize(cache_file)
        except OSError:
            self._send_text(502, '❌錯誤：讀取緩存失敗')
            return
        common = {
            'Content-Type': 'video/MP2T',
            'Cache-Control': 'public, max-age=%d' % CACHE_TIME,
            'Expires': time.strftime('%a, %d %b %Y %H:%M:%S',
                                     time.gmtime(time.time() + CACHE_TIME)) + ' UTC',
            'X-Cache': 'HIT',
        }
        range_header = self.headers.get('Range')
        if range_header:
            # 解析 bytes=start-end
            seek_start, seek_end = 0, filesize - 1
            try:
                _, range_orig = range_header.split('=', 1)
                range_part = range_orig.split(',')[0]
                s, e = range_part.split('-', 1)
                seek_end = min(abs(int(e)), filesize - 1) if e.strip() else (filesize - 1)
                seek_start = abs(int(s)) if s.strip() and seek_end >= abs(int(s)) else 0
            except (ValueError, IndexError):
                seek_start, seek_end = 0, filesize - 1
            if seek_start > 0 or seek_end < (filesize - 1):
                length = seek_end - seek_start + 1
                self.send_response(206)
                self.send_header('Content-Range',
                                 'bytes %d-%d/%d' % (seek_start, seek_end, filesize))
                self.send_header('Content-Length', str(length))
                for k, v in common.items():
                    self.send_header(k, v)
                self.end_headers()
                with open(cache_file, 'rb') as fp:
                    fp.seek(seek_start)
                    remaining = length
                    while remaining > 0:
                        chunk = fp.read(8192 if remaining > 8192 else remaining)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
        # 完整檔案
        self.send_response(200)
        self.send_header('Content-Length', str(filesize))
        for k, v in common.items():
            self.send_header(k, v)
        self.end_headers()
        with open(cache_file, 'rb') as fp:
            while True:
                chunk = fp.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    # ---------- ofiii 點播頻道 ----------
    def _handle_vod(self, channel_id, query, base_url):
        headers = list(BROWSER_HEADERS)

        # 獲取構建 ID
        build_id = get_build_id()

        # 獲取節目數據
        json_url = 'https://www.ofiii.com/_next/data/%s/channel/watch/%s.json' % (build_id, channel_id)
        json_data = fetch_url(json_url, headers)
        if not json_data:
            self._send_text(500, '❌錯誤：無法獲取節目數據')
            return
        try:
            data = json.loads(json_data.decode('utf-8'))
        except ValueError:
            self._send_text(500, '❌錯誤：解析節目數據失敗')
            return

        # 提取節目清單
        try:
            programs = data['pageProps']['channel']['vod_channel_schedule']['programs']
        except (KeyError, TypeError):
            programs = []
        if not programs:
            self._send_text(404, '❌錯誤：目前無節目安排')
            return

        # 獲取節目 asset_id
        ch_asset_id = get_program_asset_id(programs, query.get('program_id'))
        if not ch_asset_id:
            self._send_text(404, '❌錯誤：無法獲取節目 asset_id')
            return

        # 建立複合 ID
        composite_id = channel_id + '%23' + ch_asset_id

        # 獲取頻道開頭 ofiii 系列播放地址
        device_id = generate_random_device_id()
        puid = get_cached_puid()
        vod_url = ('%s?device_type=pc&device_id=%s&media_type=playout-channel&asset_id=%s'
                   '&project_num=OFWEB00&puid=%s' % (BASE_URL, device_id, composite_id, puid))
        vod_data = fetch_url(vod_url, headers)
        if not vod_data:
            self._send_text(500, '❌錯誤：無法獲取播放地址')
            return
        try:
            vod_json = json.loads(vod_data.decode('utf-8'))
        except ValueError:
            vod_json = None
        if not vod_json or not vod_json.get('asset_urls'):
            self._send_text(500, '❌錯誤：解析播放地址失敗')
            return

        # 處理 M3U8 內容
        m3u8_content = process_m3u8(vod_json['asset_urls'][0], headers, query, base_url)
        if not m3u8_content:
            self._send_text(500, '❌錯誤：處理M3U8內容失敗')
            return

        # 輸出 M3U8 內容
        self._send_text(200, m3u8_content, 'application/vnd.apple.mpegurl')

    # ---------- 直播頻道 ----------
    def _handle_live(self, channel_id, query, base_url):
        device_id = generate_random_device_id()
        timestamp = int(time.time())
        puid = get_cached_puid()
        url = ('%s?device_type=pc&device_id=%s&media_type=channel&asset_id=%s&_t=%d'
               '&project_num=OFWEB00&puid=%s' % (BASE_URL, device_id, channel_id, timestamp, puid))

        response = fetch_url(url, list(BROWSER_HEADERS))
        if not response:
            self._send_text(500, '❌錯誤：獲取頻道信息失敗')
            return
        try:
            data = json.loads(response.decode('utf-8'))
        except ValueError:
            self._send_text(500, '❌錯誤：解析JSON響應失敗')
            return

        asset_urls = data.get('asset_urls') or []
        play_url = asset_urls[0] if asset_urls else ''
        if play_url and play_url.startswith(('http://', 'https://')):
            # 檢查是否需要啟用切片代理
            enable_slice = (query.get('proxy') == 'true') or ENABLE_SLICE_PROXY
            # 如果開啟切片代理，則處理 M3U8 內容
            if enable_slice:
                m3u8_content = process_m3u8(play_url, list(BROWSER_HEADERS), query, base_url)
                if m3u8_content:
                    self._send_text(200, m3u8_content, 'application/vnd.apple.mpegurl')
                    return
            # 否則直接跳轉
            self.send_response(302)
            self.send_header('Location', play_url)
            self.end_headers()
            return
        self._send_text(503, '❌錯誤：無法獲取有效的播放地址')


# ============================
# 入口
# ============================
def main():
    ap = argparse.ArgumentParser(description='ofiii 直播/點播代理（Python 版）')
    ap.add_argument('--host', default='0.0.0.0', help='監聽地址（默認 0.0.0.0）')
    ap.add_argument('--port', type=int, default=8080, help='監聽端口（默認 8080）')
    ap.add_argument('--self-test', action='store_true', help='運行內部自檢後退出')
    args = ap.parse_args()

    if ENABLE_PROXY and PROXY_TYPE.lower().startswith('socks'):
        try:
            import socks  # noqa: F401
        except ImportError:
            print('[ofiii] 提示：socks 代理已配置但未安裝 PySocks，'
                  '如需走 socks 代理請先 pip install PySocks', file=sys.stderr)

    if args.self_test:
        _self_test()
        return

    server = ThreadingHTTPServer((args.host, args.port), OfiiiHandler)
    print('ofiii.py 運行中：http://%s:%d/%s?token=%s' % (args.host, args.port, SCRIPT_NAME, SECRET_TOKEN))
    print('M3U 清單：http://%s:%d/%s?token=%s' % (args.host, args.port, SCRIPT_NAME, SECRET_TOKEN))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def _self_test():
    """不依賴外網的內部自檢。"""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(('PASS' if cond else 'FAIL'), '-', name)
        if not cond:
            ok = False

    # 1. device id 格式（UUIDv4 形式）
    did = generate_random_device_id()
    check('device_id 格式', bool(re.fullmatch(
        r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}', did)))

    # 2. 節目匹配：program_id 直接命中
    programs = [
        {'asset_id': 'a1', 'p_start': 0, 'p_end': 1},
        {'asset_id': 'a2', 'p_start': 0, 'p_end': 99999999999999},
    ]
    check('program_id 直接命中', get_program_asset_id(programs, 'a1') == 'a1')
    # 3. 節目匹配：按當前時間
    now_ms = int(time.time() * 1000)
    programs2 = [
        {'asset_id': 'old', 'p_start': 0, 'p_end': now_ms - 1000},
        {'asset_id': 'now', 'p_start': now_ms - 1000, 'p_end': now_ms + 3600000},
    ]
    check('按當前時間匹配', get_program_asset_id(programs2, None) == 'now')
    # 4. 節目匹配：無命中返回第一個
    check('無命中返回第一個', get_program_asset_id([{'asset_id': 'x'}], None) == 'x')
    check('空節目列表', get_program_asset_id([], None) == '')

    # 5. process_m3u8：選最高碼率 + 相對路徑解析 + ts 重寫
    import unittest.mock as mock
    master = ('#EXTM3U\n'
              '#EXT-X-STREAM-INF:BANDWIDTH=800000\nlow.m3u8\n'
              '#EXT-X-STREAM-INF:BANDWIDTH=2000000\nmid/high.m3u8\n')
    media = ('#EXTM3U\n#EXT-X-TARGETDURATION:10\n'
             '#EXTINF:10,\nseg1.ts\n'
             '#EXTINF:10,\nhttps://cdn.example.com/abs/seg2.ts?k=1\n')
    with mock.patch(__name__ + '.fetch_url') as fu:
        fu.side_effect = [master.encode(), media.encode()]
        out = process_m3u8('https://cdn.example.com/live/master.m3u8', [],
                           {'proxy': 'true'}, 'http://127.0.0.1:8080')
    check('選最高碼率(相對路徑拼接)',
          out is not None and 'ts_proxy=' in out and 'seg1.ts' not in out.split('ts_proxy=')[0])
    check('相對 ts 轉絕對',
          out is not None and urllib.parse.quote('https://cdn.example.com/live/mid/seg1.ts', safe='') in out)
    check('絕對 ts 保留',
          out is not None and urllib.parse.quote('https://cdn.example.com/abs/seg2.ts?k=1', safe='') in out)

    # 6. process_m3u8：未開啟切片代理時原文返回
    import sys as _sys
    _mod = _sys.modules[__name__]
    with mock.patch(__name__ + '.fetch_url') as fu, \
         mock.patch.object(_mod, 'ENABLE_SLICE_PROXY', False):
        fu.side_effect = [master.encode(), media.encode()]
        out2 = process_m3u8('https://cdn.example.com/live/master.m3u8', [], {}, 'http://x')
    check('切片代理關閉時原文返回', out2 == media)

    # 7. base_url 推導
    class FakeH:
        def __init__(self):
            self.headers = {'Host': 'example.com:9000', 'X-Forwarded-Proto': 'https'}
    # 直接測函數邏輯（不依賴 handler 實例）
    class FakeHandler:
        headers = {'Host': 'example.com:9000', 'X-Forwarded-Proto': 'https, http'}
    check('反代 https 推導', get_base_url(FakeHandler()) == 'https://example.com:9000')

    print('自檢%s' % ('全部通過' if ok else '有失敗項'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
