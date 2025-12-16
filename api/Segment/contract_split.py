import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    from langchain_text_splitters import CharacterTextSplitter  # LangChain 1.x 拆分后的官方实现
except ImportError:
    from langchain.text_splitter import CharacterTextSplitter  # 兼容旧版本 LangChain
import spacy  # 用于中文分词和文本解析的核心库
from spacy.lang.zh import Chinese

# 加载中文分词模型，如缺失则回退到内置空白模型
try:
    nlp = spacy.load("zh_core_web_sm")
except OSError:
    nlp = Chinese()

# ====================== 1. 爬虫输入接口：接收上游模块数据 ======================
def receive_crawl_data(crawl_data: dict) -> tuple[str, str, str]:
    """
    适配爬虫模块的输出格式，提取核心信息
    :param crawl_data: 爬虫返回的单条数据字典（来自crawl_laws的结果）
    :return: data_id, data_type, raw_text
    """
    # 从爬虫结果中提取字段，对应爬虫的返回格式
    data_id = crawl_data.get("id", "default_id")
    # 爬虫抓取的是法规，所以数据类型固定为"law"
    data_type = "law"
    # 读取txt文件内容作为原始文本（爬虫已自动生成txt）
    raw_text = ""
    txt_path = crawl_data.get("txt_path", "")
    if txt_path:
        try:
            with open(txt_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except Exception as e:
            print(f"读取txt文件失败：{e}")
    return data_id, data_type, raw_text

# ====================== 2. 分块核心逻辑 ======================
def split_contract(raw_text: str, data_type: str) -> list[str]:
    if data_type == "law":
        splitter = CharacterTextSplitter(separator="第", chunk_size=500, chunk_overlap=0)
        blocks = splitter.split_text(raw_text)
        blocks = ["第" + b for b in blocks if b]
    elif data_type == "case":
        blocks = [p for p in raw_text.split("\n") if p.strip()]
    else:
        doc = nlp(raw_text)
        blocks = []
        current_block = ""
        for token in doc:
            if token.text in ["一", "二", "三", "1.", "2.", "（", "）"] and current_block:
                blocks.append(current_block.strip())
                current_block = token.text
            else:
                current_block += token.text
        if current_block:
            blocks.append(current_block.strip())
    return blocks

# ====================== 3. 向量库输出接口 ======================
def send_to_vector_db(data_id: str, data_type: str, blocks: list[str]) -> list[dict]:
    structured_blocks = []
    for idx, block_content in enumerate(blocks):
        structured_blocks.append({
            "data_id": data_id,
            "block_id": f"{data_id}_block_{idx+1}",
            "block_type": data_type,
            "block_content": block_content
        })
    return structured_blocks
