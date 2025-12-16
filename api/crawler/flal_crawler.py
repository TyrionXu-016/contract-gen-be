# -*- coding: utf-8 -*-
"""
人民法院案例库（https://rmfyalk.court.gov.cn/）案例抓取工具

功能：
  - 按关键词搜索案例（调用 /cpws_al_api/api/cpwsAl/search 接口，POST + JSON）；
  - 从搜索结果中提取 id / 标题 / 裁判要旨等基础信息；
  - 访问详情页 /view/content.html?id=...，解析标题 / 案号等信息；
  - 调用 /cpws_al_api/api/cpwsAl/contentDownload?id=... 下载 PDF 文书；
  - 使用 pdfplumber 将 PDF 导出为 txt 文本；
  - 既可以作为命令行工具使用，也可以作为库被其他 Python 代码调用。

⚠ 使用前置条件：
  - 需要你先在浏览器正常登录 rmfyalk.court.gov.cn；
  - 在开发者工具（F12）Network 中找到 cpwsAl/search 请求，
    复制其中的 faxin-cpws-al-token（那一长串 JWT）；
  - 运行脚本时通过 --token 参数传入该 token，例如：

      python flal_crawler.py -k 合同纠纷 -p 1 --token "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

依赖：
  pip install requests beautifulsoup4 pdfplumber
"""

import os
import re
import time
import json
import argparse
from typing import Any, List, Dict, Optional
from urllib.parse import quote, unquote

import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4
import pdfplumber              # pip install pdfplumber


# ----------------- 常量配置 -----------------

BASE_URL = "https://rmfyalk.court.gov.cn"

# 搜索接口（POST + JSON）：
SEARCH_API_URL = BASE_URL + "/cpws_al_api/api/cpwsAl/search"

# PDF 下载接口：
PDF_DOWNLOAD_URL = BASE_URL + "/cpws_al_api/api/cpwsAl/contentDownload"

# 详情页 URL 模板：
CONTENT_VIEW_PATH = "/view/content.html"

# 水印字符：人民法院案例库 + 页码相关
WATERMARK_CHARS = set("库例案院法民人第页")


# ----------------- 工具函数 -----------------

def ensure_dir(path: str) -> None:
    """确保目录存在。"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def safe_filename(name: str) -> str:
    """将任意标题转换为适合作为文件名的字符串。"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = name.strip()
    return name or "unnamed"


def html_to_text(html: str) -> str:
    """把包含 <em><p> 等标签的 HTML 转为纯文本。"""
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def clean_court_text(raw: str) -> str:
    """
    清理人民法院案例库 PDF 抽取后的文本：
      - 去掉只由“库例案院法民人第页”等水印字符组成的行
      - 去掉行中成串重复的水印字符（如“法 法 法”、“库 库 库”等）
      - 合理压缩空行
    """
    cleaned_lines: List[str] = []

    for line in raw.splitlines():
        # 用于判断整行是不是水印：先去掉空格
        no_space = line.replace(" ", "")

        # 空行 -> 保留一个真正的空行
        if not no_space:
            cleaned_lines.append("")
            continue

        # 如果行内“非空格字符”全部是水印字符 -> 认为是背景/页眉/页脚，整行丢弃
        if all(ch in WATERMARK_CHARS for ch in no_space):
            continue

        # 对于混在正文里的“法 法 法”“民 民 民”之类，删掉成串的重复水印
        # 使用相对保守的策略：只删 3 连以上的 same char（避免误伤正常文本）
        cleaned = line
        for ch in WATERMARK_CHARS:
            pattern3 = f"{ch} {ch} {ch}"
            while pattern3 in cleaned:
                cleaned = cleaned.replace(pattern3, "")
            # 有些 PDF 会是 4、5 个连着，3 连删掉后会剩下 2 连，
            # 这里再粗暴一点把 "ch ch" 也删掉
            pattern2 = f"{ch} {ch}"
            while pattern2 in cleaned:
                cleaned = cleaned.replace(pattern2, "")

        cleaned_lines.append(cleaned)

    # 再压缩连续空行为单空行
    result_lines: List[str] = []
    last_blank = False
    for line in cleaned_lines:
        if line.strip() == "":
            if not last_blank:
                result_lines.append("")
            last_blank = True
        else:
            result_lines.append(line)
            last_blank = False

    return "\n".join(result_lines)


def pdf_to_txt(pdf_path: str, txt_path: str) -> None:
    """
    使用 pdfplumber 将 PDF 内容导出为 txt 文本（utf-8），
    并对人民法院案例库的水印做清洗处理。
    """
    texts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text.strip())

    raw = "\n\n".join(texts)
    content = clean_court_text(raw)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)


# ----------------- Session -----------------

def new_session(token: str = "") -> requests.Session:
    """
    创建一个带通用 Header 的 Session。

    token: 在浏览器 F12 -> Network -> 任意 cpwsAl/search 请求中
           复制出的 faxin-cpws-al-token 那一长串 JWT。
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/view/list.html",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json;charset=UTF-8",
    })

    if token:
        # header 里带一份
        s.headers["faxin-cpws-al-token"] = token
        # cookie 里再带一份
        s.cookies.set(
            "faxin-cpws-al-token",
            token,
            domain="rmfyalk.court.gov.cn",
            path="/"
        )

    return s


# ----------------- 搜索 payload & 请求 -----------------

def build_search_payload(keyword: str, page: int, size: int = 10) -> Dict[str, Any]:
    """
    构造 /cpwsAl/search 的 JSON 请求体。

    Request Payload 示例：

    {
      "page":1,
      "size":10,
      "lib":"qb",
      "searchParams":{
        "userSearchType":1,
        "isAdvSearch":"0",
        "selectValue":["qw"],
        "lib":"cpwsAl_qb",
        "sort_field":"",
        "keyTitle":["合同"]
      }
    }
    """
    payload: Dict[str, Any] = {
        "page": page,
        "size": size,
        "lib": "qb",
        "searchParams": {
            "userSearchType": 1,
            "isAdvSearch": "0",
            "selectValue": ["qw"],        # 检索字段：qw = 全文
            "lib": "cpwsAl_qb",
            "sort_field": "",
            "keyTitle": [keyword],        # 用传入的关键词
        }
    }
    return payload


def fetch_search_page(
    session: requests.Session,
    keyword: str,
    page: int = 1,
    page_size: int = 10,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    调用 /cpws_al_api/api/cpwsAl/search 拿一页搜索结果。
    """
    payload = build_search_payload(keyword, page=page, size=page_size)
    print(f"请求搜索接口，第 {page} 页，payload:")
    print(payload)

    resp = session.post(
        SEARCH_API_URL,
        json=payload,
        timeout=15,
    )
    print("  状态码：", resp.status_code)

    if debug:
        print("  响应前 500 字符：")
        print(resp.text[:500])

    if resp.status_code != 200:
        print("  ⚠ 非 200 状态码，响应前 500 字符：")
        print(resp.text[:500])
        resp.raise_for_status()

    ctype = resp.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        print("  ⚠ 返回的不是 JSON，前 500 字符：")
        print(resp.text[:500])
        return {}

    data = resp.json()
    if debug:
        print("  JSON data:", json.dumps(data, ensure_ascii=False)[:1000])
    return data


# ----------------- 搜索主逻辑 -----------------

def search_contracts(
    session: requests.Session,
    keyword: str,
    max_pages: int = 1,
    page_size: int = 10,
    debug: bool = False,
    delay: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    按关键字搜索案例，返回记录列表：
      [{"id": "...", "title": "...", "brief": "...", "meta": {...}}, ...]
    """

    all_items: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        print(f"\n==== 搜索关键字：{keyword}，第 {page} 页 ====")
        data = fetch_search_page(
            session,
            keyword,
            page=page,
            page_size=page_size,
            debug=debug,
        )
        if not data:
            print("  ⚠ 本页无数据，提前结束。")
            break

        # 结构：
        # {
        #   "msg": "...",
        #   "code": 0,
        #   "data": {
        #       "totalCount": 1937,
        #       "datas": [ {...}, {...}, ... ]
        #   }
        # }
        inner = data.get("data") or {}
        rows = inner.get("datas") or []
        total = inner.get("totalCount")

        print(f"  当前页记录数：{len(rows)}，totalCount：{total}")

        if not rows:
            break

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                if debug:
                    print(f"  ⚠ 第 {idx} 条记录不是 dict：{row}")
                continue

            cid = row.get("id") or row.get("cpws_al_id")
            if not cid:
                if debug:
                    print(f"  ⚠ 第 {idx} 条记录没有 id：{row}")
                continue

            # 标题在 cpws_al_title，有 <em> 标签
            title_html = row.get("cpws_al_title", "") or ""
            title = html_to_text(title_html) or cid

            # 裁判要旨：cpws_al_cpyz，也是 HTML
            brief_html = row.get("cpws_al_cpyz", "") or ""
            brief = html_to_text(brief_html)

            if debug:
                print(f"  ✅ 第 {idx} 条记录：id = {cid}, title = {title}")

            all_items.append({
                "id": str(cid),
                "title": title,   # <- 用 cpws_al_title 转成的纯文本
                "brief": brief,
                "meta": row,
            })

        # 接口没有明确 totalPage，这里只按 max_pages 控制
        time.sleep(delay)

    print(f"\n搜索结果总数（去重前）：{len(all_items)}")
    uniq: Dict[str, Dict[str, Any]] = {}
    for it in all_items:
        cid = it["id"]
        if cid not in uniq:
            uniq[cid] = it
    result = list(uniq.values())
    print(f"去重后：{len(result)} 条")
    return result


# ----------------- 解析 /View 页面 -----------------

def parse_view_page(html: str) -> Dict[str, Any]:
    """
    解析 /view/content.html?id=... 页面，提取标题、案号等信息。
    """
    soup = BeautifulSoup(html, "html.parser")
    res: Dict[str, Any] = {
        "title": "",
        "code": "",
    }

    # 1) 标题：优先 h1/h2，失败再用 <title>
    h = soup.find(["h1", "h2"])
    if h:
        res["title"] = h.get_text(strip=True)

    if not res["title"]:
        title_tag = soup.find("title")
        if title_tag:
            res["title"] = title_tag.get_text(strip=True).split(" - ")[0]

    # 2) 案号 / 编号：示例正则，可根据实际页面内容调整
    full_text = soup.get_text("\n", strip=True)
    m = re.search(r"案号[:：]?\s*（?\(?\d{4}\)?）?.{0,30}号", full_text)
    if m:
        res["code"] = m.group(0).replace(" ", "")

    return res


# ----------------- 下载 PDF -----------------

def download_pdf_for_contract(
    session: requests.Session,
    encoded_id: str,
    title: str,
    code: str,
    save_dir: str,
    auto_txt: bool = True,
) -> Dict[str, Any]:
    """
    下载 PDF 文书（/cpwsAl/contentDownload?id=...），并可选导出 txt。

    注意：
      - search 返回的 id 已经是一次 URL 编码（含 %2F, %3D）；
      - contentDownload 的 URL 里需要“只编码一次”的版本；
      - requests 在组装 params 时会对参数再次进行 URL 编码，
        所以这里需要先用 unquote() 解码，再交给 params，让它重新编码一次。
    """
    raw_id = unquote(encoded_id)  # 先解码成原始字符串
    print(f"  尝试下载 PDF 文书：{PDF_DOWNLOAD_URL}?id={encoded_id}")

    try:
        r = session.get(PDF_DOWNLOAD_URL, params={"id": raw_id}, timeout=60)
        print("    状态码：", r.status_code)
        if r.status_code != 200 or not r.content:
            print("    ⚠ 未成功下载 PDF，跳过。")
            return {"type": "pdf", "path": "", "txt_path": ""}
    except Exception as e:
        print("    ❌ 请求失败：", e)
        return {"type": "pdf", "path": "", "txt_path": ""}

    # 文件名直接用传进来的 title（优先 cpws_al_title），附加案号更利于区分
    if code:
        base_name = f"{code}_{title}"
    else:
        base_name = title

    filename = safe_filename(base_name) + ".pdf"
    out_path = os.path.join(save_dir, filename)

    try:
        with open(out_path, "wb") as f:
            f.write(r.content)
        print("    ✅ 已保存 PDF：", out_path)
    except Exception as e:
        print("    ❌ 保存 PDF 失败：", e)
        return {"type": "pdf", "path": "", "txt_path": ""}

    txt_path = ""
    if auto_txt:
        txt_path = os.path.splitext(out_path)[0] + ".txt"
        try:
            pdf_to_txt(out_path, txt_path)
            print("    ✅ 已导出 TXT：", txt_path)
        except Exception as e:
            print("    ⚠ TXT 导出失败：", e)
            txt_path = ""

    return {"type": "pdf", "path": out_path, "txt_path": txt_path}


def download_for_contract(
    session: requests.Session,
    encoded_id: str,
    save_dir: str,
    auto_txt: bool = True,
    preset_title: str = "",
) -> Dict[str, Any]:
    """
    根据案例 id 抓取详情页，并下载 PDF 文书。

    encoded_id: search 返回的 id（已 URL 编码，如 bEWKpC...%2F...%3D）
    preset_title: 优先使用的标题（一般是搜索结果里的 cpws_al_title）

    返回结构：
      {
        "id": <encoded_id>,
        "title": <标题>,
        "code": <案号或空串>,
        "files": [...]
      }
    """
    # 详情页示例：
    # https://rmfyalk.court.gov.cn/view/content.html?id=bEWKpCPsHgwg4a9%252FN4sfaYhgXlUukPninqvENCvDrEk%253D&lib=ck&qw=合同
    double_encoded_id = quote(encoded_id, safe="")  # 再编码一次 -> %25 + ...
    view_url = (
        f"{BASE_URL}{CONTENT_VIEW_PATH}"
        f"?id={double_encoded_id}"
        f"&lib=ck"
    )
    print(f"\n--- 抓取案例详情：{view_url} ---")

    page_title = ""
    code = ""

    try:
        resp = session.get(view_url, timeout=20)
        print("  详情页状态码：", resp.status_code)
        resp.raise_for_status()
        info = parse_view_page(resp.text)
        page_title = info.get("title") or ""
        code = info.get("code") or ""
    except Exception as e:
        print("  ⚠ 获取详情页或解析失败：", e)

    # 标题优先用 preset_title（即 cpws_al_title 的纯文本）
    title = preset_title or page_title or encoded_id

    print(f"  标题：{title}")
    if code:
        print(f"  案号：{code}")

    pdf_info = download_pdf_for_contract(
        session=session,
        encoded_id=encoded_id,
        title=title,
        code=code,
        save_dir=save_dir,
        auto_txt=auto_txt,
    )

    files: List[Dict[str, Any]] = []
    if pdf_info.get("path"):
        files.append(pdf_info)

    if not files:
        print("  ⚠ 未能成功下载任何 PDF 文档。")

    return {
        "id": encoded_id,
        "title": title,
        "code": code,
        "files": files,
    }


# ----------------- 对外主接口 -----------------

def crawl_cases(
    keyword: Optional[str] = None,
    ids: Optional[List[str]] = None,
    max_pages: int = 1,
    save_dir: str = "",
    auto_txt: bool = True,
    token: str = "",
    page_size: int = 10,
    debug: bool = False,
    max_items: int = 0,
    search_delay: float = 2.0,
    download_delay: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    主入口函数：按关键字搜索 / 或 按给定 id 列表抓取案例。

    - 关键点：内部维护 tasks_map: { id -> title }，
      搜索得到的 title 来自 cpws_al_title，用作文件名。
    - max_items: 本次运行最多抓取多少个案例（0 表示不限制）。
    - search_delay: 每个搜索请求之间的间隔秒数。
    - download_delay: 每个案例详情+下载之间的间隔秒数。
    """
    if not save_dir:
        save_dir = "人民法院案例_下载"
    ensure_dir(save_dir)

    session = new_session(token=token)

    # id -> title
    tasks_map: Dict[str, str] = {}

    # 1) 如果显式给了 ids（只知道 id），先塞进去，标题为空
    if ids:
        for cid in ids:
            cid = cid.strip()
            if cid:
                tasks_map.setdefault(cid, "")

    # 2) 如果给了 keyword，则通过搜索接口拿 id + 标题（cpws_al_title）
    if keyword:
        search_items = search_contracts(
            session,
            keyword,
            max_pages=max_pages,
            page_size=page_size,
            debug=debug,
            delay=search_delay,
        )
        for it in search_items:
            cid = it["id"]
            title = it.get("title", "")
            # 如果之前没这个 id，或者之前是空标题，就更新为搜索得到的标题
            if cid not in tasks_map or not tasks_map[cid]:
                tasks_map[cid] = title

    contract_ids = list(tasks_map.keys())

    # 如果设置了最大抓取数量，则在这里截断
    if max_items and len(contract_ids) > max_items:
        print(f"\n⚠ 本次搜索共得到 {len(contract_ids)} 个案例，"
              f"根据 --max-items={max_items} 限制，本次只抓取前 {max_items} 个。")
        contract_ids = contract_ids[:max_items]

    print("\n待抓取案例数量：", len(contract_ids))
    if not contract_ids:
        print("⚠ 没有任何待抓取的案例 id。")
        return []

    results: List[Dict[str, Any]] = []
    for idx, cid in enumerate(contract_ids, 1):
        print(f"\n>>> 正在抓取第 {idx}/{len(contract_ids)} 个案例 ...")
        preset_title = tasks_map.get(cid, "")
        info = download_for_contract(
            session=session,
            encoded_id=cid,
            save_dir=save_dir,
            auto_txt=auto_txt,
            preset_title=preset_title,  # 把 cpws_al_title 透传下去
        )
        results.append(info)

        if(len(results)>2):
            break

        time.sleep(download_delay)

    return results


# ----------------- 命令行入口 -----------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="从人民法院案例库按 id 或关键字抓取案例（搜索 + 详情 + PDF + txt）。"
    )
    parser.add_argument(
        "-k", "--keyword",
        default="",
        help="搜索关键词，例如：合同纠纷、买卖合同纠纷等"
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=1,
        help="搜索结果翻页数上限，仅在 -k / --keyword 模式下生效（默认：1）"
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=5,
        help="每页条数（默认：5，建议不要太大）"
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5,
        help="本次最多抓取的案例数量上限（默认：5，0 表示不限制）"
    )
    parser.add_argument(
        "--ids",
        default="",
        help="直接指定要抓取的案例 id（用 search 返回的 id），逗号分隔"
    )
    parser.add_argument(
        "--save-dir",
        default="",
        help="保存目录，默认：人民法院案例_下载"
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="不要自动从 PDF 导出 txt"
    )
    parser.add_argument(
        "--token",
        default="",
        help="必填：faxin-cpws-al-token，在浏览器 F12 抓包 cpwsAl/search 请求时复制"
    )
    parser.add_argument(
        "--sleep-search",
        type=float,
        default=10.0,
        help="每次搜索请求之间的等待秒数（默认：5.0）"
    )
    parser.add_argument(
        "--sleep-download",
        type=float,
        default=10.0,
        help="每个案例详情+下载之间的等待秒数（默认：5.0）"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="打印调试信息（原始 JSON / row 等）"
    )
    return parser.parse_args()


def main_cli():
    args = parse_args()

    id_list: Optional[List[str]] = None
    if args.ids:
        id_list = [x.strip() for x in args.ids.split(",") if x.strip()]

    if not args.token:
        print("⚠ 未提供 --token，调用接口很可能 400/401，请从浏览器 F12 中复制 faxin-cpws-al-token。")

    results = crawl_cases(
        keyword=args.keyword or None,
        ids=id_list,
        max_pages=args.max_pages,
        save_dir=args.save_dir,
        auto_txt=not args.no_txt,
        token=args.token,
        page_size=args.page_size,
        debug=args.debug,
        max_items=args.max_items,
        search_delay=args.sleep_search,
        download_delay=args.sleep_download,
    )

    print("\n=== 抓取完成，结果摘要 ===")
    for r in results:
        print(f"- [{r['id']}] 《{r['title']}》 案号：{r.get('code','')}")
        if not r.get("files"):
            print("    （未抓到任何 PDF 附件）")
        for f in r.get("files", []):
            print(f"    [{f['type']}] {f['path']}")
            if f.get("txt_path"):
                print(f"        txt: {f['txt_path']}")


if __name__ == "__main__":
    main_cli()
