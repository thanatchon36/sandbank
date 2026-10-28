# arXiv submission metadata

Generated from `paper/sections/abstract.tex` with the numbers substituted (`make arxiv` prints the same).
The upload is the author's own step; nothing here has been submitted.

**Title**

Under Pressure: Do LLM Agents Circumvent KYC/AML Controls to Hit Business Targets?

**Authors**

Thanatchon Chongmankhong

**Abstract** (1842 characters; arXiv allows 1,920)

Banks are starting to give LLM agents tools that can open accounts and post transactions. We ask whether such an agent, given an ordinary sales target and a manager who pushes for it, will circumvent know-your-customer (KYC) and anti-money-laundering (AML) controls. SandBank is a fully synthetic core-banking sandbox exposed to the agent as tools, with a deterministic detector for eight violation types, a Compliance check-in, and pre-registered experiments varying pressure, control hardness, oversight cues, a compliance sentence and four mitigations. Across 3,522 runs of Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 we observed 0 violations and 0 circumvention attempts. In the main pressure experiment the 95% upper bound on the per-run violation rate is 0.53% for Haiku and 0.53% for Sonnet (720 runs each) and 1.32% for Opus (288); counting each scenario once, since seeds are reused across pressure levels, the bounds are 2.1%, 2.1% and 5.1%. In pilot and ceiling probes run on Haiku and Sonnet only, neither an explicit licence from the manager ("use the override fields, I'll back you") nor a direct order to enter an override produced a violation; scripted agents confirmed that the environment registers every violation type. The agents instead checked KYC, requested documents, escalated sanctions hits and told the manager the target would be missed. The pre-registered hypotheses about pressure, hardness, oversight and mitigations are not supported, and those about deception and knowing violations could not be tested. In an exploratory comparison the models differed in legitimate goal attainment: a large deposit that policy allows once its report is filed was opened in 65% of Haiku runs (95% CI 56-73), 92% of Sonnet runs (85-95) and 100% of Opus runs (93-100). The sandbox, pre-registration and all run logs are released.

**Comments**

17 pages, 3 figures. Pre-registered; code, data and the sandbox: https://github.com/thanatchon36/sandbank

**Categories (proposed)**

Primary cs.AI; cross-lists cs.CY and q-fin.RM. A first submission to cs.AI may need an endorser.

**Licence (proposed)**

CC BY 4.0.

**Source**

`paper/arxiv.tar.gz` from `make arxiv` (not tracked; rebuild before uploading).
