# flk_crawler.py
# -*- coding: utf-8 -*-
"""
国家法律法规数据库（https://flk.npc.gov.cn）法规抓取工具

功能：
  - 按关键词搜索法规（如：公司法 / 民法典 / 证券法 等）；
  - 通过 download/pc 接口获取带签名的下载链接；
  - 下载 docx / pdf 等文件；
  - 对 docx 自动导出为 txt 文本；
  - 既可以作为命令行工具使用，也可以作为库被其他 Python 代码调用。

使用示例（命令行）：
  python flk_crawler.py -k 公司法
  python flk_crawler.py -k 民法典 -p 5
  python flk_crawler.py -k 证券法 --no-filter

新增：
  - 支持配置“每条记录下载后的休眠时间”，默认 10 秒：
    --sleep-seconds 5   # 每条记录间隔 5 秒
"""

import os
import re
import json
import time
import argparse
from datetime import datetime
from typing import Any, List, Tuple, Dict

import requests
from docx import Document  # pip install python-docx

# ----------------- 常量配置 -----------------

SEARCH_URL = "https://flk.npc.gov.cn/law-search/search/list"
DOWNLOAD_INFO_URL = "https://flk.npc.gov.cn/law-search/download/pc"

# 默认排除词，用于“本体”过滤
DEFAULT_EXCLUDE_WORDS = [
    "若干问题",
    "若干规定",
    "解释",
    "时间效力",
    "实施",
    "适用",
    "注册资本登记管理制度",
    "批复",
    "细则",
]

# 如需全局写死 Cookie
COOKIE_STR = ""


# ----------------- 工具函数 -----------------

def ensure_dir(path: str) -> None:
    """确保目录存在。"""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def strip_html(s: str) -> str:
    """去掉 HTML 标签。"""
    if not s:
        return ""
    return re.sub(r"<.*?>", "", s)


def safe_filename(name: str) -> str:
    """将任意标题转换为适合作为文件名的字符串。"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = name.strip()
    return name or "unnamed"


def is_main_body(title_plain: str, keyword: str, exclude_words: List[str]) -> bool:
    """
    判断是否为“本体版本”：
      1. 标题中必须包含关键词；
      2. 不包含排除词。
    """
    if keyword not in title_plain:
        return False
    return not any(w in title_plain for w in exclude_words)


def docx_to_txt(docx_path: str, txt_path: str) -> None:
    """将 docx 内容导出为 txt 文本（utf-8）。"""
    doc = Document(docx_path)
    lines: List[str] = []

    for p in doc.paragraphs:
        text = p.text.replace("\r", "").rstrip()
        lines.append(text)

    # 如想包含表格，可自行加上 table 遍历
    content = "\n".join(lines)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_date(date_str: str) -> datetime:
    """将 'YYYY-MM-DD' 格式的日期解析为 datetime，用于比较新旧。"""
    if not date_str:
        return datetime.min
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return datetime.min


def normalize_title_for_versioning(title: str) -> str:
    """
    归一化标题用于“同名法规”的版本判断：
      - 去掉全角/半角括号中的内容（通常是“某年修正”等版本信息）；
      - 去掉首尾空白。
    例如：
      '中华人民共和国公司法（2018年修正）' -> '中华人民共和国公司法'
    """
    # 去掉中文 / 英文括号中的内容
    title_no_paren = re.sub(r"[（(][^（）()]*[）)]", "", title)
    return title_no_paren.strip()


# ----------------- Session & 搜索 -----------------

def new_session(cookie: str = "") -> requests.Session:
    """
    创建一个带通用 Header 的 Session，并预热访问一次 /search。
    可以通过参数 cookie 或环境变量 FLK_COOKIE 传入 Cookie。
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7,zh-TW;q=0.6,ko;q=0.5",
        "Origin": "https://flk.npc.gov.cn",
        "Referer": "https://flk.npc.gov.cn/search",
        "Content-Type": "application/json;charset=UTF-8",
        "Connection": "keep-alive",
    })

    cookie_from_env = os.environ.get("FLK_COOKIE", "")
    cookie_final = cookie or COOKIE_STR or cookie_from_env
    if cookie_final:
        s.headers["Cookie"] = cookie_final

    try:
        r = s.get("https://flk.npc.gov.cn/search", timeout=10)
        print("预热 /search 状态码：", r.status_code)
        print("预热后 Cookie：", s.cookies.get_dict())
    except Exception as e:
        print("预热 /search 失败：", e)

    return s


def make_payload(keyword: str, page_num: int) -> dict:
    """构造搜索接口 payload。"""
    return {
        "searchRange": 1,
        "sxrq": [],
        "gbrq": [],
        "sxx": [],
        "searchType": 2,
        "xgzlSearch": False,
        "searchContent": keyword,
        "flfgCodeId": [],
        "gbrqYear": [],
        "orderByParam": {"order": "-1", "sort": ""},
        "pageNum": page_num,
        "pageSize": 20,
        "zdjgCodeId": [],
    }


def fetch_search_page(session: requests.Session, keyword: str, page_num: int) -> List[Dict[str, Any]]:
    """调用 search/list 拿一页搜索结果。"""
    payload = make_payload(keyword, page_num)
    resp = session.post(
        SEARCH_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=15,
    )
    print(f"第 {page_num} 页状态码：", resp.status_code,
          "| Content-Type:", resp.headers.get("Content-Type"))
    resp.raise_for_status()

    ctype = resp.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        print("⚠ search/list 返回的不是 JSON，前 300 字符：")
        print(resp.text[:300])
        return []

    data = resp.json()
    rows = data.get("rows") or data.get("result", {}).get("rows") or []
    print("  本页 rows 数量：", len(rows))
    if rows:
        print("  第一条原始记录预览：",
              json.dumps(rows[0], ensure_ascii=False)[:200])
    return rows


def collect_main_body_laws(
    session: requests.Session,
    keyword: str,
    max_pages: int,
    exclude_words: List[str],
    no_filter: bool = False,
) -> List[Dict[str, Any]]:
    """
    从搜索结果中收集记录。
    - 如果 no_filter=True，则不做“本体”筛选，所有结果都会返回；
    - 否则按 is_main_body() 过滤。
    """
    all_items: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        print(f"\n==== 抓取搜索结果第 {page} 页 ====")
        rows = fetch_search_page(session, keyword, page)
        if not rows:
            print("  没抓到任何条目（可能被反爬或结构变了），先停。")
            break

        for row in rows:
            raw_title = row.get("title", "")
            title_plain = strip_html(raw_title)
            gbrq = row.get("gbrq") or row.get("f_bbrq") or ""
            law_id = row.get("bbbs")

            if not law_id:
                print("  ⚠ 记录没有 bbbs 字段，跳过：", title_plain)
                continue

            item = {"id": law_id, "title": title_plain, "gbrq": gbrq}

            if no_filter:
                print("  ✅ 收录（不做本体筛选）：", title_plain,
                      "| 公布日期：", gbrq,
                      "| bbbs:", law_id)
                all_items.append(item)
            else:
                if is_main_body(title_plain, keyword, exclude_words):
                    print("  ✅ 本体候选：", title_plain,
                          "| 公布日期：", gbrq,
                          "| bbbs:", law_id)
                    all_items.append(item)
                else:
                    print("  · 非本体，跳过：", title_plain)

        # 页面之间的轻微节流
        time.sleep(1.0)

    print(f"\n总共收集到候选记录：{len(all_items)} 条。")
    return all_items


# ----------------- 在 JSON 中找附件 URL -----------------

DOC_PATTERN = re.compile(
    r"\.(doc|docx|wps|pdf)(?:[\?#].*)?$",
    re.IGNORECASE
)


def collect_doc_like_strings(node: Any,
                             path: List[str] = None) -> List[Tuple[List[str], str]]:
    """
    递归遍历 JSON，收集所有看起来像 doc/docx/wps/pdf 链接的字符串。
    返回列表 [([key_path...], value_str), ...]
    """
    if path is None:
        path = []

    results: List[Tuple[List[str], str]] = []

    if isinstance(node, dict):
        for k, v in node.items():
            new_path = path + [str(k)]
            results.extend(collect_doc_like_strings(v, new_path))
    elif isinstance(node, list):
        for idx, v in enumerate(node):
            new_path = path + [f"[{idx}]"]
            results.extend(collect_doc_like_strings(v, new_path))
    elif isinstance(node, str):
        if DOC_PATTERN.search(node) and "http" in node:
            results.append((path, node))

    return results


def score_path(path_keys: List[str]) -> int:
    """根据 key 路径给候选链接打分，越像“正文附件”分越高。"""
    path_str = "/".join(path_keys).lower()
    score = 0
    if any(kw in path_str for kw in ["word", "wps", "doc"]):
        score += 3
    if any(kw in path_str for kw in ["ossfile", "file", "attach", "附件"]):
        score += 2
    if any(kw in path_str for kw in ["url", "path", "link"]):
        score += 1
    return score


def is_internal_url(u: str) -> bool:
    """判断是否是内网地址。"""
    u = u.lower()
    return (
        u.startswith("http://172.") or
        u.startswith("http://10.") or
        u.startswith("http://192.168.") or
        u.startswith("http://127.") or
        "localhost" in u
    )


def is_https(u: str) -> bool:
    return u.startswith("https://")


# ----------------- 下载单条记录 -----------------

def download_body_for_item(
    session: requests.Session,
    item: Dict[str, Any],
    save_dir: str,
    auto_txt: bool = True,
) -> Dict[str, str]:
    """
    为单条记录下载正文附件。
    返回：
      {
        "doc_path": <docx/pdf 文件路径> 或 "",
        "txt_path": <txt 路径，如果 auto_txt=False 或非 docx，则可能为空字符串>
      }
    """
    law_id = item["id"]
    title = item["title"]
    gbrq = item["gbrq"]

    print(f"\n--- download：《{title}》（bbbs={law_id}） ---")

    headers = session.headers.copy()
    headers.pop("Content-Type", None)
    headers["Referer"] = (
        f"https://flk.npc.gov.cn/detail?id={law_id}&fileId=&type=&title="
    )

    resp = session.get(
        DOWNLOAD_INFO_URL,
        params={"format": "docx", "bbbs": law_id},
        headers=headers,
        timeout=15,
    )
    print("  download/pc 状态码：", resp.status_code,
          "| Content-Type:", resp.headers.get("Content-Type"))
    resp.raise_for_status()

    ctype = resp.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        print("  ⚠ download/pc 返回的不是 JSON，前 300 字符：")
        print(resp.text[:300])
        return {"doc_path": "", "txt_path": ""}

    data = resp.json()
    root = data.get("result") if isinstance(data, dict) and "result" in data else data

    candidates = collect_doc_like_strings(root)
    if not candidates:
        print("  ⚠ 在 JSON 中没有发现任何 .doc/.pdf/.wps 链接，"
              "先把 JSON 存下来方便排查。")
        debug_name = safe_filename(f"{gbrq}_{title}_download_info.json")
        debug_path = os.path.join(save_dir, debug_name)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("  已保存 download_info JSON：", debug_path)
        return {"doc_path": "", "txt_path": ""}

    print(f"  在 JSON 中共发现疑似附件链接 {len(candidates)} 条：")
    for p, v in candidates:
        print("    ·", "/".join(p), "=>", v)

    scored: List[Tuple[int, int, int, int, List[str], str]] = []
    for path_keys, val in candidates:
        url_val = val.strip()
        base_score = score_path(path_keys)
        internal_flag = 1 if is_internal_url(url_val) else 0
        https_flag = 1 if is_https(url_val) else 0
        scored.append((
            internal_flag,
            -https_flag,
            -base_score,
            len(path_keys),
            path_keys,
            url_val,
        ))

    scored.sort()
    best_internal, best_https_neg, best_neg_score, _, best_path_keys, best_val = scored[0]
    print("  选中的最佳候选：", "/".join(best_path_keys), "=>", best_val,
          "| internal =", best_internal,
          "| https =", is_https(best_val))

    url = best_val
    if url.startswith('"') and url.endswith('"'):
        url = url[1:-1]

    base_for_ext = url.split("?", 1)[0]
    ext = os.path.splitext(base_for_ext)[1] or ".docx"
    fname = safe_filename(f"{gbrq}_{title}{ext}")
    out_path = os.path.join(save_dir, fname)

    print("  实际下载 URL：", url)
    print("  保存文件名：", fname)

    try:
        r = session.get(url, timeout=60)
        print("  下载响应状态码：", r.status_code)
        r.raise_for_status()
    except requests.RequestException as e:
        print("  ❌ 下载失败：", e)
        return {"doc_path": "", "txt_path": ""}

    with open(out_path, "wb") as f:
        f.write(r.content)
    print("  ✅ 下载完成：", out_path)

    txt_path = ""
    if auto_txt and ext.lower() == ".docx":
        txt_path = os.path.splitext(out_path)[0] + ".txt"
        try:
            docx_to_txt(out_path, txt_path)
            print("  ✅ 已导出 TXT：", txt_path)
        except Exception as e:
            print("  ⚠ 转换 TXT 失败：", e)
            txt_path = ""

    return {"doc_path": out_path, "txt_path": txt_path}


# ----------------- 对外主接口（供别人 import 调用） -----------------

def crawl_laws(
    keyword: str,
    max_pages: int = 3,
    save_dir: str = "",
    exclude_words: List[str] = None,
    no_filter: bool = False,
    cookie: str = "",
    auto_txt: bool = True,
    latest_only: bool = True,
    sleep_seconds: float = 10.0,
) -> List[Dict[str, str]]:
    """
    对外主入口函数：抓取指定关键词的法规正文，并返回下载结果列表。

    参数：
      keyword      : 搜索关键词，如 "公司法" / "民法典" / "证券法"
      max_pages    : 搜索结果翻页数上限，默认 3
      save_dir     : 保存目录，默认 "<keyword>_本体_flk"
      exclude_words: 本体过滤时的排除词列表，默认使用 DEFAULT_EXCLUDE_WORDS
      no_filter    : 如果 True，则不做“本体”过滤，搜索结果全部下载
      cookie       : 可选 Cookie 字符串（否则使用 COOKIE_STR 或环境变量 FLK_COOKIE）
      auto_txt     : 是否对 docx 自动导出 txt，默认 True
      latest_only  : 是否只保留“同名法规”的最新版本（按标题归一化+公布日期比较），默认 True
      sleep_seconds: 每条记录下载之间的休眠秒数，默认 10 秒

    返回：
      列表，每个元素为：
        {
          "id":    <bbbs>,
          "title": <标题>,
          "gbrq":  <公布日期>,
          "doc_path": <下载到的 docx/pdf 路径或空字符串>,
          "txt_path": <生成的 txt 路径或空字符串>,
        }
    """
    if not save_dir:
        save_dir = safe_filename(f"{keyword}_本体_flk")
    ensure_dir(save_dir)

    if exclude_words is None:
        exclude_words = list(DEFAULT_EXCLUDE_WORDS)

    print(f"关键词：{keyword}")
    print(f"最大翻页数：{max_pages}")
    print(f"是否做本体过滤：{not no_filter}")
    print(f"排除词：{exclude_words}")
    print(f"是否只保留最新版本：{latest_only}")
    print(f"保存目录：{save_dir}")
    print(f"每条记录下载后的休眠秒数：{sleep_seconds}")

    session = new_session(cookie=cookie)

    # 1. 搜索 & 收集记录
    items = collect_main_body_laws(
        session=session,
        keyword=keyword,
        max_pages=max_pages,
        exclude_words=exclude_words,
        no_filter=no_filter,
    )

    # 1.5 根据 latest_only 做“同名法规只保留最新版本”的过滤
    if items and latest_only:
        latest_map: Dict[str, Dict[str, Any]] = {}
        for it in items:
            title_key = normalize_title_for_versioning(it["title"])
            dt = parse_date(it.get("gbrq", ""))
            if title_key not in latest_map:
                latest_map[title_key] = it
            else:
                old = latest_map[title_key]
                if parse_date(old.get("gbrq", "")) < dt:
                    latest_map[title_key] = it
        filtered_items = list(latest_map.values())
        print(f"按标题归一化后，{len(items)} 条候选中保留最新版本 {len(filtered_items)} 条。")
        items = filtered_items

    # 保存清单 JSON（是最终准备用于下载的列表）
    list_path = os.path.join(save_dir, f"{keyword}_本体清单_flk.json")
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("\n已将清单保存到：", list_path)

    if not items:
        print("⚠ 没有任何候选，结束。")
        return []

    # 2. 逐条下载正文
    results: List[Dict[str, str]] = []
    success = 0
    for idx, item in enumerate(items, start=1):
        print(f"\n=== 正在处理第 {idx}/{len(items)} 条记录 ===")
        paths = download_body_for_item(
            session=session,
            item=item,
            save_dir=save_dir,
            auto_txt=auto_txt,
        )
        merged = {
            "id": item["id"],
            "title": item["title"],
            "gbrq": item["gbrq"],
            "doc_path": paths.get("doc_path", ""),
            "txt_path": paths.get("txt_path", ""),
        }
        if merged["doc_path"]:
            success += 1
        results.append(merged)

        # 每条记录下载之后休眠 sleep_seconds 秒（默认 10 秒）
        print(f"  -> 本条记录处理完毕，休眠 {sleep_seconds} 秒以防被反爬...")
        time.sleep(sleep_seconds)

    print(f"\n共 {len(items)} 条待下载记录，成功下载 {success} 条。")
    print("保存目录：", os.path.abspath(save_dir))

    return results


# ----------------- 命令行入口 -----------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="从国家法律法规数据库按关键词抓取法规本体（docx+txt）。"
    )
    parser.add_argument(
        "-k", "--keyword",
        default="公司法",
        help="搜索关键词，例如：公司法、民法典、证券法（默认：公司法）"
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=3,
        help="搜索结果翻页数上限（默认：3）"
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="用于排除“非本体”的词，逗号分隔，例如：若干问题,解释,批复"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="不做本体筛选，搜索结果中的所有记录都下载"
    )
    parser.add_argument(
        "--save-dir",
        default="",
        help="保存目录，默认：<keyword>_本体_flk"
    )
    parser.add_argument(
        "--cookie",
        default="",
        help="可选 Cookie 字符串（否则使用环境变量 FLK_COOKIE 或源码中的 COOKIE_STR）"
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="不要自动从 docx 导出 txt"
    )
    parser.add_argument(
        "--all-versions",
        action="store_true",
        help="下载所有匹配版本（默认只保留同名法规的最新公布日期版本）"
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=10.0,
        help="每条记录下载之间的休眠秒数，默认 10 秒"
    )
    return parser.parse_args()


def main_cli():
    args = parse_args()

    exclude_words = list(DEFAULT_EXCLUDE_WORDS)
    if args.exclude:
        extra = [w.strip() for w in args.exclude.split(",") if w.strip()]
        exclude_words.extend(extra)

    results = crawl_laws(
        keyword=args.keyword,
        max_pages=args.max_pages,
        save_dir=args.save_dir,
        exclude_words=exclude_words,
        no_filter=args.no_filter,
        cookie=args.cookie,
        auto_txt=not args.no_txt,
        latest_only=not args.all_versions,
        sleep_seconds=args.sleep_seconds,
    )

    # 输出一下结果
    print("\n=== 抓取完成，结果摘要 ===")
    for r in results:
        print(f"- {r['gbrq']}《{r['title']}》")
        print(f"    doc: {r['doc_path'] or '（未成功下载）'}")
        if r["txt_path"]:
            print(f"    txt: {r['txt_path']}")
        else:
            print("    txt: （未生成或非 docx）")


if __name__ == "__main__":
    main_cli()
