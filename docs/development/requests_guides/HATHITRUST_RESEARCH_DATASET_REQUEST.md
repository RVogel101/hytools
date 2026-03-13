# HathiTrust Research Dataset Request

HathiTrust blocks web scraping (403). For bulk Armenian text, request rsync access to a research dataset.

**Source:** [HathiTrust Research Datasets](https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/research-datasets/)

---

## 1. Choose a Dataset

You request access to an **entire dataset**; even if you only want a subset (e.g. Armenian volumes), you get rsync access to the full endpoint. Your options:

| Dataset | Who | Contents |
|---------|-----|----------|
| **ht_text_pd_open_access** | US-based researchers | Public domain, excluding Google-digitized volumes |
| **ht_text_pd_world_open_access** | Non-US researchers | Same, excluding Google-digitized |
| **ht_text_pd** | US-based researchers | All public domain, including Google-digitized |
| **ht_text_pd_world** | Non-US researchers | Same, including Google-digitized |

**Google-digitized volumes:** If you want ht_text_pd or ht_text_pd_world, your institution must have signed the [Distribution Agreement with Google](https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/research-datasets/). Send signed agreement to support@hathitrust.org to begin.

### If You Don't Know Which Dataset

HathiTrust will help. In your proposal, include:

- **Characterization of desired texts:** dates, languages (e.g. Armenian), subjects
- **Or** a list of HathiTrust volume IDs (HTIDs)
- **Or** a link to a public HathiTrust Collection

They will recommend which dataset fits your needs and is available to you.

---

## 2. Send the Proposal

Email **support@hathitrust.org** with:

1. **Researchers:** Name, institutional affiliation, country of residence for all who will contribute
2. **Dataset:** Which dataset you want (ht_text_pd_open_access, ht_text_pd_world_open_access, ht_text_pd, or ht_text_pd_world)
3. **Research description:** What research is to be done
4. **Outputs:** What the result outputs will be
5. **Use:** How the research outputs will be used
6. **Permission:** Whether you grant HathiTrust permission to share your proposal as an example (optional)

---

## 3. Sign the Researcher Agreement

Sign and return the appropriate agreement:

- [Researcher Agreement for public domain data, excluding Google-digitized materials](https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/research-datasets/)
- [Researcher Agreement for all public domain data, including Google-digitized materials](https://www.hathitrust.org/member-libraries/resources-for-librarians/data-resources/research-datasets/)

---

## 4. After Approval

- HathiTrust will ask for a **static IP address**
- rsync access is granted only from that IP
- Use [Dataset rsync instructions](https://github.com/hathitrust/datasets/wiki/Dataset-rsync-instructions) to sync
- Convert HTIDs to pairtree paths for rsync (see [HTRC Feature Reader](https://github.com/htrc/HTRC-Feature-Reader) or pairtree library)

---

## 5. Suggested Proposal Text (Armenian Corpus)

**Subject:** Research dataset request — Armenian language corpus

**Researchers:** [Your name], [Affiliation], [Country]

**Dataset:** ht_text_pd_open_access (or ht_text_pd_world_open_access if outside US)

**Research:** Building a Western Armenian language corpus for NLP research and language model training. We need Armenian-language public-domain texts from the 19th–20th century.

**Characterization:** Language: Armenian (arm). Subjects: literature, history, religion, periodicals. Dates: 1800–1950.

**Outputs:** Extracted plain text, metadata, and corpus statistics for academic use.

**Use:** Non-commercial research, publications, and open-source tools. We will cite HathiTrust in all outputs.

**Permission:** Yes, HathiTrust may share this proposal as an example.
