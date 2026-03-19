“””
CGV 용아맥(용산 아이파크몰) 예매 오픈 알림 봇

- 특정 날짜 + 특정 영화 예매 오픈 시 텔레그램 알림
  “””

import os
import time
import json
import hashlib
import requests
from datetime import datetime
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get(“TELEGRAM_BOT_TOKEN”, “여기에_봇_토큰_입력”)
TELEGRAM_CHAT_ID   = os.environ.get(“TELEGRAM_CHAT_ID”,   “여기에_챗ID_입력”)

CHECK_INTERVAL = 2
TARGET_DATE    = “20260326”
TARGET_MOVIE   = “프로젝트 헤일메리”

CGV_THEATER_CODE = “0013”
CGV_URL = (
“https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx”
f”?theaterCode={CGV_THEATER_CODE}&date=”
)

HEADERS = {
“User-Agent”: (
“Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) “
“AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1”
),
“Referer”: “https://www.cgv.co.kr/”,
}

STATE_FILE = “seen_movies.json”

def now():
return datetime.now().strftime(”%Y-%m-%d %H:%M:%S”)

def send_telegram(message: str):
url = f”https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage”
payload = {
“chat_id”: TELEGRAM_CHAT_ID,
“text”: message,
“parse_mode”: “HTML”,
“disable_web_page_preview”: True,
“reply_markup”: {
“inline_keyboard”: [[
{“text”: “CGV 앱 열기”, “url”: “https://m.cgv.co.kr/Schedule/Movie/MovieList.aspx?cinema=0013”}
]]
},
}
try:
res = requests.post(url, json=payload, timeout=10)
if res.status_code == 200:
print(f”[{now()}] 텔레그램 전송 성공”)
else:
print(f”[{now()}] 텔레그램 오류: {res.text}”)
except Exception as e:
print(f”[{now()}] 텔레그램 예외: {e}”)

def fetch_movies_for_date(date_str: str) -> list:
url = CGV_URL + date_str
movies = []
try:
res = requests.get(url, headers=HEADERS, timeout=15)
res.encoding = “utf-8”
soup = BeautifulSoup(res.text, “html.parser”)
for section in soup.select(“div.col-times”):
title_tag = section.select_one(“strong.title”)
time_tags = section.select(“a.btn-timeinfo”)
if not title_tag:
continue
title = title_tag.get_text(strip=True)
times = [t.get_text(strip=True) for t in time_tags if t.get_text(strip=True)]
if times:
movies.append({“date”: date_str, “title”: title, “times”: times, “count”: len(times)})
except Exception as e:
print(f”[{now()}] 크롤링 오류: {e}”)
return movies

def load_state() -> dict:
if os.path.exists(STATE_FILE):
with open(STATE_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)
return {}

def save_state(state: dict):
with open(STATE_FILE, “w”, encoding=“utf-8”) as f:
json.dump(state, f, ensure_ascii=False, indent=2)

def make_key(movie: dict) -> str:
raw = f”{movie[‘date’]}*{movie[‘title’]}*{movie[‘count’]}”
return hashlib.md5(raw.encode()).hexdigest()

def check_once(state: dict) -> dict:
movies = fetch_movies_for_date(TARGET_DATE)
for movie in movies:
if TARGET_MOVIE not in movie[“title”]:
continue
key = make_key(movie)
if key not in state:
state[key] = True
date_fmt = f”{TARGET_DATE[:4]}.{TARGET_DATE[4:6]}.{TARGET_DATE[6:]}”
times_str = “ / “.join(movie[“times”][:6])
if len(movie[“times”]) > 6:
times_str += f” 외 {len(movie[‘times’])-6}회”
message = (
f”<b>[용아맥 예매 오픈!]</b>\n\n”
f”날짜: {date_fmt}\n”
f”영화: {movie[‘title’]}\n”
f”시간: {times_str}”
)
send_telegram(message)
print(f”[{now()}] 체크 완료”)
return state

def main():
print(f”[{now()}] 용아맥 모니터링 시작! ({CHECK_INTERVAL}초 간격)”)
send_telegram(
f”<b>용아맥 예매 알림봇 시작!</b>\n”
f”{CHECK_INTERVAL}초마다 체크합니다.\n”
f”대상: {TARGET_DATE[:4]}.{TARGET_DATE[4:6]}.{TARGET_DATE[6:]} / {TARGET_MOVIE}”
)
state = load_state()
while True:
try:
state = check_once(state)
save_state(state)
except Exception as e:
print(f”[{now()}] 오류: {e}”)
time.sleep(CHECK_INTERVAL)

if **name** == “**main**”:
main()
