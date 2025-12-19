import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader  # DirectoryLoader 추가
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RagService:
    def __init__(self):
        self.persist_directory = "data/chroma_db"
        self.pdf_dir = "data/pdfs"

        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={'device': 'cpu'}
        )

        self.vector_db = self._prepare_vector_db()

    def _prepare_vector_db(self):
        # 만약 기존 DB가 있다면 로드
        if os.path.exists(self.persist_directory) and os.listdir(self.persist_directory):
            print("기존 크로마디비를 로드합니다.")
            return Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)

        print("새로운 PDF 데이터를 인덱싱합니다...")

        # 폴더 내 모든 PDF를 읽어옴
        loader = DirectoryLoader(self.pdf_dir, glob="*.pdf", loader_cls=PyPDFLoader)
        documents = loader.load()

        # 텍스트 쪼개기
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)

        # 벡터 DB 생성 및 저장
        return Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )

    def get_relevant_context(self, question: str) -> str:
        # 질문과 가장 유사한 본문 2개 추출
        docs = self.vector_db.similarity_search(question, k=4)
        return "\n\n".join([doc.page_content for doc in docs])