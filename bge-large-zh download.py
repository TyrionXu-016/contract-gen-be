from modelscope import snapshot_download
import os

# 指定明确的下载目录
custom_dir = "./models/BAAI-bge-large-zh"
os.makedirs(custom_dir, exist_ok=True)

# 下载到指定目录
model_dir = snapshot_download(
    'BAAI/bge-large-zh',
    cache_dir=custom_dir
)
print(f"模型下载到: {model_dir}")

# 下载简体中文小型模型
#python -m spacy download zh_core_web_sm