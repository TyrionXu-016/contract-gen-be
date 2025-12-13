### 大语言模型调用
模型以及版本选择：doubao-seed-1-6-251015

### 激活虚拟环境
source venv/bin/activate

### 下载依赖包
conda install -c conda-forge fastapi uvicorn transformers pytorch openai

### api_key
请在https://console.volcengine.com/iam/keymanage 生成密钥
保留.env_example文件，自己创建一个.env文件，填入里面所有的信息，
AI_SERVICE_BASE_URL ="http://localhost:8000/docs"是对的，不用改，直接用
向量库用的模型密钥也可以像这样在.env_example文件添加一下

### 运行
uvicorn main:app --reload --host 0.0.0.0 --port 8000

### 查看网页，使用大模型
http://127.0.0.1:8000/docs

### model_api结构
front.html 是给（徐阳）参考，是用的FastAPI作为模型接口，如果不行再改
knowledge_retriever.py 作为向量知识库的接口，目前是模拟状态，还待完善（等陈玲）
main.py 配置模型和输入输出的地方，已在根目录放了刘娅给的最新提示词

