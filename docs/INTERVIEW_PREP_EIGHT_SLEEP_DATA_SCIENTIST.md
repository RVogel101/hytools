# Eight Sleep — Data Scientist Interview Prep (30-Min Intro with Hiring Manager)

**Role:** Data Scientist (forecasting, inventory, finances, marketing)  
**Company:** Eight Sleep (health/tech, sleep optimization)  
**Prep for:** Intro call with Andrew (hiring manager) — casual conversation + fit + questions  

Use this doc to research the company, prepare your stories, and draft questions. Adjust specifics (e.g., Andrew’s exact title) once the recruiter confirms.

---

## Part 1: Company Overview

### What Eight Sleep Does

- **Mission:** Technology that enhances sleep — “clinically-backed sleep fitness.” Sleep is treated as an optimizable health metric (like fitness), not just rest.
- **Product:** Smart sleep system (Pod) — mattress cover + hub that does:
  - **Dual-zone cooling/heating** (e.g. 13°C–43°C) for couples
  - **Sleep tracking:** stages, HR, HRV, respiratory rate, snoring
  - **Automated adjustments** (Autopilot) using age, sex, sleep stage, environment
  - **Snoring detection and mitigation** (e.g. elevation), vibration alarms, optional soundscapes
- **Product tiers:** Pod 5 Core (cover + hub), Pod 5 Ultra (+ adjustable base, speakers). Add-ons: Hydro-powered blanket, Pod Pillow Cover.
- **Reported outcomes (from their materials):** e.g. 44% less time to fall asleep, 34% more deep sleep, 45% snoring reduction, 23% fewer wake-ups; hot-flash reduction in clinical studies.
- **Data scale:** 400M+ hours of sleep data; Sleep Fitness Score tracked across 25+ countries; expanding from sleep into predictive health (e.g. FDA-related work for sleep apnea detection/mitigation).

### Business & Funding

- **Founded:** 2014  
- **HQ:** New York (with presence in San Francisco).  
- **Funding:** $300M+ total; Series D; ~$1.5B valuation (2026); free-cash-flow positive (2025).  
- **Scale:** ~100–160 employees; ships to 34+ countries; DTC + partnerships (e.g. athletes, teams like UAE Team Emirates, Charles Leclerc, Taylor Fritz).  
- **Leadership:** CEO Matteo Franceschetti (co-founder), CTO Massimo Andreasi Bassi (co-founder). Scientific Advisory Board includes e.g. Andrew Huberman, Matthew Walker.

### Why This Matters for a Data Scientist

- **Data-rich:** Millions of sleep sessions, biometrics, and product usage → forecasting, personalization, and health insights.
- **Hardware + software:** Demand depends on product launches, seasonality, marketing, and inventory — ideal for forecasting and growth analytics.
- **Health/tech:** Rigor, experimentation, and clear communication to non-technical stakeholders (growth, finance, ops) matter.

---

## Part 2: The Data Scientist Role (Growth / Forecasting)

From job posts, the Growth Data Scientist role centers on:

- **Demand & inventory forecasting** — Reduce stock-outs (e.g. Black Friday, holidays) without over-committing capital.
- **Marketing optimization** — Spend allocation, seasonality, macro trends, cross-channel effects, CAC targets.
- **Experimentation** — A/B and incrementality testing (e.g. Meta, Google, YouTube).
- **Attribution & analytics** — Marketing attribution, customer journey complexity, dashboards for growth and finance.
- **Cross-functional work** — With Growth and Finance on performance and opportunities.

**Typical requirements (adapt to your background):**  
Python/R and SQL at an advanced level; forecasting (e.g. Prophet); A/B testing; marketing/sales data; visualization (Tableau, Looker, or similar); ~5+ years of impact on business-critical forecasting/optimization.

---

## Part 3: Questions to Ask Andrew (Hiring Manager)

Pick 2–3 that feel most genuine to you. Avoid questions that a quick Google search can answer.

### About the Role & Team

1. **“How does the Data Science team work with Growth and Finance day to day — is it mostly ad-hoc analyses, recurring forecasts, or both?”**
  *(Shows you care about how your work lands and how priorities are set.)*
2. **“What does ‘good’ look like for this role in the first 6–12 months? Any specific forecasting or marketing problems you’d want tackled first?”**
  *(Signals you think in outcomes and timelines.)*
3. **“How is demand forecasting currently done — who owns it, what tools and data do you use, and where do you see the biggest gaps?”**
  *(Reveals maturity of forecasting and where you could add value.)*
4. **“Is the data science team centralized or embedded in Growth/Finance? How do you balance quick business asks vs. longer-term model/infra work?”**
  *(Team structure and prioritization.)*

### About Data, Tech & Impact

1. **“What’s the single most important metric or decision that data science supports for the business right now — inventory, CAC, LTV, or something else?”**
  *(Shows you think in business impact.)*
2. **“How do you handle seasonality and promotions (e.g. Black Friday) in forecasting — any war stories or lessons learned?”**
  *(Directly relevant to the role.)*
3. **“Where does marketing attribution sit today — last-touch, MTA, MMM, or experiments — and what would you want to improve?”**
  *(Shows you understand growth/marketing analytics.)*

### About Andrew & Culture

1. **“What’s the part of your job you’re most excited about right now, and what’s the hardest trade-off you’re dealing with?”**
  *(Personal, shows curiosity about the manager.)*
2. **“What kind of person tends to thrive on your team, and what kind tends to struggle?”**
  *(Fit and self-assessment.)*
3. **“What does the take-home assignment usually look like for data roles — is it more forecasting, experimentation, or open-ended analysis?”**
  *(Practical and shows you’ve read their process.)*

### About Eight Sleep Specifically

1. **“How does the fact that Eight Sleep sells hardware (Pod) change how you think about demand forecasting compared to a pure software or subscription business?”**
  *(Product-aware and strategic.)*
2. **“Is any of the sleep or usage data from the Pod used in growth or finance models, or is that mainly for product/health features?”**
  *(Connects product data to your potential work.)*

---

## Part 4: Possible Questions from the Hiring Manager (With Answer Frameworks)

Use these to prepare short, concrete stories. Keep answers to 1–2 minutes unless they ask for more detail.

### Situational / Behavioral

**1. “Tell me about a time you built a demand or sales forecast that had real business impact.”**

- **Structure:** Situation → Task → Action → Result.  
- **Include:** What was being forecast (e.g. units, revenue, by channel/SKU); what data and methods you used (time series, ML, Prophet, etc.); how you handled seasonality or promotions; who used it (ops, finance, marketing); one concrete outcome (e.g. reduced stock-outs, better allocation).  
- **Tip:** Quantify impact (e.g. “reduced overstock by X%” or “improved forecast error by Y%”).
- Durring negotiations with various third-party payment providers, the payment team relied on my multi-demensional prophet forecasts for sales and transaction volume of each payment product to estimate expenses for various pricing structurs proposed during negotiations. This allowed payment business team to be "armed" with information to push back and get better deals.
- I used forecasting models to develope business case proposals in collaboration between with the business to present to executive leadership to choose between projects. 

**2. “Describe a situation where your forecast was wrong or a launch underperformed. What did you do?”**

- **Structure:** What happened → How you found out → How you diagnosed (data, assumptions, external factors) → What you changed (model, process, communication) → What you learned.  
- **Show:** Accountability, curiosity, and focus on improving the next forecast or process.  
- **Avoid:** Blaming others or being vague.
- During a negotiation with PayPal, my business partners asked for a 5 year monthly forecast to help them compare possible costs of different pricing structures proposed by the vendow. Since this was a seperate payment product from the rest of the credit and debit card products, the was collected and stored as a seperate process. At the time, I was unaware of a data source issue that caused my query to count the same transaction multiple times in a number of instances. Because of this, although my model was trained well, and in my testing and validation stage, I found no instances of over or under fit and MAPE scores of ~10%, because my training data was all doubled, the forecast predicted twice as much as it should. During my meeting with my business partner to go over the results, they called out that my numbers looked a bit high. Based on that comment, I went back to the data and did a deep dive and looked at it row by row to figure out where my qeury was going wrong and discovered a bug in the data. I then updated my qeury to account for the issue and re-ran my model to get the final accurate results that could be presented to leadership.   

**3. “Tell me about working with a non-technical stakeholder (e.g. finance or marketing) on a complex data problem.”**

- **Structure:** Who they were, what they needed, why it was hard (jargon, conflicting priorities, ambiguity).  
- **Action:** How you simplified the problem, chose 1–2 key metrics or visuals, and iterated based on feedback.  
- **Result:** Decision made or behavior changed; what you’d do differently.  
- **Tip:** Emphasize clarity, visuals, and “so what” instead of methodology details.

**4. “Give an example of balancing multiple urgent requests. How did you prioritize?”**

- **Structure:** What the competing asks were, who needed what and by when.  
- **Action:** How you prioritized (impact, dependency, stakeholder alignment) and how you communicated timelines and trade-offs.  
- **Result:** What shipped, what was deferred, and whether anyone was unhappy and how you handled it.  
- **Tip:** Shows you can say no or re-scope in a constructive way.

**5. “Describe a time you improved a process or introduced a new tool or method on your team.”**

- **Structure:** What was broken or manual; what you proposed (e.g. automated pipeline, new forecast model, dashboard).  
- **Action:** How you got buy-in, piloted, and rolled out.  
- **Result:** Time saved, fewer errors, or better decisions.  
- **Tip:** Small wins (e.g. “automated a weekly report”) are fine if the impact is clear.
- automated firm monthly saturation reporting for the vender risk part of  operation risk management team using SQL and Python.

### Technical (Forecasting & Analytics)

**6. “How would you forecast demand for a product with strong seasonality (e.g. Black Friday) and limited history?”**

- **Answer direction:**  
  - Use whatever history exists (same product or similar SKUs); consider proxy series (e.g. category or channel).  
  - Decompose trend + seasonality (e.g. seasonal decomposition, or Prophet’s built-in components).  
  - Incorporate leading indicators: promo calendar, marketing spend, macro/industry data if useful.  
  - Quantify uncertainty (intervals, scenarios) and stress-test assumptions.  
  - Be explicit about limitations (e.g. “first-year Black Friday is partly judgment + benchmarks”).
- **Tip:** Mention specific tools (e.g. Prophet, ARIMA, or simple regression with seasonal dummies) and why you’d choose one for this context.

**7. “How do you approach marketing mix modeling (MMM) or attribution when you have many channels and limited data?”**

- **Answer direction:**  
  - Clarify goal: budget allocation, incrementality, or both.  
  - MMM: aggregate time series, adstock, saturation, seasonality; identify colinearity and use priors or regularization if needed.  
  - When data is limited: simplify (fewer channels, longer windows), use experiments for key channels, or hybrid (MMM + test-based calibration).  
  - Be clear about causality limits and use experiments where possible.
- **Tip:** Show you know the difference between correlation and incrementality.

**8. “Explain how you’d design an A/B test for a marketing campaign (e.g. Meta) to measure true incrementality.”**

- **Answer direction:**  
  - Define metric (e.g. sign-ups, purchases, CAC).  
  - Holdout or geo test: random holdout (no campaign) vs. exposed; or geo-level randomization if user-level is not possible.  
  - Duration and power: ensure enough sample size and conversion rate; avoid short runs.  
  - Guard against spillover (e.g. same user on multiple channels) and selection bias.  
  - Mention incrementality vs. last-click and why it matters for budget decisions.
- **Tip:** Even a high-level design (holdout, duration, metric) shows you think like a growth data scientist.

**9. “What’s your experience with Python/R and SQL in production? Give an example of a pipeline or report you built.”**

- **Answer direction:**  
  - One concrete example: data source → transform (SQL or Python) → model or aggregation → output (forecast, dashboard, table).  
  - Mention scheduling (e.g. cron, Airflow), versioning, and how stakeholders consumed it.  
  - If you haven’t built “production” pipelines, describe the most automated, repeatable analysis you’ve done and what you’d add to make it production-ready.
- **Tip:** Honesty about “mostly ad-hoc but I’ve built X” is better than overclaiming.

**10. “How do you communicate forecast uncertainty to finance or operations?”**

- **Answer direction:**  
  - Use ranges or intervals (e.g. 80% or 90% prediction intervals), not just point forecasts.  
  - Scenario framing: “best / base / worst” or “with/without promo.”  
  - Simple visuals: fan charts, scenario tables, or a few key numbers.  
  - Tie to decisions: “If we order X we have Y% chance of stock-out.”
- **Tip:** Emphasize that the goal is better decisions, not impressing them with stats.

### Fit & Motivation

**11. “Why are you looking to leave your current role / why are you interested in Eight Sleep?”**

- **Do:** Tie to mission (health, sleep, measurable impact), product (hardware + data), stage (growth, small team), and the type of work (forecasting, growth, cross-functional).  
- **Don’t:** Badmouth current employer or focus only on compensation.  
- **Example:** “I want to work on forecasting and growth analytics in a place where the product is data-rich and the team is small enough that my work directly affects decisions. Eight Sleep’s focus on sleep fitness and the mix of inventory and marketing problems is a strong fit.”

**12. “What kind of work excites you most — and what do you prefer less?”**

- **Do:** Be honest; align “excites” with the role (e.g. building forecasts that ops and finance use, improving marketing efficiency, experimentation).  
- **Mention one “prefer less”** that isn’t central to the job (e.g. “I prefer less pure maintenance of legacy reports”) so you sound balanced.  
- **Tip:** Shows self-awareness and fit.

**13. “Tell me about a time you worked on a small team or wore multiple hats.”**

- **Structure:** Team size, your role, what “multiple hats” meant (e.g. data + some eng, or analytics + stakeholder management).  
- **Action:** How you prioritized, stayed organized, and communicated.  
- **Result:** Deliverables and what you learned.  
- **Tip:** Eight Sleep is ~100–160 people; they value ownership and flexibility.
- in my first position out of university, I worked as a Risk Analyst in the Operational Risk Management team at Russell Investments. This was a small team of 6, responsible for all Operational Risk activities for an $300B Asset Firm. I was hired to work under the lead analyst in charge of the Business Continuity and Vendor Risk Management programs, but because I was the most junior analyst on the team, I was given any other slack work needed by the other team. Because of this, I had to become a sort of "jack of all trades" analyst. I eventually was able to learn every position on the team and trained multiple new analyst during my tenure and even took over the Business Continuity and Vendor Risk Management programs when my team lead left for another position.  
---

## Part 5: Eight Sleep’s Stated Values (From Their Interview Guide)

Align your examples and tone with these:

- **Meaningful work** — Motivated by building something meaningful with a tight-knit team.  
- **Learning and challenge** — Learn quickly; challenge the status quo when it’s constructive.  
- **Pace** — Thrive in a fast-paced environment.  
- **Communication** — Clear and direct.  
- **Ownership** — Take ownership; bias toward action.  
- **Standards and kindness** — High standards while staying kind.  
- **Collaboration** — Excited to help others win.

**Interview process (for later rounds):** Application → 2–4 interviews → take-home (data folks often analyze/interpret data) → panel (e.g. review your deliverable together) → CEO interview → reference checks. They read cover letters and assessments carefully; they want thoughtful questions and to see how you think.

---

## Part 6: Quick Prep Checklist

- Read Eight Sleep’s site (product, science, blog) and their interview guide.  
- Identify 2–3 stories that show forecasting, cross-functional work, and handling mistakes.  
- Pick 2–3 questions to ask Andrew that you genuinely care about.  
- Prepare a 60–90 second “why Eight Sleep / why this role” that ties your background to their mission and the job.  
- Prepare a short “why looking / what excites you next” that’s positive and forward-looking.  
- Re-read the job description and map your experience to forecasting, inventory, marketing, and finance.

Good luck. Keep the intro call conversational; show curiosity about the team and the problems, and be ready to go deeper on one or two technical or situational topics if Andrew goes there.