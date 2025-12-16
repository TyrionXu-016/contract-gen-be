from api.dbManager.VectorDBManager import *
from api.crawler.htsfw_crawler import crawl_contracts
from api.crawler.flk_crawler import crawl_laws
from api.crawler.flal_crawler import crawl_cases

if __name__ == "__main__":
    db_manager = VectorDBManager()

    # ========== 步骤1：调用爬虫接口，抓取真实法规数据 ==========
    print("📌 开始抓取国家法律法规数据...")
    laws_keyword = "民法典"  # 可替换为"公司法"\"合同法"\"证券法"
    crawl_results = crawl_laws(
        laws_keyword, 
        max_pages=1,       # 抓取2页结果，可调整
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




    print("📌 开始抓取合同示范文本库数据...")
    contracts_results = crawl_contracts(
        keyword="买卖", #买卖 \ 租赁 \
        max_pages=2,
        auto_txt=True
    )
    print(f"✅ 爬虫完成，共抓取 {len(contracts_results)} 条合同示范文本数据\n")
    # ========== 步骤2：循环处理每条爬虫数据 ==========
    for idx, contract_data in enumerate(contracts_results, start=1):
        print(f"===== 处理第 {idx} 条数据：{contract_data.get('title')} =====")
        data_id, data_type, raw_text = receive_contract_data(contract_data)
        if not raw_text:
            print("❌ 该条数据无txt内容，跳过\n")
            continue
        print(f"📄 提取文本长度：{len(raw_text)} 字")
        # 向量入库
        contract_metadata = {
            "id":contract_data.get('id'),
            "title":contract_data.get('title'),
            "region":"全国",
        }
        db_manager.add_contract_template(content = raw_text,metadata = contract_metadata)





    print("📌 开始抓取人民法院案例数据...")
    case_results = crawl_cases(
        keyword="合同纠纷", #合同纠纷 \ 买卖合同纠纷 \ 建设工程施工合同纠纷
        max_pages=2,
        max_items=10,
        auto_txt=True
    )
    # "id": encoded_id,
    # "title": title,
    # "code": code,
    # "files": files,
    print(f"✅ 爬虫完成，共抓取 {len(case_results)} 条案例文本数据\n")
    for idx, case_data in enumerate(case_results, start=1):
        print(f"===== 处理第 {idx} 条数据：{case_data.get('title')} =====")
        data_id, data_type, raw_text = receive_contract_data(case_data)
        if not raw_text:
            print("❌ 该条数据无txt内容，跳过\n")
            continue
        print(f"📄 提取文本长度：{len(raw_text)} 字")
        # 向量入库
        contract_metadata = {
            "id":case_data.get('id'),
            "title":case_data.get('title'),
            "region":"全国",
        }
        db_manager.add_case_template(content = raw_text,metadata = contract_metadata)


    # ========== 步骤3：向量数据库本地保存 ==========
    db_manager.backup_database()
    print("🎉 全部数据处理完成，向量库已更新！")