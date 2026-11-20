"""PDF 导出：用 Playwright 驱动浏览器把成书预览页打印成 PDF。

相比 WeasyPrint，这条路在 Windows 上不需要装 GTK3 运行时，
排版就是浏览器所见即所得，中文字体也不容易出问题。

浏览器选择策略（按优先级）：
1. 本机已安装的 Google Chrome（channel="chrome"），零下载；
2. 本机已安装的 Microsoft Edge（channel="msedge"），Windows 必备；
3. Playwright 自带 chromium（需要先执行 `python -m playwright install chromium`）。
"""

import logging
from pathlib import Path

from app.config import EXPORT_DIR, settings

logger = logging.getLogger(__name__)

CHANNELS = ("chrome", "msedge", None)


class PdfError(RuntimeError):
    pass


def _launch_browser(playwright):
    errors: list[str] = []
    for channel in CHANNELS:
        try:
            if channel:
                browser = playwright.chromium.launch(channel=channel)
                logger.info("PDF 导出使用本机浏览器：%s", channel)
                return browser
            browser = playwright.chromium.launch()
            logger.info("PDF 导出使用 Playwright 自带 chromium")
            return browser
        except Exception as exc:
            errors.append(f"{channel or 'bundled-chromium'}: {exc}".split("\n")[0])
            continue

    raise PdfError(
        "没有可用的浏览器。请任选其一："
        "① 安装 Google Chrome 或 Microsoft Edge；"
        "② 执行 `python -m playwright install chromium` 下载自带内核。"
        f"尝试记录：{'; '.join(errors)}"
    )


def export_book_pdf(token: str) -> Path:
    target = EXPORT_DIR / f"{token}.pdf"
    url = f"{settings.app_base_url.rstrip('/')}/book/{token}?print=1"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PdfError("未安装 playwright，请执行 pip install -r requirements.txt") from exc

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            try:
                page = browser.new_page(viewport={"width": 900, "height": 1200})
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.emulate_media(media="print")
                page.pdf(
                    path=str(target),
                    prefer_css_page_size=True,
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
            finally:
                browser.close()
    except PdfError:
        raise
    except Exception as exc:
        logger.warning("PDF 导出失败: %s", exc)
        raise PdfError(
            f"PDF 导出失败，请确认服务地址 {settings.app_base_url} 可访问。原始错误：{exc}"
        ) from exc

    if not target.exists():
        raise PdfError("PDF 生成失败：未产生文件")
    return target