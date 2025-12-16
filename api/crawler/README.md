# flk_crawler — 国家法律法规数据库爬取工具

从 **国家法律法规数据库**（https://flk.npc.gov.cn）  按关键词抓取法规 ，自动下载 `docx`/`pdf` 等附件，并将 `docx` 导出为 `txt` 文本。

支持两种使用方式：

- **命令行工具**  
使用示例（命令行）：
```bash
python flk_crawler.py -k 公司法
python flk_crawler.py -k 合同法
python flk_crawler.py -k 民法典 -p 5
python flk_crawler.py -k 证券法 --no-filter
```

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
```python
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

```python
from htsfw_crawler import crawl_contracts

# 按关键字批量抓取
results = crawl_contracts(
    keyword="买卖",
    max_pages=2,
    save_dir="买卖合同示范文本",
)
```


# flal_crawler — 人民法院案例库爬取工具

从 **人民法院案例库**（https://rmfyalk.court.gov.cn/） 按关键词抓取“典型案例”，自动下载对应的 `PDF` 文书，并使用 `pdfplumber` 抽取正文为 `txt` 文本。

> ⚠ 使用前置条件：  
> - 需在浏览器中正常登录人民法院案例库；  
> - 在开发者工具（F12）Network 面板中找到 `cpwsAl/search` 请求；  
> - 从该请求的 Header/Cookie 中复制 `faxin-cpws-al-token`（一长串 JWT）；  
> - 运行脚本时通过 `--token` 参数传入该 token。

## 1. 命令行用法

示例：

```bash
# 按关键字“合同纠纷”搜索第 1 页，下载 PDF + TXT
python flal_crawler.py -k 合同纠纷 -p 1 --token "<你的 faxin-cpws-al-token>"

# 按关键字“买卖合同纠纷”搜索前 2 页，限制最多抓取 20 条案例
python flal_crawler.py -k 买卖合同纠纷 -p 2 --max-items 20 --token "<token>"

# 控制下载频率：每条之间暂停 5 秒
python flal_crawler.py -k 建设工程施工合同纠纷 -p 1 --sleep-download 5 --token "<token>"

# 直接根据已知案例 Id 下载
python flal_crawler.py --ids "bEWKpCPsHgwg4a9%2FN4sfaYhgXlUukPninqvENCvDrEk%3D" --token "<token>"
```

主要命令行参数：

```text
-k, --keyword        : 搜索关键词（可选），如 "合同纠纷" / "买卖合同纠纷"
-p, --max-pages      : 搜索结果翻页数上限，仅在 -k / --keyword 模式下生效，默认 1
--page-size          : 每页条数，默认 10
--ids                : 直接指定案例 id（使用 search 返回的 id），多个以逗号分隔
--save-dir           : 保存目录，默认 "人民法院案例_下载"
--no-txt             : 不自动从 PDF 导出 txt（默认会导出）
--token              : 必填，浏览器抓包得到的 faxin-cpws-al-token
--debug              : 打印调试信息（如原始 JSON）
--max-items          : 本次最多抓取的案例数量上限，默认 50
--sleep-search       : 每页搜索之间的休眠时间（秒），默认 1.0
--sleep-download     : 每条案例下载之间的休眠时间（秒），默认 2.0
```

## 2. 作为 Python 库调用

参数（核心函数 `crawl_contracts`）：

```text
keyword       : 搜索关键词（可选），如 "合同纠纷" / "房屋买卖合同纠纷"
ids           : 案例 id 列表（可选），如 ["bEWKpC...%2F...%3D", "..."]
max_pages     : 搜索结果翻页数上限，仅在 keyword 模式下生效，默认 1
save_dir      : 保存目录，默认 "人民法院案例_下载"
auto_txt      : 是否从 PDF 自动导出 txt，默认 True
token         : 必填，faxin-cpws-al-token
page_size     : 每页条数，默认 10
debug         : 是否输出调试信息，默认 False
max_items     : 限制本次最多抓取多少条案例，默认 50（None 表示不限制）
search_delay  : 每一页搜索之间的间隔（秒），默认 1.0
download_delay: 下载每个 PDF 之间的间隔（秒），默认 2.0
```

返回（列表，每个元素形如）：

```python
{
    "id": "<案例 id（search 的 id 原样返回）>",
    "title": "案例标题（cpws_al_title 解析后的纯文本）",
    "code": "案号（若能从详情页解析到）或空字符串",
    "files": [
        {
            "type": "pdf",
            "path": "下载到的 pdf 文件路径或空字符串",
            "txt_path": "生成的 txt 路径或空字符串（auto_txt=True 时）",
        }
    ],
}
```

调用示例：

```python
from flal_crawler import crawl_cases

# 按关键字抓取前 1 页，最多 10 条
results = crawl_cases(
    keyword="合同纠纷",
    max_pages=1,
    page_size=10,
    max_items=10,
    save_dir="人民法院案例_下载",
    token="你的_faxin-cpws-al-token",
)
```


## 1. 环境要求

- Python 3.8+
- 依赖库：
  - `requests`
  - `python-docx`
  - `beautifulsoup4`
  - `pdfplumber`

安装依赖：

```bash
pip install requests python-docx beautifulsoup4 pdfplumber
```
