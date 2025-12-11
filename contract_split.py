import sys
sys.stdout.reconfigure(encoding='utf-8')

from langchain.text_splitter import CharacterTextSplitter  # 用于文本分块的工具库
import spacy  # 用于中文分词和文本解析的核心库

from flk_crawler import crawl_laws

# 加载中文分词模型
nlp = spacy.load("zh_core_web_sm")

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
        splitter = CharacterTextSplitter(separator="第", chunk_size=200, chunk_overlap=0)
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

# ====================== 4. 主函数：串联爬虫+分块+向量库流程 ======================
if __name__ == "__main__":
    # ========== 步骤1：调用爬虫接口，抓取真实法规数据 ==========
    print("📌 开始抓取法规数据...")
    # 配置爬虫参数：关键词、翻页数等
    crawl_results = crawl_laws(
        keyword="民法典",  # 可替换为"公司法""合同法"等
        max_pages=2,       # 抓取2页结果，可调整
        auto_txt=True      # 自动生成txt文件，必须开启
    )
    print(f"✅ 爬虫完成，共抓取 {len(crawl_results)} 条法规数据\n")

    # ========== 步骤2：循环处理每条爬虫数据 ==========
    for idx, crawl_data in enumerate(crawl_results, start=1):
        print(f"===== 处理第 {idx} 条数据：{crawl_data.get('title')} =====")
        
        # 调用输入接口，提取信息
        data_id, data_type, raw_text = receive_crawl_data(crawl_data)
        if not raw_text:
            print("❌ 该条数据无txt内容，跳过\n")
            continue
        print(f"📄 提取文本长度：{len(raw_text)} 字")

        # 调用分块逻辑
        split_blocks = split_contract(raw_text, data_type)
        print(f"🔧 分块完成，共 {len(split_blocks)} 个分块")

        # 调用输出接口，生成向量库数据
        vector_data = send_to_vector_db(data_id, data_type, split_blocks)
        print(f"📊 生成向量库数据 {len(vector_data)} 条\n")