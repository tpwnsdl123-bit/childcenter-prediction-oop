import os
from dotenv import load_dotenv  # [필수] 이 줄이 있어야 .env를 읽을 수 있음

# env 파일 로드 (가장 먼저 실행되어야 함)
load_dotenv()

BASE_DIR = os.path.dirname(__file__)

# 환경변수 가져오기
SQLALCHEMY_DATABASE_URI = os.getenv("DB_URI")

# 잘 가져왔는지 검증 (안전 장치)
if not SQLALCHEMY_DATABASE_URI:
    raise ValueError("오류: .env 파일에서 'DB_URI'를 찾을 수 없습니다. 파일 위치나 오타를 확인해주세요.")

# 디버깅용 - 배포 시에는 지우기
print(f" DB 연결 설정 완료: {SQLALCHEMY_DATABASE_URI}")

SQLALCHEMY_TRACK_MODIFICATIONS = False

# 시크릿 키 가져오기
SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not SECRET_KEY:
    print("경고: FLASK_SECRET_KEY가 설정되지 않았습니다. 기본값을 사용합니다.")
    SECRET_KEY = "dev" # 비상용 기본값