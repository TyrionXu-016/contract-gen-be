# config.py
"""
配置文件
"""
import os

# 路径配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
LAWS_DIR = os.path.join(DATA_DIR, "laws")

# 模型配置
BGE_MODEL_NAME = "D:/fdu/fDu_homework/project_manager/models/BAAI-bge-large-zh/BAAI/bge-large-zh"
EMBEDDING_DIM = 1024
NORMALIZE_EMBEDDINGS = True

# 数据库配置
COLLECTION_CONTRACTS = "contract_templates"
COLLECTION_LAWS = "legal_regulations"
COLLECTION_CASE = "case_templates"  

# 检索配置
SIMILARITY_THRESHOLD = 0.75  # 相似度阈值
MAX_CONTRACT_RESULTS = 5
MAX_LAW_RESULTS = 10
MAX_CASE_RESULTS = 5

# 元数据字段
CONTRACT_METADATA_FIELDS = [
    "type", "region", "industry", "quality_score", 
    "key_words", "create_time", "version", "business_type"
]

LAW_METADATA_FIELDS = [
    "type", "region", "law_topic", "importance",
    "publish_date", "effect_status", "regulatory_authority"
]