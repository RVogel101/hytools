# Gomidas Institute — Bulk Access Permission Walkthrough

The Gomidas Institute ([https://www.gomidas.org](https://www.gomidas.org)) holds 5,000+ digitized Armenian newspaper pages. Partial content is available online. This guide walks through requesting bulk access for research/corpus building.

## Current Status

- **Online resources**: [https://www.gomidas.org/resources.html](https://www.gomidas.org/resources.html)
- **Scraper**: `scraping/gomidas.py` — discovers and downloads linked PDFs
- **Limitation**: Only publicly linked items are accessible; full archive requires permission

## Step 1: Identify Contact

1. Visit [https://www.gomidas.org/](https://www.gomidas.org/)
2. Look for **Contact** or **About** page
3. Typical contacts:
  - **General inquiries**: [info@gomidas.org](mailto:info@gomidas.org) (verify on site)
  - **Research / archive**: May have a dedicated email for academic requests

## Step 2: Draft Permission Request

Use this template (customize as needed). Below is a **ready-to-send** version; fill in the bracketed fields.

---

**Ready-to-send draft**

**To:** [info@gomidas.org](mailto:info@gomidas.org) (verify on [https://www.gomidas.org](https://www.gomidas.org) for current contact)  
**Subject:** Request for Bulk Access to Armenian Newspaper Digitizations (Research)

Dear Gomidas Institute,

I am working on a Western Armenian language corpus project for NLP research and language preservation. Your digitized newspaper collection is a valuable resource for training language models and studying historical Armenian text.

**Project:** Western Armenian corpus expansion — open-source, non-commercial research.

**Request:** Permission to access and download digitized newspaper pages in bulk for:

- Text extraction via OCR
- Inclusion in a research corpus with full attribution to the Gomidas Institute
- Academic and preservation purposes only

**Usage:** The data would be used for:

- Training language models for Western Armenian
- Linguistic research and dialect studies
- No commercial use; full attribution to Gomidas Institute in metadata and any publications

**Technical:** We have implemented a scraper that can process your online resources. Bulk access (e.g. FTP, API, or batch download) would allow us to work more efficiently and reduce load on your servers.

Could you please advise:

1. Whether bulk access is possible for research projects?
2. Any terms, attribution requirements, or usage restrictions we should follow?
3. The preferred contact for formal permission requests?

Thank you for your work preserving Armenian cultural heritage.

Best regards,  
[Your name]  
[Affiliation]  
[Email]

---

**Alternative / shorter template (customize as needed):**

**Subject**: Request for Bulk Access to Armenian Newspaper Digitizations (Research)

Dear Gomidas Institute,

I am working on a Western Armenian language corpus project for NLP research and language preservation. Your digitized newspaper collection is a valuable resource for training language models and studying historical Armenian text.

**Project**: Western Armenian corpus expansion (open-source, non-commercial research)

**Request**: Permission to access and download digitized newspaper pages in bulk for:

- Text extraction via OCR
- Inclusion in a research corpus (with full attribution)
- Academic and preservation purposes

**Usage**: The data would be used for:

- Training language models for Western Armenian
- Linguistic research and dialect studies
- No commercial use; full attribution to Gomidas Institute

**Technical**: We have implemented a scraper that can process your online resources. Bulk access (e.g., FTP, API, or batch download) would allow us to work more efficiently and reduce load on your servers.

Could you advise on:

1. Whether bulk access is possible for research projects?
2. Any terms, attribution requirements, or usage restrictions?
3. Preferred contact for formal permission requests?

Thank you for your work preserving Armenian cultural heritage.

Best regards,  
[Your name]  
[Affiliation]  
[Email]

---

## Step 3: Follow Up

- Allow 2–4 weeks for response
- If no reply, try alternative contacts (e.g., via NAASR or AGBU if they have institutional links)
- Document any response and terms for future reference

## Step 4: After Permission

If granted:

1. **Update scraper**: Add any bulk download URLs or API keys to `scraping/gomidas.py`
2. **Attribution**: Ensure metadata includes `source: gomidas` and `attribution: Gomidas Institute`
3. **Terms**: Respect any usage restrictions (e.g., no redistribution of raw scans)

## Related

- [DATA_SOURCES_EXPANSION.md](DATA_SOURCES_EXPANSION.md) — overall source expansion plan
- [MECHITARIST_PERMISSION_REQUEST.md](MECHITARIST_PERMISSION_REQUEST.md) — similar template for Venice library

