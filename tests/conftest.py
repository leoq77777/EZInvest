"""
测试会话初始化：用内存 DB、假 Redis 和伪 RAG 替代外部依赖，便于在无 Docker 环境下运行 unit 测试。
"""
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

# 替换 MySQL 为内存 SQLite
import app.database.mysql_client as mysql_client

# 替换 Redis 客户端
import app.database.redis_client as redis_client_mod

# 替换 RAG 工具
import app.tools.rag as rag_mod


def _setup_sqlite_in_memory():
    engine = create_engine('sqlite:///:memory:', connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 覆写模块中的 engine 与 SessionLocal
    mysql_client.engine = engine
    mysql_client.SessionLocal = SessionLocal

    # 创建表
    try:
        mysql_client.Base.metadata.create_all(bind=engine)
    except Exception:
        pass


class FakeRedisClient:
    def __init__(self):
        self.store = {}
        self.client = self

    def ping(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        self.store[key] = value
        return True

    def delete(self, key):
        return int(self.store.pop(key, None) is not None)

    def exists(self, key):
        return int(key in self.store)

    def expire(self, key, time):
        return key in self.store

    def get_json(self, key):
        v = self.get(key)
        if v:
            try:
                return json.loads(v)
            except Exception:
                return None
        return None

    def set_json(self, key, value, ex=None):
        return self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    def close(self):
        self.store.clear()


class FakeRagTool:
    def __init__(self):
        self.docs = []
        self.index = type('I', (), {'ntotal': 0})()

    def add_documents(self, documents):
        for doc in documents:
            self.docs.append(doc)
        self.index.ntotal = len(self.docs)

    def search(self, query, top_k=5, filter_dict=None):
        results = []
        for i, doc in enumerate(self.docs[:top_k]):
            results.append({
                'text': doc.get('text', ''),
                'metadata': doc.get('metadata', {}),
                'score': 0.0,
                'rank': i + 1
            })
        return results

    def search_by_symbol(self, symbol, query, top_k=5):
        return self.search(query, top_k=top_k, filter_dict={'symbol': symbol})

    def get_stats(self):
        return {
            'total_vectors': self.index.ntotal,
            'embedding_dim': None,
            'index_path': mysql_client.settings.FAISS_INDEX_PATH
        }


@pytest.fixture(scope='session', autouse=True)
def replace_external_deps():
    """在测试会话开始前替换 MySQL/Redis/RAG 依赖"""
    _setup_sqlite_in_memory()

    # 覆写 redis_client
    redis_client_mod.redis_client = FakeRedisClient()

    # 覆写 rag_tool
    rag_mod.rag_tool = FakeRagTool()

    # yield 控制 fixture 生命周期
    yield

    # 会话结束时的清理（如果需要）
    try:
        redis_client_mod.redis_client.close()
    except Exception:
        pass
