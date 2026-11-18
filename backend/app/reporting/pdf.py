from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.reporting.domain import ReportRenderError, ReportSnapshot, ReportTooLargeError
from app.reporting.presentation import json_text, present, utc

ASSETS = Path(__file__).parent / "assets"
MAX_HTML_BYTES = 2_000_000
MAX_PDF_PAGES = 100


def report_asset(url: str) -> bytes:
    fonts = {
        "iphi-font:regular": "IBMPlexSans-Regular.ttf",
        "iphi-font:medium": "IBMPlexSans-Medium.ttf",
        "iphi-font:mono": "IBMPlexMono-Regular.ttf",
    }
    name = fonts.get(url)
    if name is None:
        raise ValueError("Report resource is not allowlisted.")
    return (ASSETS / name).read_bytes()


def report_html(snapshot: ReportSnapshot) -> str:
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=True,
        undefined=StrictUndefined,
    )
    environment.filters.update(utc=utc, json_text=json_text)
    html = environment.get_template("incident.html").render(view=present(snapshot))
    if len(html.encode()) > MAX_HTML_BYTES:
        raise ReportTooLargeError("The report exceeds the 2 MB content limit.")
    return html


class PdfRenderer:
    def pdf(self, snapshot: ReportSnapshot) -> bytes:
        # Lazy loading keeps non-PDF routes independent of the native rendering libraries.
        from weasyprint import HTML  # type: ignore[import-untyped]  # noqa: PLC0415
        from weasyprint.urls import (  # type: ignore[import-untyped]  # noqa: PLC0415
            FatalURLFetchingError,
            URLFetcher,
            URLFetcherResponse,
        )

        class AssetsOnly(URLFetcher):  # type: ignore[misc]
            def fetch(self, url: str, headers: object = None) -> object:
                return cast(
                    object,
                    URLFetcherResponse(
                        url, body=report_asset(url), headers={"Content-Type": "font/ttf"}
                    ),
                )

        try:
            document = HTML(
                string=report_html(snapshot), url_fetcher=AssetsOnly(fail_on_errors=True)
            ).render()
            if len(document.pages) > MAX_PDF_PAGES:
                raise ReportTooLargeError("The PDF exceeds the 100 page limit.")
            return cast(bytes, document.write_pdf(pdf_tags=True))
        except (FatalURLFetchingError, OSError, ValueError) as exc:
            raise ReportRenderError("The PDF could not be generated. Retry or export CSV.") from exc
