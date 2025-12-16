from api.dbManager.VectorDBManager import VectorDBManager
from api.Segment.contract_split import receive_crawl_data
from api.crawler.flk_crawler import crawl_laws

# ====================== 4. 主函数：串联爬虫+分块+向量库流程 ======================
if __name__ == "__main__":
    # ========== 步骤1：调用爬虫接口，抓取真实法规数据 ==========
    print("📌 开始抓取法规数据...")
    # 配置爬虫参数：关键词、翻页数等
    laws_keyword = "合同法"  # 可替换为"公司法""合同法"等
    crawl_results = crawl_laws(
        laws_keyword, 
        max_pages=1,       # 抓取2页结果，可调整
        auto_txt=True      # 自动生成txt文件，必须开启
    )
    print(f"✅ 爬虫完成，共抓取 {len(crawl_results)} 条法规数据\n")

    # ========== 步骤2：循环处理每条爬虫数据 ==========
    db_manager = VectorDBManager()
    for idx, crawl_data in enumerate(crawl_results, start=1):
        print(f"===== 处理第 {idx} 条数据：{crawl_data.get('title')} =====")
        
        # 调用输入接口，提取信息
        data_id, data_type, raw_text = receive_crawl_data(crawl_data)
        if not raw_text:
            print("❌ 该条数据无txt内容，跳过\n")
            continue
        print(f"📄 提取文本长度：{len(raw_text)} 字")

        if(data_type == "law"):
            # 法律向量入库
            law_metadata = {
                "id":crawl_data.get('id'),
                "title":crawl_data.get('title'),
                "region":"全国",
                "gbrq_date":crawl_data.get('gbrq'),
            }
            db_manager.add_law_regulation(content = raw_text,metadata = law_metadata)
        elif(data_type == "case"):
            # 法律案例入库
            case_metadata = {
                "id":crawl_data.get('id'),
                "title":crawl_data.get('title'),
                "gbrq_date":crawl_data.get('gbrq'),
            }
            db_manager.add_case_template(content = raw_text,metadata = case_metadata)

    # ========== 步骤3：向量数据库本地保存 ==========
    db_manager.backup_database()
    print("🎉 全部数据处理完成，向量库已更新！")