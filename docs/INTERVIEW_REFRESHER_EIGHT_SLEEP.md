# Interview Refresher: Forecasting, A/B Testing, Business Jargon & Eight Sleep Summary

One-stop refresher for the Data Scientist (Growth) role: concepts, tech, and Eight Sleep in one place.

---

## 1. CAC Targets (and LTV)

**CAC = Customer Acquisition Cost**  
Total marketing/sales spend to acquire one customer, over a period (e.g. month/quarter).

- **Formula:** `CAC = (Marketing + Sales spend) / New customers acquired`
- **CAC target:** A ceiling or range the business sets (e.g. “CAC < $X” or “CAC must be < ⅓ of LTV”). Used to cap spend and compare channels/campaigns.
- **Why it matters:** If CAC exceeds what the customer will generate in profit (or LTV), growth is unprofitable.

**LTV = Lifetime Value**  
Expected total revenue (or profit) from a customer over their relationship with the company.

- **Formula (simplified):** `LTV = (ARPU × Gross margin %) / Churn rate` or `LTV = ARPU × (1 / churn)`; more advanced models use cohort retention curves and discounting.
- **LTV:CAC ratio:** Often target 3:1 or higher (LTV at least 3× CAC). Too low = unsustainable; too high can mean under-investing in growth.

**In interviews:** “CAC targets” = the business rule or goal (e.g. “keep CAC under $Y” or “improve CAC by Z%”). Your job as data scientist is to measure CAC by channel/campaign, forecast how changes (budget, creative, audience) affect it, and support incrementality tests so the business knows which spend actually drives new customers vs. steals credit.

---

## 2. Stock-Outs vs. Over-Committing Capital (Inventory Trade-off)

**The tension**

- **Stock-out:** Demand exceeds inventory → you can’t fulfill orders. Result: lost sales, unhappy customers (many switch after one bad experience), expedited shipping, brand damage.
- **Over-committing capital:** Ordering too much inventory → cash tied up in stock, carrying cost (warehouse, insurance, obsolescence), risk of markdowns or write-offs.

You **cannot** fully maximize “no stock-outs” and “minimize capital” at the same time. The goal is to choose a point on the **trade-off curve** (e.g. “95% fill rate at minimum inventory”) using data.

**How forecasting helps**

1. **Demand forecast** (by SKU, geography, time window) → expected need.
2. **Uncertainty** (intervals, scenarios) → how much safety stock to hold.
3. **Lead time** (supplier + in-transit) → when to reorder so stock arrives before demand.
4. **Replenishment policy** (reorder point, order-up-to level, or min/max) → translates forecast + uncertainty + lead time into “order X when stock hits Y.”

**Peak periods (Black Friday, holidays)**

- Demand spikes and is harder to predict (limited history, promo-driven). Forecasts use:
  - Prior-year same event (or similar SKUs)
  - Promo calendar and planned spend
  - Leading indicators (traffic, early sales)
- **Risk:** Under-forecast → stock-outs at peak. Over-forecast → excess after peak (capital tied up, markdowns).
- **Practice:** “We target a service level (e.g. 95% of demand fulfilled from stock) while minimizing expected excess at end of season” → safety stock + scenario planning + clear communication to ops/finance.

**Jargon**

- **Fill rate / service level:** % of demand satisfied from stock (e.g. 98% fill rate).
- **Safety stock:** Extra inventory held to absorb demand and lead-time variability.
- **Reorder point (ROP):** Inventory level at which you place a new order.
- **Lead time:** Time from order placement to stock availability.

---

## 3. Forecasting: SARIMAX & Deep Learning (Conceptual + Practice)

### SARIMAX — Conceptual

**SARIMAX** = Seasonal ARIMA with **eXogenous** regressors.

- **AR (Autoregressive):** Future value depends on past values of the series (e.g. yesterday’s sales helps predict today).
- **I (Integrated):** Differencing to make the series stationary (remove trend so mean/variance are stable).
- **MA (Moving Average):** Future value depends on past **errors** (shocks), not just past values.
- **S (Seasonal):** Repeating pattern at a fixed period (e.g. weekly, yearly). Same AR/MA structure but at the seasonal lag.
- **X (Exogenous):** External variables (e.g. promo flag, marketing spend, temperature) included as regressors.

**When to use SARIMAX**

- Clear **trend** and **seasonality** (e.g. retail, energy).
- You have **covariates** that drive demand (promos, ads, weather).
- Series is or can be made **stationary** (after differencing).
- Interpretability and confidence intervals matter (SARIMAX gives both).

**When not to use**

- Very short history; high-dimensional covariates; many series at once (scaling SARIMAX is painful). Then consider ML/DL or Prophet.

**Typical workflow**

1. Plot series; check trend/seasonality.
2. Test for stationarity (e.g. ADF); difference if needed.
3. Identify seasonal period (e.g. 12 for monthly, 7 for daily).
4. Fit SARIMAX (e.g. `statsmodels`); use AIC/BIC or cross-validation to choose order.
5. Forecast; report point forecast + prediction intervals.

**Practice-style question**

- **“How would you forecast demand for a new product with no history?”**  
  Use proxy series (similar product or category), incorporate leading indicators (launch spend, seasonality), state assumptions and uncertainty clearly, and plan to update as data comes in.

### Deep Learning Forecasting — Conceptual

- **N-BEATS:** Fully connected blocks with backward/forward residuals; good for univariate series; interpretable (trend/season blocks). Used when you want a single-series DL model without heavy tuning.
- **Transformers (e.g. TFT, PatchTST, Timer-XL):** Attention over time (and across series); good for long horizons and multi-variate settings. Require more data and compute.
- **When to use DL:** Large volume of series, long history, non-linear patterns, or need for multi-variate/global models. When to avoid: small data, need for interpretability or fast iteration (then SARIMAX/Prophet/ETS).

**Practice-style question**

- **“SARIMAX vs. a neural network for demand forecasting?”**  
  SARIMAX: interpretable, works with limited data, handles seasonality and trend explicitly, easy to explain to business. NN: better when you have many series and rich features, or complex non-linearities; less interpretable and more data-hungry. “I’d start with SARIMAX or Prophet for a single product; move to DL if we have hundreds of SKUs and enough history.”

---

## 4. A/B Testing & Causal Inference — Principles and Tech

**Goal:** Estimate the **causal** effect of a change (e.g. ad on vs. off), not just correlation.

**Core idea**

- **Treatment group:** Exposed to the intervention (e.g. sees campaign).
- **Control group (holdout):** Not exposed (e.g. no campaign, or placebo).
- **Incrementality:** Difference in outcome (e.g. conversions, revenue) between treatment and control = causal effect of the campaign.  
  **Incremental lift** = `(Treatment result − Control result) / Control result`.

**Why not just “before vs after” or “last-touch”?**

- Before/after confounds time (seasonality, other campaigns).  
- Last-touch attributes credit to the last click but doesn’t prove that touch **caused** the conversion (could have happened anyway).  
- Holdout vs. exposed isolates the effect of the campaign.

**Design choices**

- **Randomization level:** User-level (ideal but not always possible), geo (region/city), or time (e.g. on/off weeks).  
- **Duration:** Long enough for behavior to stabilize and for enough conversions (power). Often 2–4+ weeks.  
- **Size:** Treatment and control large enough for detectable effect (power analysis).  
- **Spillover:** Avoid same user in both (e.g. geo holdout when user-level is messy).

**Tech implementation (typical)**

1. **Experiment design:** Define cells (treatment/control), randomization unit, primary metric, duration.  
2. **Traffic/audience split:** Platform (e.g. Meta, Google) or internal system assigns users/geos to treatment vs. control; holdout gets no (or minimal) ad spend.  
3. **Data:** Log exposure (who saw what) and outcomes (conversions, revenue) by cell; join to one analysis table.  
4. **Analysis:** Compare metric in treatment vs. control (t-test, regression with treatment dummy, or CUPED/variance reduction); report point estimate and confidence interval.  
5. **Reporting:** Incremental lift %, incremental revenue, cost per incremental conversion (iCPA).

**Causal inference beyond A/B**

- **Difference-in-differences (DiD):** Compare change over time in treatment vs. control (controls for time trends).  
- **Synthetic control:** Build a “synthetic” control from similar untreated units when one large unit (e.g. one region) is treated.  
- **Instrumental variables (IV):** When you can’t randomize, use an instrument that affects exposure but not outcome except through exposure.

**Practice-style question**

- **“How would you measure if a Meta campaign is truly driving sales?”**  
  Run a holdout test: random split of audience (or geo); one group gets the campaign, one doesn’t. After 2–4 weeks, compare sales (or sign-ups) per user in each group. Difference = incremental impact. Report lift and confidence interval; avoid last-touch for this question.

---

## 5. Glossary: Inventory, Marketing & Business Jargon

| Term | Meaning |
|------|--------|
| **CAC** | Customer Acquisition Cost. Total cost to acquire one customer (marketing + sales). |
| **LTV** | Lifetime Value. Expected revenue (or profit) from a customer over their lifetime. |
| **LTV:CAC** | Ratio of LTV to CAC; often target ≥ 3. |
| **Last-touch attribution** | 100% credit for a conversion to the last touchpoint (e.g. last ad click). Simple but biased toward bottom-funnel. |
| **MTA (Multi-Touch Attribution)** | Credit split across multiple touchpoints (linear, time decay, position-based, or data-driven). User/journey level; good for optimization; weakened by cookie loss. |
| **MMM (Marketing Mix Modeling)** | Top-down, aggregate time-series model: outcome (e.g. sales) ~ spend by channel + seasonality + promo + external factors. Used for budget allocation and strategy; privacy-safe; needs 2+ years of data. |
| **Incrementality** | Causal lift from a campaign (treatment vs. holdout). “Incrementality testing” = measuring that lift with experiments. |
| **Stock-out** | No inventory to fulfill demand; lost sale. |
| **Fill rate / service level** | % of demand met from stock (e.g. 98% fill rate). |
| **Safety stock** | Extra inventory to buffer demand and lead-time variability. |
| **Lead time** | Time from placing an order to having stock available. |
| **Reorder point** | Inventory level that triggers a new purchase order. |
| **EOQ** | Economic Order Quantity. Order quantity that minimizes total cost (ordering + holding). |
| **Carrying cost** | Cost to hold inventory (warehouse, capital, insurance, obsolescence). |
| **ARPU** | Average Revenue Per User (per month or per year). |
| **Churn** | Rate at which customers stop (e.g. cancel). |
| **Cohort** | Group of users/customers defined by a shared event (e.g. sign-up month). |
| **Prophet** | Open-source forecasting tool (Facebook/Meta); handles trend, seasonality, holidays; easy to use. |
| **Adstock** | In MMM, the delayed/carry-over effect of ad spend (ads keep working after they run). |
| **Saturation** | In MMM, diminishing returns to spend (curve flattens at high spend). |

---

## 6. Eight Sleep: Product, Science, Blog & Interview Guide — Summary

### Product (from eightsleep.com)

- **What it is:** Smart sleep system — a **Pod** (mattress cover + hub) that fits on top of a mattress.  
- **Core features:**  
  - **Temperature:** Dual-zone cooling/heating (~55°F–110°F per side); personalized by biology and preference.  
  - **Sleep & health tracking:** Heart rate (~99% accuracy vs. ECG), HRV, respiratory rate, sleep stages, snoring; no wearable.  
  - **Autopilot:** Algorithm adjusts temperature over the night.  
  - **Snoring:** Detection and automatic elevation (Pod 4/5 Ultra) to reduce it.  
- **Tiers:** Pod 5 Core (cover + hub); Pod 5 Ultra (adds adjustable base, speakers). Add-ons: Hydro Blanket, Pod Pillow Cover.  
- **Claimed outcomes (from site):** e.g. 44% less time to fall asleep, 34% more deep sleep, 23% fewer wake-ups, 34% higher daytime energy, 25% improved sleep quality.

### Science (eightsleep.com/science)

- **Positioning:** “Clinically-backed sleep fitness” — sleep as an optimizable health metric.  
- **Studies (they cite):** Improvements in deep/REM sleep, cardiovascular recovery, heart rate, sleep quality, energy, executive function, memory, processing speed after short use (e.g. 1–2 weeks).  
- **Accuracy:** HR 99% vs. ECG; respiratory rate 98% vs. gold standard; deep learning sleep-staging algorithm.  
- **Comparison table:** Pod vs. melatonin, prescription sleep meds, wearables — no wearable, no consumable, non-addictive, long-term use.  
- **Advisory board:** Andrew Huberman (Stanford), Matthew Walker (UC Berkeley, *Why We Sleep*).

### Blog (high level)

- Content centers on **sleep fitness**, recovery, and performance (athletes, DST, sleep debt).  
- **Partnerships:** e.g. Charles Leclerc (F1), UAE Team Emirates (cycling) — Pod as recovery tool.  
- **Interview guide** (blog): “How to land a job at Eight Sleep” — see below.

### Interview Guide — Summary (from their blog)

- **Who they want:** Top performers; curious; move fast and aim high; builders, operators, scientists. Values: meaningful work with a tight-knit team, learn quickly, challenge the status quo, fast-paced, clear and direct communication, ownership, bias for action, high standards with kindness, help others win.  
- **Process (typical):**  
  1. **Application** — Resume + cover letter or short assessment.  
  2. **2–4 interviews** — Experience, judgment, how you think; come with thoughtful questions.  
  3. **Take-home** — Role-specific (for data: analyze/interpret simulated data); think critically, question assumptions, be data-driven and structured.  
  4. **Panel** — Teammates review your deliverable (e.g. memo-style) and discuss live; collaborative, not interrogation.  
  5. **CEO interview** — Vision, values, long-term goals; they send prep.  
  6. **Reference checks** — Required; not a formality.  
- **Tips they give:** Align resume with LinkedIn; be concise and specific with examples; show how you think; ask questions you can’t just Google; treat the take-home as a signal of whether you’d enjoy the job.

---

Use this doc for quick review before the call: CAC/LTV and targets, stock-out vs. capital trade-off, SARIMAX vs. DL, A/B and causal inference, and the glossary. Pair it with the main **INTERVIEW_PREP_EIGHT_SLEEP_DATA_SCIENTIST.md** for full prep.
