"""
CGV 용아맥(용산 아이파크몰) 예매 오픈 알림 봇
- CGV 상영 스케줄 페이지를 주기적으로 체크
- 새로운 날짜/영화 예매가 열리면 텔레그램으로 즉시 알림
"""

import os
import time
import json
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ──────────────────────────────────────────
# ✅ 여기에 본인 정보 입력
# ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "여기에_봇_토큰_입력")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "여기에_챗ID_입력")

# 모니터링 간격 (초)
CHECK_INTERVAL = 2

# CGV 용아맥 상영관 코드: P007 (용산아이파크몰)
CGV_THEATER_CODE = "0013"   # 용산아이파크몰 CGV 코드
CGV_URL = (
    "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
    f"?theaterCode={CGV_THEATER_CODE}&date="
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://www.cgv.co.kr/",
}

STATE_FILE = "seen_movies.json"

# ──────────────────────────────────────────
# 텔레그램 메시지 전송
# ──────────────────────────────────────────
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "CGV 앱 열기", "url": "https://m.cgv.co.kr/Schedule/Movie/MovieList.aspx?cinema=0013"}

            ]]
        },
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"[{now()}] ✅ 텔레그램 전송 성공")
        else:
            print(f"[{now()}] ❌ 텔레그램 오류: {res.text}")
    except Exception as e:
        print(f"[{now()}] ❌ 텔레그램 예외: {e}")

# ──────────────────────────────────────────
# 날짜 목록 가져오기 (7일 앞까지 체크)
# ──────────────────────────────────────────
def get_available_dates():
    """CGV에서 예매 가능한 날짜 목록을 가져옵니다."""
    from datetime import timedelta
    dates = []
    today = datetime.now()
    for i in range(14):  # 오늘부터 14일 후까지
        d = today + timedelta(days=i)
        dates.append(d.strftime("%Y%m%d"))
    return dates

# ──────────────────────────────────────────
# 특정 날짜의 상영 영화 목록 크롤링
# ──────────────────────────────────────────
def fetch_movies_for_date(date_str: str) -> list[dict]:
    url = CGV_URL + date_str
    movies = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        # CGV 상영시간표 파싱
        movie_sections = soup.select("div.col-times")
        for section in movie_sections:
            title_tag = section.select_one("strong.title")
            time_tags  = section.select("a.btn-timeinfo")

            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            times = [t.get_text(strip=True) for t in time_tags if t.get_text(strip=True)]

            if times:
                movies.append({
                    "date":  date_str,
                    "title": title,
                    "times": times,
                    "count": len(times),
                })

    except Exception as e:
        print(f"[{now()}] ⚠️ {date_str} 크롤링 오류: {e}")

    return movies

# ──────────────────────────────────────────
# 상태 저장/로드
# ──────────────────────────────────────────
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def make_key(movie: dict) -> str:
    raw = f"{movie['date']}_{movie['title']}_{movie['count']}"
    return hashlib.md5(raw.encode()).hexdigest()

# ──────────────────────────────────────────
# 메인 체크 루프
# ──────────────────────────────────────────
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def check_once(state: dict) -> dict:
    dates  = get_available_dates()
    new_items = []

    for date_str in dates:
        movies = fetch_movies_for_date(date_str)
        for movie in movies:
            key = make_key(movie)
            if key not in state:
                state[key] = True
                new_items.append(movie)
        time.sleep(2)  # 서버 부하 방지

    if new_items:
        grouped: dict[str, list] = {}
        for item in new_items:
            grouped.setdefault(item["date"], []).append(item)

        for date_str, movies in grouped.items():
            date_fmt = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
            lines = [f"🎬 <b>[용아맥 예매 오픈!]</b> {date_fmt}\n"]
            for m in movies:
                times_str = " / ".join(m["times"][:6])
                if len(m["times"]) > 6:
                    times_str += f" 외 {len(m['times'])-6}회"
                lines.append(f"▶ {m['title']}\n   ⏰ {times_str}\n")

            lines.append("\n🔗 <a href='https://www.cgv.co.kr/theaters/?areaCode=01&theaterCode=0013'>지금 예매하기</a>")
            message = "\n".join(lines)
            send_telegram(message)
            time.sleep(1)

    else:
        print(f"[{now()}] 변경 없음 (체크 완료)")

    return state

def main():
    print(f"[{now()}] 🚀 용아맥 모니터링 시작! ({CHECK_INTERVAL}초 간격)")
    send_telegram(
        "🤖 <b>용아맥 예매 알림봇 시작!</b>\n"
        f"✅ {CHECK_INTERVAL}초마다 CGV 용산 아이파크몰 예매를 체크합니다.\n"
        "새 상영 일정이 열리면 즉시 알려드릴게요!"
    )

    state = load_state()

    if not state:
        print(f"[{now()}] 📦 초기 상태 수집 중... (첫 실행 시 알림 없음)")
        dates = get_available_dates()
        for date_str in dates:
            movies = fetch_movies_for_date(date_str)
            for movie in movies:
                state[make_key(movie)] = True
            time.sleep(2)
        save_state(state)
        print(f"[{now()}] ✅ 초기 상태 저장 완료. 이후 새로운 예매만 알림!")

    while True:
        try:
            state = check_once(state)
            save_state(state)
        except Exception as e:
            print(f"[{now()}] ❌ 체크 오류: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
