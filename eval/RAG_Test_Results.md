# RAG Test Results — Personal Test (20 Questions)

_Backend:_ **docling** · _Retrieval:_ top-8 · _Embedding:_ `text-embedding-3-large` · _LLM:_ `gpt-5.6-terra` · _Generated:_ 2026-07-24

## Summary

| Metric | Value |
|---|---|
| **Overall match score (LLM-judge, 0-100)** | **100.0** |
| Keyword coverage (avg) | 80.4% |
| Correct source retrieved | 95% (19/20) |
| Verdicts | ✅ correct 20 · 🟡 partial 0 · ❌ wrong 0 |

> Scoring: **match_score** is an LLM judge (0-100) comparing the RAG answer to the reference answer (numbers must match). **keyword_match** = share of the test set's match-keywords present in the RAG answer. **source_hit** = the expected source deck appeared in the retrieved chunks.

> **Note on Q10:** `source_hit` shows ❌ only because the exact test-set filename (`_140_DSX_Adtalem_..._Copy1.pptx`) is not in the corpus — but a **near-duplicate of the same deck** (`_140_DSX_Data Science_Lead Score Generation - Copy.pptx`, same Adtalem content) **is**, and the RAG correctly retrieved and cited it. So effective source coverage is **20/20**; the ❌ is a filename-matching artifact, not a retrieval miss. `keyword_match` is a strict literal check (e.g. it counts "3M" but not "3 million"), so it understates correctness — the judge score is the better signal.

## Scoreboard

| # | Score | Verdict | Keywords | Src hit | Question |
|---|---|---|---|---|---|
| 1 | 100 | ✅ correct | 4/5 (80%) | ✅ | In the Mastercard financial services deck on benchmarking vs. best-in-… |
| 2 | 100 | ✅ correct | 4/4 (100%) | ✅ | In the Phoenix pharmaceutical case about repositioning a major marketi… |
| 3 | 100 | ✅ correct | 4/5 (80%) | ✅ | In the OTA financial services omni-channel acquisition campaign, which… |
| 4 | 100 | ✅ correct | 5/5 (100%) | ✅ | For FreshDirect acquisition, what direct-mail campaign results beat pl… |
| 5 | 100 | ✅ correct | 3/3 (100%) | ✅ | In the State Farm national auto insurer MMM case about a $500MM-$750MM… |
| 6 | 100 | ✅ correct | 6/6 (100%) | ✅ | In the 21st Century California auto insurance lead scoring case, what … |
| 7 | 100 | ✅ correct | 4/4 (100%) | ✅ | In the CNO Financial campaign strategy and lead journey case, what del… |
| 8 | 100 | ✅ correct | 5/5 (100%) | ✅ | In the Dish telecom and retail wireless marketing excellence roadmap c… |
| 9 | 100 | ✅ correct | 3/4 (75%) | ✅ | In the AdTech MLOps case for real-time bidding campaign optimization, … |
| 10 | 100 | ✅ correct | 5/6 (83%) | ❌ | For Adtalem lead scoring, what conversion lift did the top decile achi… |
| 11 | 100 | ✅ correct | 4/6 (67%) | ✅ | In the Goldman Sachs financial services cross-channel attribution case… |
| 12 | 100 | ✅ correct | 5/6 (83%) | ✅ | Which case should a sales rep use to show a hospitality company moving… |
| 13 | 100 | ✅ correct | 3/5 (60%) | ✅ | For PetPlan, what data-quality issue changed confidence in marketing a… |
| 14 | 100 | ✅ correct | 4/5 (80%) | ✅ | In the Aetna health insurance next-best-action case, what customer lif… |
| 15 | 100 | ✅ correct | 2/6 (33%) | ✅ | For USF sales leadership, what scale and commercial lift did the custo… |
| 16 | 100 | ✅ correct | 4/6 (67%) | ✅ | In the Benefytt health insurance direct-mail modeling case, what total… |
| 17 | 100 | ✅ correct | 5/5 (100%) | ✅ | In the Seamless retail apparel analytics case aiming for Apple-level s… |
| 18 | 100 | ✅ correct | 6/6 (100%) | ✅ | For Myovant, what outcomes show the omnichannel next-best-action solut… |
| 19 | 100 | ✅ correct | 3/5 (60%) | ✅ | In the predictive personalization case for a global entertainment stre… |
| 20 | 100 | ✅ correct | 2/5 (40%) | ✅ | In the healthcare integrated media marketing analytics engine case, wh… |

## Question-by-question

### Q1 — ✅ correct · score 100/100

**File:** `_004_BTS_Mastercard`  
**Question:** In the Mastercard financial services deck on benchmarking vs. best-in-class B2B marketers, what did the work use to compare leading B2B marketers?

**Expected (test set):** A comparative multi-dimensional framework with composite scores and dimensions.

**RAG answer:**

> The work developed a **comparative, multi-dimensional framework** to compare leading B2B marketers against one another, using **composite scores and key performance dimensions** derived from multi-sourced data, subject-matter expertise, and company intelligence. [MasterCard Case Study-project 4.pptx · slide 1]

**Keyword match:** 4/5 (80%) · **Source retrieved:** yes · **Judge:** It correctly states that the work used a comparative multi-dimensional framework with composite scores and dimensions to compare leading B2B marketers.

---

### Q2 — ✅ correct · score 100/100

**File:** `_005_BTS_Phoenix`  
**Question:** In the Phoenix pharmaceutical case about repositioning a major marketing services agency for growth, what shift did the CEO want to make over the next five years?

**Expected (test set):** Shift from a services company to a software-and-services company.

**RAG answer:**

> The CEO wanted to transition the agency from a **“services” company to a “software and services” company**, leveraging the proprietary technology that powered its services, while pursuing the next stage of double-digit growth. [_005_BTS_Phoenix_Pharmaceutical_Re positioning Major Marketing Services Agency for Growth .pptx · slide 1]

**Keyword match:** 4/4 (100%) · **Source retrieved:** yes · **Judge:** The answer exactly matches the requested shift from a services company to a software-and-services company.

---

### Q3 — ✅ correct · score 100/100

**File:** `_009_DSX_OTA`  
**Question:** In the OTA financial services omni-channel acquisition campaign, which channel combinations produced 12% and 26% lift?

**Expected (test set):** DM + Paid Social produced 12% lift; DM + Connected TV produced 26% lift.

**RAG answer:**

> - **Direct Mail + Paid Social** produced a **12% lift** over Direct Mail only.   - **Direct Mail + Connected TV** produced a **26% lift**. [_009_DSX_OTA_FinancialServices_Omni Channel Campaign Execution & Onboarding - OTA.pptx · slide 1]

**Keyword match:** 4/5 (80%) · **Source retrieved:** yes · **Judge:** The answer exactly matches both channel combinations and lift values: Direct Mail + Paid Social at 12% and Direct Mail + Connected TV at 26%.

---

### Q4 — ✅ correct · score 100/100

**File:** `_024_DSX_FreshDirect`  
**Question:** For FreshDirect acquisition, what direct-mail campaign results beat plan in fall 2018?

**Expected (test set):** Response rate beat plan by 29%, and CPA was 29% below target.

**RAG answer:**

> For FreshDirect’s fall 2018 acquisition campaign, response rate exceeded plan by **29%**, and CPA was **29% below target**. [\_024_DSX_FreshDirect_OnlineGrocer_Acquisition Optimization - Fresh Direct.pptx · slide 1]

**Keyword match:** 5/5 (100%) · **Source retrieved:** yes · **Judge:** The answer exactly matches both reported results: response rate beat plan by 29% and CPA was 29% below target.

---

### Q5 — ✅ correct · score 100/100

**File:** `_047_DSX_StateFarm`  
**Question:** In the State Farm national auto insurer MMM case about a $500MM-$750MM marketing budget, what efficiency result was reported?

**Expected (test set):** Marketing efficiency improved by almost 30%.

**RAG answer:**

> The State Farm MMM case reported an improvement in marketing efficiency of **almost 30%**. [_047_DSX_StateFarm_Insurance_MMM.pptx · slide 1]

**Keyword match:** 3/3 (100%) · **Source retrieved:** yes · **Judge:** The RAG answer exactly matches the reported result that marketing efficiency improved by almost 30%.

---

### Q6 — ✅ correct · score 100/100

**File:** `_053_DSX_21stCentury`  
**Question:** In the 21st Century California auto insurance lead scoring case, what three quantified impacts were reported after real-time scoring?

**Expected (test set):** 64% higher conversion, 79% lower cost per conversion, and 91% shorter lead scoring run time.

**RAG answer:**

> The reported impacts were:  - **64% increase in conversion rates** - **79% decrease in cost per conversion** - **91% shorter lead-scoring run times** [_053_DSX_21stCentury_Insurance_Lead Scoring & Optimization.pptx · slide 1]

**Keyword match:** 6/6 (100%) · **Source retrieved:** yes · **Judge:** The RAG answer exactly matches all three reported quantified impacts: 64% higher conversion, 79% lower cost per conversion, and 91% shorter lead scoring run time.

---

### Q7 — ✅ correct · score 100/100

**File:** `_094_DSX_CNO`  
**Question:** In the CNO Financial campaign strategy and lead journey case, what deliverable improved understanding of lead flow and decisioning outcomes?

**Expected (test set):** A multichannel lead journey map.

**RAG answer:**

> The deliverable was a comprehensive **multichannel Lead Journey Map**, showing the platform, responsible team, and sales/marketing actions at each step. It improved understanding of lead flow and supported better decisioning outcomes and customer experience. [_094_DSX_CNO Financial_Insurance_Campaign Strategy.pptx · slide 1]

**Keyword match:** 4/4 (100%) · **Source retrieved:** yes · **Judge:** It correctly identifies the deliverable as a multichannel lead journey map.

---

### Q8 — ✅ correct · score 100/100

**File:** `_095_Dish`  
**Question:** In the Dish telecom and retail wireless marketing excellence roadmap case, what campaign activation results were reported?

**Expected (test set):** Send volume increased 400%, and revenue impact increased 33%.

**RAG answer:**

> The reported campaign activation results were:  - Media planning shifted from ad hoc planning 2–3 weeks in advance to planning two full quarters ahead. - Multi-touch campaigns increased send volume by **400%** and overall revenue impact by **33%**. - The team identified martech/adtech gaps and overlaps, streamlined the ecosystem, eliminated excess technology, and began implementing new CDP, journey-orchestration, and identity solutions. [_095_Dish_TTM_BI_Customer Experience_Dish Telecommunications Roadmap and Campaign Activation.pptx · slide 1]

**Keyword match:** 5/5 (100%) · **Source retrieved:** yes · **Judge:** The answer correctly reports that send volume increased 400% and revenue impact increased 33%.

---

### Q9 — ✅ correct · score 100/100

**File:** `_126_TTM`  
**Question:** In the AdTech MLOps case for real-time bidding campaign optimization, what bidding-decision scale did the solution support?

**Expected (test set):** 3 million bidding decisions per second.

**RAG answer:**

> The solution supported **3 million bidding decisions per second** for real-time bidding campaign optimization. [_126_TTM_Data Science_Customer Experience_Advertisement Campaign Optimization through MLOps.pptx · slide 1]

**Keyword match:** 3/4 (75%) · **Source retrieved:** yes · **Judge:** The RAG answer exactly matches the reference scale of 3 million bidding decisions per second.

---

### Q10 — ✅ correct · score 100/100

**File:** `_140_DSX_Adtalem`  
**Question:** For Adtalem lead scoring, what conversion lift did the top decile achieve versus the existing production model?

**Expected (test set):** 47% higher conversion for DLS and 26% higher conversion for TOF.

**RAG answer:**

> For Adtalem lead scoring, conversion in the top decile increased by **47% for the DLS model** and **26% for the TOF model**, versus the existing production model. [_140_DSX_Data Science_Lead Score Generation - Copy.pptx · slide 1]

**Keyword match:** 5/6 (83%) · **Source retrieved:** NO · **Judge:** The answer exactly matches the reference conversion lifts: 47% for DLS and 26% for TOF versus the existing production model.

---

### Q11 — ✅ correct · score 100/100

**File:** `_004_DSX_GoldmanSachs`  
**Question:** In the Goldman Sachs financial services cross-channel attribution case, how did the model estimate incremental lift for channel mix decisions?

**Expected (test set):** It used transit and conversion stages, then compared actual conversions to a simulation where a channel was removed.

**RAG answer:**

> The model used a two-stage causal attribution approach:  1. **Transit stage:** It estimated how TV and digital impressions drove transits into variable channels, using aggregated customer-panel data across regions and time. The regressions controlled for seasonality, regional fixed effects, and other factors.  2. **Conversion stage:** A machine-learning attribution model on individual customer data estimated the incremental impact of those channel transits on conversions.  The combined estimates were used to simulate the number of conversions that would have occurred if a particular channel had not operated. The difference between simulated conversions and actual conversions was the channel’s estimated **incremental lift**, informing channel-mix decisions. [_004_DSX_GoldmanSachs_FinancialServices_Cross Channel Management & Attribution Model.pptx · slide 1]

**Keyword match:** 4/6 (67%) · **Source retrieved:** yes · **Judge:** It correctly states that the model used transit and conversion stages and estimated incremental lift by comparing actual conversions with simulations removing each channel.

---

### Q12 — ✅ correct · score 100/100

**File:** `_018_DSX_HGV`  
**Question:** Which case should a sales rep use to show a hospitality company moving from telemarketing to data-driven digital targeting, and what lift was reported?

**Expected (test set):** HGV predictive modeling and omni-channel targeting; over 60% incremental lift.

**RAG answer:**

> Use the **$2B Hospitality Predictive Modeling & Omni-Channel Targeting** case. It specifically describes a hospitality company moving beyond its long-standing telemarketing approach to predictive models and digital channels including display and paid social. The reported result was **over 60% incremental lift** versus business-as-usual lists and targeting. [_018_DSX_HGV_Hospitality_Predictive Modeling & Omni-Channel Targeting.pptx · slide 1]

**Keyword match:** 5/6 (83%) · **Source retrieved:** yes · **Judge:** It identifies the HGV Hospitality Predictive Modeling & Omni-Channel Targeting case and correctly reports over 60% incremental lift.

---

### Q13 — ✅ correct · score 100/100

**File:** `_025_DSX_PetPlan`  
**Question:** For PetPlan, what data-quality issue changed confidence in marketing attribution?

**Expected (test set):** A Google Analytics cookie expiration setting limited tracking of consumer behavior over time.

**RAG answer:**

> PetPlan identified that the Google Analytics cookie-expiration setting limited its ability to track consumer behavior over time. This data-capture issue reduced confidence in attribution conclusions and prompted a data-quality workstream. [_025_DSX_PetPlan_Insurance_Attribution Sensitivity Analysis.pptx · slide 1]

**Keyword match:** 3/5 (60%) · **Source retrieved:** yes · **Judge:** The answer exactly identifies the Google Analytics cookie-expiration setting as limiting longitudinal consumer tracking and reducing attribution confidence.

---

### Q14 — ✅ correct · score 100/100

**File:** `_058_DSX_Aetna`  
**Question:** In the Aetna health insurance next-best-action case, what customer life moment was the recommendation engine designed around?

**Expected (test set):** Customers around their 60th birthday.

**RAG answer:**

> The recommendation engine was designed to identify the best combination of offers to send customers around their **60th birthday**, to maximize sign-up rates. [_058_DSX_Aetna_Next Best Action.pptx · slide 1]

**Keyword match:** 4/5 (80%) · **Source retrieved:** yes · **Judge:** The answer correctly states that the recommendation engine targeted customers around their 60th birthday.

---

### Q15 — ✅ correct · score 100/100

**File:** `_077_DSX_USF`  
**Question:** For USF sales leadership, what scale and commercial lift did the customer-centric pricing solution deliver?

**Expected (test set):** 20M+ customer-level prices monthly, with 1.5-2% revenue lift and 7-8% margin lift.

**RAG answer:**

> For USF, the customer-centric pricing solution operated at substantial scale:  - Optimized prices across **60+ U.S. markets**, **126k+ customers**, and **67k+ products**. - Delivered **20M+ customer-level prices every month** to support field sales. - The solution had been in use for **8+ years**.  Commercially, it delivered an estimated **1.5–2% revenue lift** and **7–8% margin lift**. In the Austin market specifically, the identified opportunity was **1.7% sales lift** and **6.2% profit lift** if optimized prices were implemented. [_077_DSX_USF_B2B_CustomerCentric_PriceOptimization.pptx · slide 1]

**Keyword match:** 2/6 (33%) · **Source retrieved:** yes · **Judge:** It correctly states 20M+ customer-level prices monthly, 1.5–2% revenue lift, and 7–8% margin lift.

---

### Q16 — ✅ correct · score 100/100

**File:** `_081_DSX_Benefytt`  
**Question:** In the Benefytt health insurance direct-mail modeling case, what total business impact should marketing leadership cite?

**Expected (test set):** 20% YoY conversion improvement and $38MM revenue influenced from submissions.

**RAG answer:**

> Marketing leadership should cite **$38 million in revenue influenced from submissions** as the total business impact. The direct-mail modeling improvements also increased response rates across phases and improved lead conversion rates by **20% year over year**. [_081_DSX_Benefytt_Health Insurance_Direct Mail Modeling.pptx · slide 1]

**Keyword match:** 4/6 (67%) · **Source retrieved:** yes · **Judge:** It accurately states both the 20% YoY conversion improvement and $38MM revenue influenced from submissions.

---

### Q17 — ✅ correct · score 100/100

**File:** `_098_Seamless`  
**Question:** In the Seamless retail apparel analytics case aiming for Apple-level store performance monitoring, what data stack was built?

**Expected (test set):** An integrated DBT and Tableau data and analytics supply chain.

**RAG answer:**

> The solution built an integrated **dbt and Tableau-based data and analytics supply chain** to keep real-time inventory and store-performance data available. Supporting materials specify **Snowflake reporting layers**, **dbt-automated transformations**, and **Tableau dashboards** for RFID counts and on-shelf availability. [_098_Seamless Retail Apparel Analytics.pptx · slide 1] [Supply Chain Analytics Master Deck May 2025.pptx · slide 38]

**Keyword match:** 5/5 (100%) · **Source retrieved:** yes · **Judge:** The answer exactly identifies an integrated dbt and Tableau data and analytics supply chain, matching the reference.

---

### Q18 — ✅ correct · score 100/100

**File:** `_109_Myovant`  
**Question:** For Myovant, what outcomes show the omnichannel next-best-action solution improved marketing efficiency?

**Expected (test set):** 30% higher sales and marketing ROI, 65% lower resource expense, and 90% higher digital effectiveness.

**RAG answer:**

> For Myovant, the outcomes indicating improved marketing efficiency were:  - **30% increase in Sales and Marketing ROI** - **65% savings in resource expenses** through vendor consolidation—one solution built inside the client firewall eliminated the need for multiple vendors - **90% increase in digital effectiveness** by identifying digitally influenced targets and reducing waste [\_109_Myovant_Healthcare_Implementing Omnichannel Next Best Action.pptx · slide 1]

**Keyword match:** 6/6 (100%) · **Source retrieved:** yes · **Judge:** The answer exactly matches all three reference outcomes: 30% higher sales and marketing ROI, 65% lower resource expense, and 90% higher digital effectiveness.

---

### Q19 — ✅ correct · score 100/100

**File:** `_184_Technology-Media`  
**Question:** In the predictive personalization case for a global entertainment streaming platform, what user-data limitation did Blend work within, and what annual value was cited?

**Expected (test set):** Only viewing habits were available; about $5.3M annual value from personalized targeting.

**RAG answer:**

> Blend worked with only users’ viewing habits—without access to traditional demographic data. The cited annual value of personalized targeting was approximately **$5.3 million**. [_184_Technology-Media-Telecom_Data Science & Insights_Customer Experience_Predictive Personalization for Audience Modeling.pptx · slide 1]

**Keyword match:** 3/5 (60%) · **Source retrieved:** yes · **Judge:** The answer correctly states that only viewing habits were available, without demographic data, and cites approximately $5.3 million in annual value.

---

### Q20 — ✅ correct · score 100/100

**File:** `_189_Healthcare`  
**Question:** In the healthcare integrated media marketing analytics engine case, what proof points show the platform was enterprise-scale?

**Expected (test set):** Six modules, 48 automated models, 40+ screens, $75M+ media budget, and 131M target audience supported in 2024.

**RAG answer:**

> The platform demonstrated enterprise scale through several proof points:  - Managed and optimized a **$75M+ media budget** across business lines. - Supported a **target audience of 131 million people in 2024**—approximately **1 in 3 Americans across Aetna’s lines of business**—with potential to scale to **190 million Americans**. - Launched as a secure, **SSO-integrated enterprise application** with **40+ interface screens and controls**. - Included **six purpose-built modules** and **48 automated planning and measurement models**. - Achieved adoption by **44 unique enterprise users**, with expansion across the enterprise. - Provided **90% measurement coverage**, with **100% accuracy validation** from users. - Used monthly enhancement releases aligned to critical business cycles, including enrollment periods. [_189_Healthcare & Lifesciences_Intelligent Applications_Enterprise Operations_Integrated Media Marketing Analytics Engine.pptx · slide 1]

**Keyword match:** 2/5 (40%) · **Source retrieved:** yes · **Judge:** It includes all enterprise-scale proof points exactly: six modules, 48 automated models, 40+ screens, $75M+ media budget, and a 131M target audience in 2024.

---
