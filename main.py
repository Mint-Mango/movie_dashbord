
# ============================================
# 어제의 박스오피스
# 영화진흥위원회(KOBIS) 일별 박스오피스 API 활용
# ============================================

import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. 웹페이지 기본 설정
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 2. 한국 시간 기준으로 어제 날짜 계산
# 배포 서버가 다른 나라 시간대를 사용해도 한국 날짜를 기준으로 한다.
KST = ZoneInfo("Asia/Seoul")
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)

# API에 전달할 날짜는 YYYYMMDD 형식으로 만든다.
target_dt = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜는 읽기 쉬운 YYYY-MM-DD 형식으로 만든다.
display_date = yesterday.strftime("%Y-%m-%d")

# 3. API 주소와 인증키 설정
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 인증키를 코드에 직접 입력하지 않고 Streamlit 비밀 금고에서 가져온다.
# secrets 설정이 누락된 경우에도 사용자가 원인을 알 수 있게 처리한다.
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except (KeyError, FileNotFoundError):
    st.error(
        "인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )
    st.code('KOBIS_KEY = "c33505f74bd56879f07950b8e90a3b40"')
    st.stop()


# 4. KOBIS API에서 박스오피스 데이터 가져오기
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(date_str, api_key):
    # 같은 날짜의 결과는 한 시간 동안 캐시에 저장해 API 호출을 줄인다.
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str,
        },
        timeout=20,
    )

    # HTTP 4xx 또는 5xx 응답은 예외로 처리한다.
    response.raise_for_status()

    # HTTP 상태코드가 200이어도 JSON에 faultInfo가 들어올 수 있다.
    return response.json()


# 5. 앱 제목과 조회 날짜 표시
st.title("🎬 어제의 박스오피스")
st.caption(
    f"조회 날짜: {display_date} "
    "(한국 시간 기준 어제 · 출처: 영화진흥위원회 KOBIS)"
)

st.divider()

# 6. API 요청 및 오류 처리
try:
    with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_dt, API_KEY)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "인터넷 연결을 확인한 뒤 잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.HTTPError as e:
    st.error(
        f"KOBIS 서버가 HTTP 오류를 반환했습니다: {e}. "
        "요청 주소와 서버 상태를 확인해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(
        f"KOBIS 서버에 연결하지 못했습니다: {e}. "
        "네트워크 연결이나 API 서버 상태를 확인해 주세요."
    )
    st.stop()

except ValueError:
    st.error(
        "API 응답을 JSON으로 해석하지 못했습니다. "
        "서버 응답이 정상인지 잠시 후 다시 확인해 주세요."
    )
    st.stop()

# 인증키가 틀리거나 API 사용에 문제가 있으면 faultInfo가 반환될 수 있다.
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.info("KOBIS 서버의 응답과 API 주소를 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo") or {}

    error_code = fault.get("errorCode", "코드 없음")
    error_message = fault.get("message", "상세 오류 메시지가 없습니다.")

    st.error("KOBIS API에서 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {error_code}")
    st.write(f"**오류 내용:** {error_message}")
    st.info(
        "다음 항목을 확인해 주세요.\n\n"
        "- Streamlit Cloud의 Secrets에 KOBIS_KEY가 올바르게 등록되어 있는지\n"
        "- 인증키가 유효하고 API 사용이 가능한지\n"
        "- API 요청 제한을 초과하지 않았는지"
    )
    st.stop()

# 정상 응답에서 영화 목록을 꺼낸다.
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("응답에 boxOfficeResult가 없습니다.")
    st.info("KOBIS API 응답 구조와 인증키를 확인해 주세요.")
    st.stop()

movies = box_office_result.get("dailyBoxOfficeList", [])

# 목록이 없거나 예상한 형식이 아닌 경우 안내한다.
if not isinstance(movies, list) or len(movies) == 0:
    st.warning(
        f"{display_date}의 영화 목록이 비어 있습니다. "
        "아직 집계되지 않았거나 해당 날짜의 데이터가 없을 수 있습니다."
    )
    st.info(
        "KOBIS 공식 사이트에서 해당 날짜의 일별 박스오피스를 확인해 주세요. "
        "인증키와 API 응답에 오류가 없는지도 확인해 주세요."
    )
    st.stop()

# 7. 영화 목록을 판다스 표로 변환
df = pd.DataFrame(movies)

# API에서 숫자도 문자열로 전달되므로 계산에 사용할 숫자형으로 변환한다.
numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]

for col in numeric_columns:
    if col not in df.columns:
        df[col] = 0

    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 영화명과 개봉일 컬럼이 누락된 경우에도 앱이 중단되지 않게 한다.
for col in ["movieNm", "openDt"]:
    if col not in df.columns:
        df[col] = ""

df["movieNm"] = df["movieNm"].fillna("").astype(str)
df["openDt"] = df["openDt"].fillna("").astype(str)

# 순위가 낮은 숫자부터 정렬한다.
df = df.sort_values("rank", ascending=True).reset_index(drop=True)

# 영화명이 없는 데이터는 화면에서 식별할 수 있도록 대체 문구를 넣는다.
df.loc[df["movieNm"].str.strip() == "", "movieNm"] = "영화명 미제공"

# 8. 1위 영화의 지표 카드 3개
first_movie = df.iloc[0]

st.subheader(f"🥇 박스오피스 1위: {first_movie['movieNm']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개",
    )

st.divider()

# 9. 전체 영화 순위표
st.subheader("📋 일별 박스오피스 순위표")
st.caption("순위, 영화명, 개봉일, 관객수, 누적관객, 스크린수")

table = df[
    ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
].copy()

table.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 관객수와 스크린수는 천 단위 쉼표를 사용해 표시한다.
for col in ["관객수", "누적관객", "스크린수"]:
    table[col] = table[col].map(lambda value: f"{value:,}")

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
)

st.divider()

# 10. 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
)

# 가로 막대그래프로 영화명과 관객수를 보기 쉽게 나타낸다.
fig = px.bar(
    top5,
    x="audiCnt",
    y="movieNm",
    orientation="h",
    labels={
        "audiCnt": "어제 관객수(명)",
        "movieNm": "영화명",
    },
    text="audiCnt",
)

# 막대 끝에 관객수를 천 단위 쉼표와 함께 표시한다.
fig.update_traces(
    texttemplate="%{x:,.0f}명",
    textposition="outside",
    cliponaxis=False,
)

fig.update_layout(
    yaxis_title="영화명",
    xaxis_title="어제 관객수(명)",
    xaxis=dict(tickformat=","),
    showlegend=False,
    margin=dict(l=10, r=70, t=20, b=10),
)

st.plotly_chart(fig, use_container_width=True)

# 11. 데이터 출처 안내
st.caption(
    "자료: 영화진흥위원회(KOBIS) 일별 박스오피스 Open API"
)
