# -*- coding: utf-8 -*-
"""
合同示范文本库（https://htsfwb.samr.gov.cn/）合同范文抓取工具

功能：
  - 按关键词搜索示范合同（调用 /api/content/SearchTemplates 接口），获取合同 id 列表；
  - 访问 /View?id=... 详情页，解析标题 / 合同编号；
  - 调用 /api/File/DownTemplate?id=...&type=2 下载 PDF 文档；
  - 使用 pdfplumber 将 PDF 导出为 txt 文本；
  - 既可以作为命令行工具使用，也可以作为库被其他 Python 代码调用。

使用示例（命令行）：
  # 按关键词搜索并下载 PDF+TXT
  python htsfw_crawler.py -k 买卖 -p 2

  # 直接按 id 下载
  python htsfw_crawler.py --ids 5e068390-d87c-4ea5-aa83-18a8ed36e3ae

依赖：
  pip install requests beautifulsoup4 pdfplumber
"""

import os
import re
import time
import argparse
from typing import Any, List, Dict, Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4
import pdfplumber              # pip install pdfplumber

# ----------------- 常量配置 -----------------

BASE_URL = "https://htsfwb.samr.gov.cn"

# 搜索合同示范文本接口：
#   GET /api/content/SearchTemplates?key=买卖&loc=true&p=1
SEARCH_API_URL = BASE_URL + "/api/content/SearchTemplates"


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


def pdf_to_txt(pdf_path: str, txt_path: str) -> None:
    """使用 pdfplumber 将 PDF 内容导出为 txt 文本（utf-8）。"""
    texts: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text.strip())
    content = "\n\n".join(texts)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)


# ----------------- Session -----------------

def new_session() -> requests.Session:
    """创建一个带通用 Header 的 Session。"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Referer": BASE_URL + "/",
    })
    return s


# ----------------- 搜索 -----------------

def fetch_search_page(
    session: requests.Session,
    keyword: str,
    page: int = 1,
    loc: bool = True,
) -> Dict[str, Any]:
    """
    调用 /api/content/SearchTemplates 拿一页搜索结果。

    示例：
      GET https://htsfwb.samr.gov.cn/api/content/SearchTemplates?key=买卖&loc=true&p=1
    """
    params = {
        "key": keyword,
        "loc": "true" if loc else "false",
        "p": page,
    }
    print(f"请求搜索接口，第 {page} 页：", params)

    headers = {
        "Referer": f"{BASE_URL}/List?key={quote(keyword)}",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }

    resp = session.get(
        SEARCH_API_URL,
        params=params,
        headers=headers,
        timeout=15,
    )
    print("  状态码：", resp.status_code)
    resp.raise_for_status()

    ctype = resp.headers.get("Content-Type", "")
    if "application/json" not in ctype:
        print("  ⚠ SearchTemplates 返回的不是 JSON，前 200 字符：")
        print(resp.text[:200])
        return {}

    data = resp.json()
    return data


def search_contracts(
    session: requests.Session,
    keyword: str,
    max_pages: int = 1,
    loc: bool = True,
) -> List[Dict[str, Any]]:
    """
    按关键字搜索合同示范文本，返回记录列表：
      [{"id": "...", "title": "...", "brief": "...", "meta": {...}}, ...]
    """
    all_items: List[Dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        print(f"\n==== 搜索关键字：{keyword}，第 {page} 页 ====")
        data = fetch_search_page(session, keyword, page=page, loc=loc)
        if not data:
            print("  ⚠ 本页无数据，提前结束。")
            break

        rows = data.get("Data") or []
        total = data.get("Total")
        total_page = data.get("TotalPage") or data.get("TotalPages") or None
        print(f"  当前页记录数：{len(rows)}，总数：{total}，总页数：{total_page}")

        if not rows:
            break

        for row in rows:
            cid = row.get("Id") or row.get("id")
            title = row.get("Title") or row.get("title") or ""
            brief = row.get("Brief") or row.get("brief") or ""
            if not cid:
                continue
            all_items.append({
                "id": cid,
                "title": title.strip(),
                "brief": brief.strip(),
                "meta": row,
            })

        if total_page is not None and page >= int(total_page):
            break

        time.sleep(1.0)

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
    解析 /View?id=... 页面，提取标题、合同编号（如果能抓到）。
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

    # 2) 合同编号：比如 "GF—2000—0104" / "SF-2020-0102"
    full_text = soup.get_text("\n", strip=True)
    m = re.search(r"(GF|SF)[—\-]\s*\d{4}[—\-]\d+", full_text)
    if m:
        res["code"] = m.group(0).replace(" ", "")

    return res


# ----------------- 下载 PDF -----------------

def download_pdf_for_contract(
    session: requests.Session,
    contract_id: str,
    title: str,
    code: str,
    save_dir: str,
    auto_txt: bool = True,
) -> Dict[str, Any]:
    """
    下载 PDF（type=2），并尝试导出 txt。

    ✅ 文件名规则：
       有编号：<合同编号>_<标题>.pdf
       无编号：<标题>.pdf

    返回：
      {"type": "pdf", "path": "xxx.pdf 或空串", "txt_path": "xxx.txt 或空串"}
    """
    url = f"{BASE_URL}/api/File/DownTemplate?id={contract_id}&type=2"
    print(f"  尝试下载 PDF：{url}")

    try:
        r = session.get(url, timeout=60)
        print("    状态码：", r.status_code)
        if r.status_code != 200 or not r.content:
            print("    ⚠ 未成功下载 PDF，跳过。")
            return {"type": "pdf", "path": "", "txt_path": ""}
    except Exception as e:
        print("    ❌ 请求失败：", e)
        return {"type": "pdf", "path": "", "txt_path": ""}

    # 文件名：严格用 “编号+标题” 或 “标题”
    if code:
        base_name = f"{code}_{title}"
    else:
        base_name = title

    filename = safe_filename(base_name) + ".pdf"
    out_path = os.path.join(save_dir, filename)

    with open(out_path, "wb") as f:
        f.write(r.content)
    print("    ✅ 已保存 PDF：", out_path)

    txt_path = ""
    if auto_txt:
        txt_path = os.path.splitext(out_path)[0] + ".txt"
        try:
            pdf_to_txt(out_path, txt_path)
            print("    ✅ 已导出 TXT（pdf）：", txt_path)
        except Exception as e:
            print("    ⚠ TXT 导出失败（pdf）：", e)
            txt_path = ""

    return {"type": "pdf", "path": out_path, "txt_path": txt_path}


def download_for_contract(
    session: requests.Session,
    contract_id: str,
    save_dir: str,
    auto_txt: bool = True,
) -> Dict[str, Any]:
    """
    访问单个合同详情页 /View?id=...，
    下载 PDF，并可选导出 txt。

    返回结构：
      {
        "id": <contract_id>,
        "title": <标题>,
        "code": <合同编号或空串>,
        "files": [
            {"type": "pdf", "path": "xxx.pdf 或空串", "txt_path": "xxx.txt 或空串"},
        ]
      }
    """
    view_url = f"{BASE_URL}/View?id={contract_id}"
    print(f"\n--- 抓取合同详情：{view_url} ---")

    try:
        resp = session.get(view_url, timeout=20)
        print("  详情页状态码：", resp.status_code)
        resp.raise_for_status()
    except Exception as e:
        print("  ❌ 获取详情页失败：", e)
        return {
            "id": contract_id,
            "title": "",
            "code": "",
            "files": [],
        }

    info = parse_view_page(resp.text)
    title = info.get("title") or contract_id
    code = info.get("code") or ""

    print(f"  标题：{title}")
    if code:
        print(f"  合同编号：{code}")

    pdf_info = download_pdf_for_contract(
        session=session,
        contract_id=contract_id,
        title=title,
        code=code,
        save_dir=save_dir,
        auto_txt=auto_txt,
    )

    files: List[Dict[str, Any]] = []
    if pdf_info["path"]:
        files.append(pdf_info)

    if not files:
        print("  ⚠ 未能成功下载可用的 PDF 文档。")

    return {
        "id": contract_id,
        "title": title,
        "code": code,
        "files": files,
    }


# ----------------- 对外主接口 -----------------

def crawl_contracts(
    keyword: Optional[str] = None,
    ids: Optional[List[str]] = None,
    max_pages: int = 1,
    save_dir: str = "",
    auto_txt: bool = True,
) -> List[Dict[str, Any]]:
    """
    主入口函数：按关键字搜索 / 或 按给定 id 列表抓取合同范文。

    参数：
      keyword  : 搜索关键词（可选）；
      ids      : 明确的合同 id 列表（可选），形如 "5e068390-d87c-4ea5-aa83-18a8ed36e3ae"；
      max_pages: 搜索翻页数上限，仅在 keyword 模式下生效；
      save_dir : 保存目录，默认 "合同示范文本_下载"；
      auto_txt : 是否自动从 PDF 导出 txt。

    返回：
      每个元素结构参考 download_for_contract 的返回值。
    """
    if not save_dir:
        save_dir = "合同示范文本_下载"
    ensure_dir(save_dir)

    session = new_session()

    contract_ids: List[str] = []

    # 1) 如果显式给了 ids，就直接用 ids
    if ids:
        contract_ids.extend(ids)

    # 2) 如果给了 keyword，则通过搜索接口拿 id
    if keyword:
        search_items = search_contracts(session, keyword, max_pages=max_pages)
        for it in search_items:
            cid = it["id"]
            if cid not in contract_ids:
                contract_ids.append(cid)

    contract_ids = list(dict.fromkeys(contract_ids))  # 去重并保持顺序

    print("\n待抓取合同数量：", len(contract_ids))
    if not contract_ids:
        print("⚠ 没有任何待抓取的合同 id。")
        return []

    results: List[Dict[str, Any]] = []
    for cid in contract_ids:
        info = download_for_contract(
            session=session,
            contract_id=cid,
            save_dir=save_dir,
            auto_txt=auto_txt,
        )
        results.append(info)
        time.sleep(1.0)

    return results


# ----------------- 命令行入口 -----------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="从合同示范文本库按 id 或关键字抓取合同范文（PDF + txt）。"
    )
    parser.add_argument(
        "-k", "--keyword",
        default="",
        help="搜索关键词，例如：租赁、买卖、服务等"
    )
    parser.add_argument(
        "-p", "--max-pages",
        type=int,
        default=1,
        help="搜索结果翻页数上限，仅在 -k / --keyword 模式下生效（默认：1）"
    )
    parser.add_argument(
        "--ids",
        default="",
        help="直接指定要下载的合同 id，逗号分隔，例如：5e068390-d87c-4ea5-aa83-18a8ed36e3ae,273e0034-..."
    )
    parser.add_argument(
        "--save-dir",
        default="",
        help="保存目录，默认：合同示范文本_下载"
    )
    parser.add_argument(
        "--no-txt",
        action="store_true",
        help="不要自动从 PDF 导出 txt"
    )
    return parser.parse_args()


def main_cli():
    args = parse_args()

    id_list: Optional[List[str]] = None
    if args.ids:
        id_list = [x.strip() for x in args.ids.split(",") if x.strip()]

    results = crawl_contracts(
        keyword=args.keyword or None,
        ids=id_list,
        max_pages=args.max_pages,
        save_dir=args.save_dir,
        auto_txt=not args.no_txt,
    )

    print("\n=== 抓取完成，结果摘要 ===")
    for r in results:
        print(f"- [{r['id']}] 《{r['title']}》 编号：{r.get('code','')}")
        if not r["files"]:
            print("    （未抓到任何 PDF 附件）")
        for f in r["files"]:
            print(f"    [{f['type']}] {f['path']}")
            if f["txt_path"]:
                print(f"        txt: {f['txt_path']}")


if __name__ == "__main__":
    main_cli()
