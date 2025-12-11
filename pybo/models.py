from pybo import db
from sqlalchemy import Sequence

class RegionData(db.Model):
    __tablename__ = 'region_data'

    id = db.Column(db.Integer, Sequence('region_data_id_seq'), primary_key=True)

    district = db.Column(db.String(50), nullable=False)   # 구 이름
    year = db.Column(db.Integer, nullable=False)          # 연도

    grdp = db.Column(db.Integer)                          # 지역총생산
    basic_beneficiaries = db.Column(db.Integer)           # 기초생활수급자
    multicultural_hh = db.Column(db.Integer)              # 다문화 가구 수
    population = db.Column(db.Integer)                    # 전체 인구
    divorce = db.Column(db.Integer)                       # 이혼 수
    child_facility = db.Column(db.Integer)                # 아동센터 시설 수
    child_user = db.Column(db.Integer)                    # 아동센터 이용자 수
    single_parent = db.Column(db.Integer)                 # 한부모 가정 수
    birth_cnt = db.Column(db.Integer)                     # 출생아 수
    academy_cnt = db.Column(db.Float)                     # 학원 수


class RegionForecast(db.Model):
    __tablename__ = 'region_forecast'

    id = db.Column(db.Integer,
                   db.Sequence('region_forecast_id_seq'),
                   primary_key=True)
    district = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    predicted_child_user = db.Column(db.Float, nullable=False)

    single_parent        = db.Column(db.Float)
    basic_beneficiaries  = db.Column(db.Float)
    multicultural_hh     = db.Column(db.Float)
    academy_cnt          = db.Column(db.Float)
    grdp                 = db.Column(db.Float)

    model_version = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class PredictionLog(db.Model):
    __tablename__ = 'prediction_log'

    id = db.Column(db.Integer, Sequence('prediction_log_id_seq'), primary_key=True)
    region = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    predicted_value = db.Column(db.Float, nullable=False)

class Question(db.Model):
    __tablename__ = 'question'
    id = db.Column(db.Integer, db.Sequence('question_seq', start=1, increment=1), primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    user = db.relationship('Users', backref=db.backref('question_set'))


class Answer(db.Model):
    __tablename__ = 'answer'
    id = db.Column(db.Integer, db.Sequence('answer_seq', start=1, increment=1), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
    question = db.relationship('Question', backref=db.backref('answer_set'))
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)


class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, db.Sequence('users_seq', start=1, increment=1), primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

class GenAIChatLog(db.Model):
    __tablename__ = 'genai_chat_log'

    id = db.Column(
        db.Integer,
        db.Sequence('genai_chat_log_seq', start=1, increment=1),
        primary_key=True
    )

    # 로그인 안 한 상태에서도 쓸 수 있게 nullable=True
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id'),
        nullable=True
    )

    # 어느 페이지/기능에서 쓴 건지 (예: 'qna', 'dashboard', 'predict' 등)
    page = db.Column(db.String(50), nullable=True)

    # 어떤 타입의 생성 기능인지 (보고서/정책/지표/QA 구분용)
    task_type = db.Column(db.String(30), nullable=False)

    question = db.Column(db.Text(), nullable=False)
    answer = db.Column(db.Text(), nullable=False)

    created_at = db.Column(
        db.DateTime(),
        nullable=False,
        server_default=db.func.now()
    )

    user = db.relationship(
        'Users',
        backref=db.backref('genai_chat_logs', lazy='dynamic')
    )