from pybo import create_app, db
from pybo.models import GenAIChatLog

# Flask 앱 생성
app = create_app()

# 앱 컨텍스트 안에서 DB 작업
with app.app_context():
    # 아직 없는 테이블/시퀀스만 생성
    db.create_all()
    print("DB create_all() 완료 - GenAIChatLog 테이블이 생성되었는지 확인하세요.")