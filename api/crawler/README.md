# flk_crawler — 国家法律法规数据库爬取工具

从 **国家法律法规数据库**（https://flk.npc.gov.cn）按关键词抓取法规 ，自动下载 `docx`/`pdf` 等附件，并将 `docx` 导出为 `txt` 文本。

支持两种使用方式：

- **命令行工具**
使用示例（命令行）：
  python flk_crawler.py -k 公司法
  python flk_crawler.py -k 合同法
  python flk_crawler.py -k 民法典 -p 5
  python flk_crawler.py -k 证券法 --no-filter


- **Python 库**（便于在其他项目中直接调用）

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



## 1. 环境要求

- Python 3.8+
- 依赖库：
  - `requests`
  - `python-docx`

安装依赖：

```bash
pip install requests python-docx

