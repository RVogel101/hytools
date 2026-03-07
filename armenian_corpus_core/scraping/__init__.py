"""Scraping sub-package.

Provides data acquisition from multiple Armenian sources:

- ``wikipedia``        — hyw / hy Wikipedia XML dump processing
- ``wikisource``       — Armenian Wikisource via MediaWiki API
- ``archive_org``      — Internet Archive DjVuTXT downloads
- ``newspaper``        — Aztag Daily, Horizon Weekly & Asbarez via Selenium
- ``nayiri``           — Nayiri.com dictionary scraping
- ``culturax``         — CulturaX HuggingFace dataset (Armenian subset)
- ``hathitrust``       — HathiTrust Digital Library
- ``loc``              — Library of Congress Armenian holdings
- ``eastern_armenian`` — Eastern Armenian Wikipedia + news agencies
- ``rss_news``         — 21 RSS news feeds (Armenian, diaspora, international)
- ``english_sources``  — English Wikipedia history, Hyestart, CSU Fresno
- ``mss_nkr``         — MSS NKR (mss.nkr.am) PDF and image downloads
- ``frequency_aggregator`` — merge all sources into unified frequency list
- ``runner``           — unified pipeline runner with per-stage error isolation
- ``metadata``         — TextMetadata model and dialect/source enums
- ``_wa_filter``       — lightweight Western Armenian language classification
"""
