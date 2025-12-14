# flk_crawler — 国家法律法规数据库爬取工具

从 **国家法律法规数据库**（https://flk.npc.gov.cn）  按关键词抓取法规 ，自动下载 `docx`/`pdf` 等附件，并将 `docx` 导出为 `txt` 文本。

支持两种使用方式：

- **命令行工具**
使用示例（命令行）：
  python flk_crawler.py -k 公司法
  python flk_crawler.py -k 合同法
  python flk_crawler.py -k 民法典 -p 5
  python flk_crawler.py -k 证券法 --no-filter


- **Python 库**（在其他项目中直接调用）

参数：

```text
keyword      : 搜索关键词，如 "公司法" / "民法典" / "证券法"
max_pages    : 搜索结果翻页数上限，默认 3
save_dir     : 保存目录，默认 "<keyword>_本体_flk"
exclude_words: 本体过滤时的排除词列表，默认使用 DEFAULT_EXCLUDE_WORDS
no_filter    : 如果 True，则不做“本体”过滤，搜索结果全部下载
cookie       : 可选 Cookie 字符串（否则使用 COOKIE_STR 或环境变量 FLK_COOKIE）
auto_txt     : 是否对 docx 自动导出 txt，默认 True
```

返回：
```text
{
    "id":    "<bbbs>",
    "title": "标题",
    "gbrq":  "公布日期",
    "doc_path": "下载到的 docx/pdf 路径或空字符串",
    "txt_path": "生成的 txt 路径或空字符串",
}
```

调用实例： 
```text
from flk_crawler import crawl_laws

results = crawl_laws(
    keyword="公司法",
    max_pages=3,
    save_dir="公司法_本体_flk",
)
```


# htsfw_crawler — 合同示范文本库爬取工具

从 **合同示范文本库**（https://htsfwb.samr.gov.cn/） 按关键词抓取“合同示范文本”，自动下载对应的 `PDF` 文档，并将 `PDF` 导出为 `txt` 文本。

支持两种使用方式：

- **命令行工具**

使用示例（命令行）：

```bash
# 按关键字“买卖”搜索前 1 页，并批量下载 PDF + TXT
python htsfw_crawler.py -k 买卖 -p 1

# 按关键字“租赁”搜索前 3 页
python htsfw_crawler.py -k 租赁 -p 3

# 直接根据已知合同 Id 下载
python htsfw_crawler.py --ids 5e068390-d87c-4ea5-aa83-18a8ed36e3ae
```

- **Python 库**（在其他项目中直接调用）

参数：

```text
keyword      : 搜索关键词（可选），如 "买卖" / "租赁" / "服务"
ids          : 合同 Id 列表（可选），例如 ["5e068390-d87c-4ea5-aa83-18a8ed36e3ae"]
max_pages    : 搜索结果翻页数上限，仅在 keyword 模式下生效，默认 1
save_dir     : 保存目录，默认 "合同示范文本_下载"
auto_txt     : 是否从 PDF 自动导出 txt，默认 True
```

返回（列表，每个元素形如）：

```text
{
    "id": "<合同示范文本 Id>",
    "title": "合同标题",
    "code": "合同编号（如 GF—2020—0102，可能为空）",
    "files": [
        {
            "type": "pdf",
            "path": "下载到的 pdf 文件路径或空字符串",
            "txt_path": "生成的 txt 路径或空字符串",
        }
    ]
}
```

调用实例：

```text
from htsfw_crawler import crawl_contracts

# 按关键字批量抓取
results = crawl_contracts(
    keyword="买卖",
    max_pages=2,
    save_dir="买卖合同示范文本",
)

# 或者指定若干 Id 直接抓取
results = crawl_contracts(
    ids=[
        "5e068390-d87c-4ea5-aa83-18a8ed36e3ae",
        "273e0034-7d9c-4358-80b1-1cdfb3754fec",
    ],
    save_dir="指定合同示范文本",
)
```


## 1. 环境要求

- Python 3.8+
- 依赖库：
  - `requests`
  - `python-docx`（仅 flk_crawler 使用，用于 docx → txt）
  - `beautifulsoup4`（仅 htsfw_crawler 使用，用于解析 HTML）
  - `pdfplumber`（仅 htsfw_crawler 使用，用于 pdf → txt）

安装依赖：

```bash
pip install requests python-docx beautifulsoup4 pdfplumber
```
