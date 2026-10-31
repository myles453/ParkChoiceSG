# ParkChoiceSG: Project Decisions and Rationale

**Context record: 31 October 2026.**

This document explains what we are trying to achieve, the choices behind the product, and the trade-offs those choices create. It is intended for teammates who need to understand the project without reading the implementation. Use it to agree on the project story before selecting material for the presentation.

**The product in one paragraph:** ParkChoiceSG helps a driver compare nearby carparks for an intended visit. It estimates the chance of a free lot when the driver reaches each carpark, calculates the supported cost of the stay, considers the drive and the walk, and ranks usable options according to the driver's preference. Its value is making those trade-offs clear while keeping unsupported prices, stale evidence and unavailable forecasts explicit.

**Fast reading route:** start with sections 1-2 for the product, 10-13 for preferences and weights, and 22-24 for scope and presentation explanations. The other sections explain the foundations and the reasons behind the safeguards.

It records the current local implementation, the reasoning in our project discussions and validation notes, and the intended features that remain unfinished. It does not replace the final requirements specification or claim that every proposal was formally approved in a team meeting.

Three labels matter:

- **Current decision:** the direction or behaviour currently represented in the working project.
- **Working policy:** an explicit, implemented setting that can be revised. In particular, the ranking weights and several operational limits are designed defaults, not values proven uniquely optimal by user research.
- **Planned/deferred:** a target or proposal, not a capability we should describe as fully working.

The main explanations below are suitable for discussing the design confidently. Evidence boundaries and unresolved questions are collected separately near the end. We should distinguish “chosen to achieve a purpose” from “experimentally proven to be the best possible choice.”

## Contents

1. [The product and its purpose](#1-the-product-and-its-purpose)
2. [The complete decision journey](#2-the-complete-decision-journey)
3. [Inputs, arrival time and parking duration](#3-inputs-arrival-time-and-parking-duration)
4. [Why we retain HDB, LTA and URA](#4-why-we-retain-hdb-lta-and-ura)
5. [Why cleaning, identity and timestamps matter](#5-why-cleaning-identity-and-timestamps-matter)
6. [What our prediction means](#6-what-our-prediction-means)
7. [Why prediction coverage is deliberately limited](#7-why-prediction-coverage-is-deliberately-limited)
8. [Why pricing is a rule calculation](#8-why-pricing-is-a-rule-calculation)
9. [Why eligibility comes before scoring](#9-why-eligibility-comes-before-scoring)
10. [Why there are three preference modes](#10-why-there-are-three-preference-modes)
11. [How we chose the scoring weights](#11-how-we-chose-the-scoring-weights)
12. [How different units become comparable](#12-how-different-units-become-comparable)
13. [A worked example of the three modes](#13-a-worked-example-of-the-three-modes)
14. [Why fallback is separate from prediction](#14-why-fallback-is-separate-from-prediction)
15. [Maps, routes, shortlists and navigation](#15-maps-routes-shortlists-and-navigation)
16. [Why the system is divided into these components](#16-why-the-system-is-divided-into-these-components)
17. [Accounts, privacy and local data](#17-accounts-privacy-and-local-data)
18. [Sessions, reporting and operator decisions](#18-sessions-reporting-and-operator-decisions)
19. [How we validate the system](#19-how-we-validate-the-system)
20. [Important numerical policies in one place](#20-important-numerical-policies-in-one-place)
21. [How the project changed over time](#21-how-the-project-changed-over-time)
22. [What is working and what remains a target](#22-what-is-working-and-what-remains-a-target)
23. [Evidence limits and decisions to confirm](#23-evidence-limits-and-decisions-to-confirm)
24. [Concise explanations for a presentation](#24-concise-explanations-for-a-presentation)
25. [Supporting project records](#25-supporting-project-records)

## 1. The product and its purpose

### D01. Help a driver choose a carpark, rather than only locate one

**Current decision.** ParkChoiceSG is a parking decision assistant. A map of nearby carparks answers “where can I park?” but leaves the driver to compare cost, convenience and the chance of finding a space.

Our product combines those considerations into an explained recommendation. A useful result tells the driver what it costs for the intended stay, how far they will walk, how long they will drive, and what availability evidence supports the choice.

The project is differentiated by the combination of arrival-oriented availability, stay-specific pricing, preference trade-offs and explicit failure handling. We do not need to claim that no other parking product has ever used prediction.

### D02. Make arrival time the relevant availability question

**Current decision.** A reading showing free spaces now can be outdated by the time the driver arrives. We therefore ask:

> What is the chance that this carpark has a free car lot when this driver reaches it?

For example, two carparks may both have spaces now, but one is ten minutes away and the other twenty-five minutes away. Their relevant future conditions are different. Current availability remains useful evidence, but it is not itself an arrival forecast.

Prediction addresses this timing gap. It does not reserve a bay or remove uncertainty.

### D03. Keep the assessed product focused

**Current decision / deferred extension.** Voice assistance was considered because a hands-free interface could reduce the physical interaction needed to use app functions. The team deferred it to concentrate on data, prediction and the recommendation workflow.

There is no runtime voice assistant or LLM agent controlling the current app. It is a possible later interface to the same functions, not part of the current novelty claim.

The current product also does not take parking payments, reserve bays or perform autonomous driving. Searching or navigating is not confirmation that the driver has parked.

## 2. The complete decision journey

There are two connected journeys: preparing trustworthy parking information and answering one driver's question.

```text
PREPARING THE INFORMATION

HDB / LTA / URA readings and reference data
        -> preserve the source evidence
        -> clean identities, values, locations and timestamps
        -> retain availability history and reviewed tariff rules
        -> support comparison, model work and later evaluation

ANSWERING A DRIVER

Starting location + destination + parking duration + preference mode
        -> shortlist nearby suitable carparks
        -> get a driving route to each carpark
        -> get a walking route from each carpark to the destination
        -> estimate each carpark's arrival time
        -> calculate the stay cost and obtain an arrival forecast
        -> check whether all required evidence is usable
        -> rank eligible options under the selected preference
        -> show the evidence, map and navigation handoff

If no forecast qualifies:
        -> consider a separately labelled current-reading fallback
        -> otherwise explain why no recommendation can be produced
```

This order is intentional. A ranking formula cannot make an unsupported price, failed route or invalid forecast trustworthy.

## 3. Inputs, arrival time and parking duration

### D04. Ask for information that changes the decision

**Current decision.** The search uses a starting location, destination, parking duration and preference mode. The starting location can come from a user-requested device fix or a manually selected place.

| Input | Why we need it |
|---|---|
| Starting location | Determines the driving route and estimated arrival at each carpark. |
| Destination | Determines the nearby search area and the walk after parking. |
| Parking duration | Determines the total estimated charge. |
| Preference mode | Determines how the driver wants the trade-offs prioritized. |

Manual selection remains available when location permission is denied or the device cannot obtain a usable fix. GPS improves convenience; it is not a prerequisite for using search.

### D05. Use a separate arrival time for every carpark

**Current decision.** We predict availability at the carpark, where the parking decision matters. We do not use a single arrival time at the final destination for every candidate.

Driving to the carpark and walking from it are different parts of the journey. The walk affects convenience, but it does not delay the moment when the driver needs a free parking lot.

Candidates use a common departure assumption after route information has been gathered. This avoids giving one option a different assumed departure merely because its network request was processed earlier.

### D06. Separate time until arrival from time spent parked

**Current decision.** These answer different questions:

| Time | Example | Purpose |
|---|---|---|
| Driving / time until carpark arrival | 20 minutes | Determines the prediction target. |
| Parking duration | 2 hours | Determines the charging period. |
| Walking after parking | 6 minutes | Describes access to the destination. |

A two-hour stay does not require a two-hour-ahead availability forecast if the driver reaches the carpark in twenty minutes.

### D07. Treat the current search as an immediate trip

**Current decision.** The implemented flow derives arrival from the route and a near-immediate departure assumption. It is not a scheduled future booking interface in which the user selects an arbitrary future arrival date.

Older notes discussed optional intended arrival. That proposal should not be confused with a currently implemented scheduled-trip input.

## 4. Why we retain HDB, LTA and URA

### D08. Use complementary sources instead of assuming one feed contains everything

**Current decision.** The providers overlap, but their useful fields are not identical.

| Source | Main contribution to our project |
|---|---|
| HDB availability | Available car lots, capacity from the same reading, and a source update time. |
| HDB reference data | Address, location and facility/policy information such as short-term hours and parking system. |
| LTA DataMall | Wider availability coverage, including records labelled HDB, URA and LTA, plus location/name evidence where published. |
| URA availability | Direct URA lot-count readings. |
| URA details | Carpark details, geometry, reference capacity and tariff fields. |
| Reviewed pricing publications | HDB charging policies and selected operator facts that availability feeds alone do not supply. |

We kept HDB even after obtaining LTA access because coverage overlap does not replace HDB's source timestamps and synchronized capacity. Those fields are especially useful for evaluating freshness and building model features.

We retained URA because availability alone does not solve pricing. Its details feed provides another part of the comparison problem.

**Collection coverage and prediction coverage are separate.** Collecting all three providers does not mean all three currently enter the app's forecast ranking.

## 5. Why cleaning, identity and timestamps matter

### D09. Give a carpark a stable identity

**Current decision.** We identify a carpark by its agency and code, while separately retaining which feed supplied a reading.

An HDB carpark appearing in both HDB and LTA data is not two physical carparks, and their counts must not be added together. Similarly, matching names are not enough to prove that two records describe exactly the same facility.

The initial mappings use exact agency/code matches. Ambiguous facilities or aggregate locations need review rather than a guessed merge.

### D10. Distinguish when a value was measured from when we received it

**Current decision.** We preserve the provider's observation time where supplied, our retrieval time, and the time at which our collector knew the observation.

Example: a reading measured at 10:00 but first received at 10:03 was not information available to a prediction made at 10:01.

This protects model evaluation from future-information leakage. It also prevents the app from calling an old reading “fresh” merely because it was downloaded recently.

LTA and URA availability readings lack the same per-carpark source timestamp and synchronized capacity available in HDB's direct payload. We retain their retrieval time as a proxy and label it accordingly. We do not invent a measurement time or factual capacity.

Reference capacity from a different capture can be useful background evidence, but it is not automatically the correct denominator for a later availability reading. We retain its source and time rather than manufacture an occupancy percentage from unrelated measurements.

### D11. Preserve unknowns and reject contradictions

**Current decision.** Cleaning is intended to make records interpretable, not make every row look complete.

| Situation | Our interpretation |
|---|---|
| Zero available lots, valid positive capacity | A reported full carpark. |
| Missing count | Unknown, not full and not empty. |
| Negative or invalid count | Unusable evidence. |
| Available lots exceeding synchronized capacity | A contradiction to reject or quarantine, not silently clamp. |
| Identical repeated source observation | One observation seen again, not another independent training example. |
| Conflicting counts for the same source instant | A conflict requiring exclusion/review, not an arbitrary choice. |
| Multiple or conflicting location points | Not automatically a verified entrance. |

We keep source evidence and quality flags so a doubtful result can be investigated. For primary training series, copies of HDB/URA readings in LTA's feed are excluded to avoid duplicated evidence.

### D12. Separate identity, history, metadata, tariffs and provenance

**Current decision.** These facts change at different rates and answer different questions. A carpark identity can remain stable while availability changes frequently and a tariff changes occasionally.

Separating them allows us to retain history, update a price without rewriting observations, and explain where a result came from. A large table row count is not the same as a large number of physical carparks or usable training examples.

## 6. What our prediction means

### D13. Predict the chance of at least one free car lot

**Current decision.** The supplied trained model is a classifier. Its output is the estimated probability that at least one car lot will be free at arrival.

That target fits the driver's immediate question: “am I likely to find a place?” It avoids presenting a precise future lot count that this particular model does not produce.

This is the model we integrated, not evidence that we proved classification universally better than count prediction. Earlier collection/export contracts also supported a future lot-count target; they describe a different possible model output.

> A value of 0.96 means an estimated 96% chance of at least one free lot. It does not mean 96 spaces, 96% of the carpark being empty, or a guarantee for this driver.

We show the current reported count separately because users can reasonably want both the latest observation and the future estimate.

### D14. Use recent conditions together with historical patterns

**Current decision.** The HDB model combines the current reading, reading age, recent changes/lagged readings, arrival horizon and time-related patterns. The supplied model uses LightGBM with probability calibration.

The product rationale is to consider both where the carpark is now and how conditions usually develop. A busy time slot alone cannot describe a recent change, while one current reading alone cannot describe the future.

We reuse the teammate's trained model and its input contract rather than build a second, inconsistent feature pipeline in the app backend. The detailed claim that this model family outperformed other families would require the model owner's comparative evidence; it is not established by successful integration.

### D15. Keep probability bands distinct from certainty

**Working policy.** The current model card uses High at 0.99 or above, Medium from 0.90 to below 0.99, and Low below 0.90.

These are labels for probability ranges. They are not a separate measurement of how certain the model is about its own answer, and they are not uncertainty intervals.

Other drivers, source delays, unusual events and uncertainty in travel time remain relevant. A free-lot forecast is not a reservation or a count of spaces that belong to our users.

## 7. Why prediction coverage is deliberately limited

### D16. Integrate HDB forecasts first

**Current decision.** The active forecast ranking is restricted to HDB. It is the provider supported by the integrated model, and its direct readings offer useful timestamp/capacity information.

URA/LTA experiments exist, but their input conditions differ. In particular, retrieval-time readings should not silently become equivalent to source-timestamped HDB history. The recorded URA transfer evaluation has limited day-type coverage, while the LTA negative-outcome sample is particularly small.

Our choice is to keep collecting useful data while limiting the deployed prediction claim to the cohort actually integrated. The current app does not rank HDB forecasts together with URA/LTA current counts as if those values measured the same thing.

With the HDB forecast configuration enabled, its shortlist and current-reading fallback are drawn from HDB candidates. Broader provider collection does not imply that URA/LTA options are automatically included in that fallback.

### D17. Keep the enabled forecast horizon at 15-90 minutes

**Working policy.** The original held-out targets were 15, 30, 45, 60 and 90 minutes. The integration accepts the continuous 15-90-minute range, but each intermediate horizon has not been independently validated here.

We have not enabled under-15-minute forecasts or historical-profile forecasts in the app ranking. The separate profile estimates describe recurring historical patterns; they should not silently stand in for a recent-condition forecast when live evidence is unsuitable.

A prospective short-trip pilot produced mixed and incomplete evidence. That supported keeping these restrictions while providing a clearly labelled current-reading option where permitted, rather than widening the forecast claim immediately.

This horizon limit concerns time until arrival, not parking duration.

### D18. Require at least a 0.90 predicted chance before forecast ranking

**Working policy.** This threshold follows the current supplied model card and separates candidates that pass the arrival-probability requirement from those that do not.

It expresses a conservative operating preference: price and convenience should be compared after a minimum predicted chance has been met. The 0.90 value is a chosen threshold, not a proof of a guaranteed 90% real-world success rate.

The same principle explains why an invalid model response, wrong carpark identity, wrong target time or excessively old history prevents a forecast from entering the ranking.

## 8. Why pricing is a rule calculation

### D19. Store charging rules rather than one universal hourly rate

**Current decision.** The meaningful comparison is the estimated total cost for the user's intended stay. Charging can change with entry time, day category, payment method, free periods, billing units, tiers and supported caps.

Consequently, a price is a calculation using a carpark's applicable rules. It is not simply a fixed attribute such as “this carpark costs $1.20 per hour.”

The database stores the conditions and source evidence. The calculator applies them to the particular stay. We do not store a separate ready-made answer for every possible arrival and duration.

### D20. Start the priced stay at the estimated carpark arrival

**Current decision.** If the driver needs twenty minutes to reach a carpark, the relevant tariff may differ from the tariff at the moment they pressed Search.

Pricing therefore uses each carpark's route-derived arrival and the requested parking duration. This also explains why two nearby carparks can require different price calculations for the same destination search.

All day/time decisions use Singapore local time, and holiday treatment is considered only where the loaded calendar and tariff interpretation support it.

### D21. Withhold a price if part of the stay is unsupported

**Current decision.** A plausible-looking estimate can wrongly make an unpriced option look cheapest. Missing or ambiguous tariff windows therefore remain unavailable; they do not become zero-cost parking.

We quote supported reviewed rules and retain a calculation breakdown. A tariff source being present does not mean every possible stay is calculatable. Observed holidays, uncertain first-entry rules or unconfirmed cap/boundary treatment can prevent a quote.

We retain schedule versions because refreshing a tariff should not erase which rule was used previously. Availability collection also does not count as a new review of every operator's pricing policy.

### D22. Disclose minute precision and use the higher supported neighbouring estimate

**Current decision.** Routes produce second-level ETAs while the current calculator uses whole minutes. We calculate the two neighbouring minute starts.

If both are supported under the same schedule and payment method, we retain their lower and higher estimates. If they differ, the app can show the range and ranking uses the higher amount. If the two starts do not share supported matching rules, we withhold the price.

The purpose is to avoid favouring a candidate because of a favourable minute-rounding choice. It is not a guarantee that the real charge must fall inside this range; actual billing, arrival and departure can differ.

## 9. Why eligibility comes before scoring

### D23. Apply non-negotiable evidence checks before preference trade-offs

**Current decision.** A candidate needs usable routes, a supported stay price and usable availability evidence for the selected comparison basis. The shortlist also excludes known unsuitable ordinary-parking cases such as loading bays and HDB facilities with no short-term parking.

Only after those conditions are met do we compare cost and convenience. This prevents a very cheap option from compensating for a failed route or an unsupported forecast.

In forecast mode, a carpark being full now does not automatically exclude it: a valid qualifying future probability can make it relevant. Conversely, a carpark having spaces now does not rescue a known low arrival probability.

An honest empty result is allowed. “We cannot produce a supported recommendation” is preferable to an invented bargain or a fake availability estimate.

## 10. Why there are three preference modes

### D24. Offer three understandable trade-off profiles

**Current decision.** The app offers:

| Mode | Intended meaning |
|---|---|
| Best overall | A default compromise with cost and walking given the largest relative influences. |
| Prioritise cheaper | Give price substantially greater influence while retaining the other factors. |
| Prioritise closer | Give the walk from parking to the destination substantially greater influence. |

The rationale is that there is no single best trade-off for every visit. A driver willing to walk can favour cost, while someone carrying shopping may place greater value on a short walk.

Presets make those choices explicit without requiring the driver to configure four numerical sliders. They also give us understandable policies to test and explain. This is a design rationale, not the result of a recorded usability study proving three is the optimal number of modes.

Availability remains relevant in all modes, and all modes retain the same eligibility checks. We did not introduce a mode that deliberately trades away those checks.

**“Closer” refers to the walk after parking, not simply the shortest drive.** Driving remains a separate factor.

### D25. Use “prioritise” rather than promise a strict minimum

**Current decision, with a historical difference to confirm.** All three implemented modes use weighted scoring. Therefore Prioritise cheaper does not guarantee the absolute cheapest eligible carpark, and Prioritise closer does not guarantee the absolute shortest walk.

Other factors can outweigh a small price or walking difference. A mode called “Lowest Cost” would imply different behaviour: sort by price first and use other factors only to break ties.

Some early notes proposed those strict single-priority modes. The current three weighted profiles must not be presented as if they implement that older proposal. Before the presentation, the team should agree that the current softer preference meaning is the intended one.

Changing a mode clears the previous results and requires a new search. This avoids leaving the driver looking at results produced by the previous preference. Remembering the selected mode across app restarts is not established by the current implementation.

## 11. How we chose the scoring weights

### D26. Make the trade-offs explicit and auditable

**Working policy.** These are the current profiles:

| Mode | Cost | Walking | Availability | Driving |
|---|---:|---:|---:|---:|
| Best overall | 0.40 | 0.30 | 0.20 | 0.10 |
| Prioritise cheaper | 0.65 | 0.15 | 0.15 | 0.05 |
| Prioritise closer | 0.15 | 0.65 | 0.15 | 0.05 |

Each row totals 1.00. The weights express relative influence on comparable factor penalties. They are not percentages of a driver's budget, percentages of model accuracy or shares of available spaces.

We chose an interpretable weighted rule because it makes the project policy visible and allows us to inspect how a result changes. Learning a preference model would require labelled driver choices that we do not currently have. Availability observations alone cannot tell us how much a driver values saving $1 compared with walking an extra 400 metres.

### D27. Why Best overall uses 0.40 / 0.30 / 0.20 / 0.10

| Weight | Design rationale |
|---|---|
| **Cost 0.40** | Cost is a direct, visible consequence of the parking choice. Giving it the largest influence makes the default budget-conscious while still allowing convenience and availability to affect the result. |
| **Walking 0.30** | A cheap carpark can be inconvenient if the walk is long. This substantial second influence prevents the default from treating a large walking burden as nearly irrelevant. |
| **Availability 0.20** | Among candidates that already pass the minimum predicted-chance requirement, a higher chance remains preferable. The entry threshold handles the first layer of risk; this component differentiates the remaining choices. |
| **Driving 0.10** | Driving time is real user effort and also varies by access route. It receives a smaller influence because the search is already geographically bounded and the route duration is an estimate, while price and post-parking access are central visit trade-offs. |

This implements the ordering **cost > walking > availability > driving within the eligible cohort**. Cost and walking together receive 70% of the penalty budget; neither completely dominates the other.

The record supports this relative-priority rationale. It does not establish a unique scientific reason that cost must be exactly 0.40 rather than 0.39 or 0.45. The exact values were proposed during the implementation workflow, then checked for behaviour and sensitivity; they were not estimated from driver surveys or a trained preference model.

**A concrete meaning for 0.40:** if the normalized cost penalty worsens by 0.10 while everything else stays fixed, the Best overall score falls by four points. The same change in walking penalty costs three points, availability two, and driving one.

### D28. Why the focused modes use 0.65 / 0.15 / 0.15 / 0.05

The selected priority receives 65%, making the preference substantially stronger than in the default mode. The remaining 35% keeps other considerations visible. This is a focused compromise, not a pure price or distance sort.

The two profiles are symmetric: changing from cheaper to closer swaps the cost and walking weights. Availability stays at 15% and driving at 5%. That makes the policy easy to explain and avoids changing several unrelated priorities at once.

The exact 0.65, 0.15 and 0.05 values are designed starting points, not measured universal preferences. A plausible explanation for the policy is “make the chosen concern dominant, while retaining other considerations,” rather than “testing proved that 65% is the only correct value.”

### D29. Why availability is not necessarily the largest weight

Availability has **two roles**: a qualifying threshold and a ranking component. Looking only at the weight misses the threshold.

In probability mode, the availability penalty is `1 - predicted chance`. With the 0.90 entry threshold, qualifying probabilities range from 0.90 to 1.00. Consequently, the availability component can change the Best overall score by at most two points within that cohort. Moving from 90% to 99%, with all else unchanged, improves it by 1.8 points. In either focused mode, the corresponding improvement is 1.35 points.

That is a meaningful policy consequence: after a candidate clears the threshold, the current design permits cost and convenience to outweigh a modest improvement in predicted chance. The weights should be reviewed if the team wants the very highest qualifying probability to dominate more strongly.

Neither a 0.90 threshold nor a large availability weight can repair a poorly validated probability model. Model quality and preference policy are separate questions.

## 12. How different units become comparable

### D30. Convert raw factors into consistent penalties

**Working policy.** Dollars, metres, seconds and probabilities cannot be added directly. We first convert each to a penalty between zero and one, then apply the weights.

Lower penalties are better. The combined penalty is subtracted from one and multiplied by 100, producing a score where higher is preferable.

| Factor | Current comparison rule | Meaning |
|---|---|---|
| Cost | cost / (cost + reference stay cost) | A higher supported stay price is worse, with diminishing additional influence. |
| Walking | metres / (metres + 500) | A longer routed walk is worse. |
| Driving | seconds / (seconds + 900) | A longer drive is worse. |
| Forecast availability | 1 - predicted chance | A higher arrival probability is better. |
| Current-only availability | 1 / (1 + available lots) | More currently reported spaces is preferable, with diminishing returns. This is not an arrival probability. |

The current-only count rule prevents a very large reported count from overwhelming the comparison merely because the carpark is large. The probability rule uses the model's actual output instead of pretending that a count has the same meaning.

### D31. Use fixed reference points instead of rescaling to each shortlist

**Working policy.** The reference points are $4 per requested parking hour, 500 metres walking and 15 minutes driving. At a reference point, that factor's penalty equals 0.5.

For a two-hour stay, the cost reference is $8. This is a normalization device; the displayed charge remains the total stay cost. It does not turn a flat-entry tariff into an hourly billing rule.

Fixed points have a useful stability property: if two carparks' factors are unchanged, adding a third option does not change their individual scores. A method that normalizes against the cheapest/dearest or nearest/farthest item in the current list can change scores simply because an unrelated candidate was added.

This property concerns the score for unchanged candidates; the separate bounded shortlist can still change which candidates are considered.

The smooth rule avoids a hard cutoff where every walk beyond 500 metres, for example, receives exactly the same penalty. A longer walk continues to get worse.

The references are practical design settings, not scientifically established driver tolerances. **500 metres is a halfway comparison point, not a maximum walking filter.** Likewise, $4/hour is not a budget ceiling and 15 minutes is not the maximum allowed drive.

If scores are exactly tied, ordering is deterministic: the closer profile prefers the shorter walk then the lower cost, while the other profiles prefer the lower cost then the shorter walk. Driving time and canonical identity provide further tie-breaks. Full-precision values determine the order, so two scores that look equal after display rounding need not be a true tie. This makes repeated comparisons explainable instead of arbitrarily shuffling equal options.

## 13. A worked example of the three modes

This is an illustrative one-hour stay, not a live-data result or a user study. Assume all candidates pass the evidence checks, have a 20-minute drive and a 96% arrival probability. Only price and walking differ.

| Candidate | Estimated total stay cost | Routed walk | Driving | Arrival probability |
|---|---:|---:|---:|---:|
| A | $1.20 | 800 m | 20 min | 96% |
| B | $2.40 | 250 m | 20 min | 96% |
| C | $6.00 | 50 m | 20 min | 96% |

Using the current formula, the scores are:

| Candidate | Best overall | Prioritise cheaper | Prioritise closer |
|---|---:|---:|---:|
| A | 65.79 | **72.31** | 53.08 |
| B | **68.49** | 67.17 | 69.25 |
| C | 66.76 | 56.18 | **81.63** |

- Best overall selects B: the middle price avoids A's long walk without paying C's much higher charge.
- Prioritise cheaper selects A: the saving matters more under that profile.
- Prioritise closer selects C: its short walk receives substantially greater influence.

The arithmetic was checked against the current scoring function while preparing this record. The example explains the policy; it does not demonstrate that real drivers agree with these choices. Other live inputs can produce the same winner in all three modes.

**A score of 68.49 is not a 68.49% chance of finding parking.** The score describes suitability under the selected policy; the arrival probability is a separate field.

## 14. Why fallback is separate from prediction

### D32. Preserve a consistent meaning within each ranking

**Current decision.** A forecast and a current count answer different questions. We do not replace a missing forecast with a current count inside the same probability-based score.

When no forecast qualifies, an allowed failure reason and usable current evidence can produce a separate current-reading list. It carries a notice that conditions may change before arrival. If the model is deliberately not configured, the application can also operate explicitly in current-baseline mode.

| Situation | Intended handling |
|---|---|
| Forecast usable and qualifying | Use forecast-based ranking. |
| Forecast unavailable for an allowed reason; current evidence fresh and usable | Consider the separate current-only fallback if no forecast ranks. |
| Known forecast below the threshold | Do not bypass that result by promoting its current count. |
| Current evidence stale, missing or only an unconfirmed retrieval proxy | Do not describe it as a confirmed fresh source reading. |
| No usable complete comparison | Show no eligible recommendation with an explanation. |

Unknown future conditions are not the same as a known poor forecast. That distinction is why fallback is controlled rather than automatic in every failure case.

## 15. Maps, routes, shortlists and navigation

### D33. Use OneMap for place search and routing

**Current decision.** During integration, avoiding reliance on a Google Maps API billing setup was an explicit concern. We connected OneMap for Singapore place search and driving/walking routes instead.

This is a description of our chosen integration, not a promise about future provider pricing, quotas or terms. We still need an available service and valid credentials. Our backend can renew the OneMap REST token using server-side account credentials; the app does not depend on a developer's chat or MCP session to renew it.

The app credits the OneMap basemap. Opening a Google Maps directions link externally does not mean that our recommendation used Google's paid routing API.

### D34. Distinguish shortlisting distance from real routes

**Current decision.** Straight-line distance is a useful cheap first filter, but it can miss roads, entrances, crossings and walking barriers. We therefore obtain actual route estimates before scoring.

The default shortlist considers up to three nearby supported candidates within a 1.5 km straight-line radius. The backend allows at most five and a radius up to 3 km. Bounding the work limits the number of external routing calls and keeps the result manageable.

The exact defaults are practical scope/latency choices, not proof that three candidates or 1.5 km always finds the best option. Fewer than three, or none, may survive the checks. We claim a recommendation among the considered eligible options, not the global optimum over Singapore.

Published points and route estimates are not independently verified carpark entrances. We also do not claim that the current OneMap duration is a verified live-traffic forecast.

### D35. Hand off turn-by-turn navigation

**Current decision.** Our responsibility is choosing and explaining an option. We show the comparison map and let an external navigation app/browser handle the turn-by-turn journey.

This avoids duplicating a navigation system and keeps development focused. No background location tracking or automatic parking-session start is implied by the handoff.

## 16. Why the system is divided into these components

### D36. Separate information preparation, recommendation and model inference

**Current decision.** The collector builds persistent evidence; the recommendation backend combines facts for a search; the model service computes the forecast; the Android app handles interaction.

Searching does not start collection or retrain a model. This separation lets the model teammate collect/train independently while the search workflow remains understandable and testable.

There are two useful data paths: persistent history in the shared database, and the model service's recent HDB readings/history cached in memory. The latter supports responsive inference and current-reading fallback without requiring a database collection cycle for every search.

The model service periodically refreshes its feed and attempts history warm-up after restart. That cache is not a replacement for durable history, and successful artifact loading alone does not prove current predictions are usable.

### D37. Use PostgreSQL hosted by Supabase

**Current decision.** PostgreSQL is the database engine; Supabase hosts that database. They are not two separate databases that we synchronize.

The fit is structured shared data with relationships, timestamps, historical records and SQL views that present consistent training/comparison inputs. Hosted storage avoids requiring each teammate to maintain an independent authoritative database.

We should not claim to have run a formal database benchmark proving this superior to MySQL. Older MySQL references are historical and need reconciliation with the actual PostgreSQL setup.

Supabase is not currently the place where the whole app/model is deployed. The demonstrated API and model run on the development computer, with the Android device connecting to the API.

### D38. Keep the architecture small and replaceable

**Current decision.** We use focused routing, pricing, prediction and scoring components, coordinated by one recommendation control class. The existing trained inference service stays separate because it is the supplied model integration boundary.

The practical benefits are clear responsibilities and the ability to replace external calls with controlled fixtures. We did not add a large repository hierarchy, message broker or dependency container simply to make the project look more sophisticated.

Moving the orchestration into a concrete control class improved traceability to the design while preserving the public function used by existing callers. It did not require rewriting tariffs, model training or data collection.

Flutter remains the chosen client technology, with Android as the physical demo platform. Its practical benefit here is using the team's existing mobile UI while retaining a web route for development checks; no comparative framework study is asserted.

## 17. Accounts, privacy and local data

### D39. Keep driver search anonymous and separate operator access

**Current decision.** A driver does not need a server account to request this parking comparison. Mandatory driver registration would add friction and personal-data management without being necessary for the current search workflow.

The operator is a different responsibility. The current implementation checks one configured operator credential and keeps sign-in state for that app run. This fits the limited operator scope without introducing an additional role hierarchy.

However, a credential check and a client-side console gate are not a complete server-session/authorization system. The prototype admin actions must not be described as protected real database operations.

### D40. Minimize retained personal trip information

**Current decision / target for additional features.** Device location is requested through a foreground user action, with a manual-input alternative. Old device fixes are rejected rather than treated as the driver's current starting point.

We do not persist personal origins/destinations as search history on the backend. Public parking observations are a different category of data from a driver's journey. The forecast audit keeps carpark identity, forecast timing and outcomes, not the driver's origin/destination.

This does not mean location is never processed externally: the routing provider receives the coordinates needed for routing, and external navigation has its own behaviour. A deployment still needs appropriate privacy information and access controls.

Provider/database credentials remain on the backend, outside the Android bundle. Read-only transactions are used for recommendation reads, but a dedicated least-privilege runtime database login remains deployment work.

### D41. Prefer device-local personal features over mandatory cloud accounts

**Planned, partially implemented.** Saved places, preferences, favourites and session history were intended to remain on the device. That supports convenience without requiring a driver-account system or cloud synchronization.

Appearance mode currently persists locally. Several other controls still use prototype/in-memory state. In particular, vehicle type and maximum-walking controls visible in Preferences are not established as filters sent through the current recommendation request.

Do not confuse the 500 m scoring reference with a user walking limit. A screen showing a 400 m preference does not establish that the current backend enforces it.

Complete local-data erasure, saved-location persistence and reminder/history behaviour need verification and implementation beyond the current UI messages.

## 18. Sessions, reporting and operator decisions

### D42. Treat a parking session as an explicit driver action

**Planned product behaviour, current prototype.** A driver searching for a carpark, viewing it or opening navigation has not necessarily parked there. A real tracker should start only after an explicit action confirming the stay.

The current session manager holds one active stay in memory. This is a simple prototype boundary, not durable parking history or evidence that a parking payment occurred.

The tracker also uses a simple hourly-rate running-cost calculation. That is not the same source-backed tariff engine used for recommendation quotes. We must not describe its running amount as a validated bill under all tariff rules.

### D43. Use reporting and overrides to address source-data problems

**Planned / policy proposal.** Public feeds can be wrong or slow to reflect closures or corrected prices. Reports and operator review are intended to provide a controlled correction path with a reason and an audit trail.

The proposed policy carried forward for review is: a closure excludes a candidate, while a verified rate correction can leave it eligible using the corrected supported tariff. It is not sensible to assume that every kind of correction means the carpark is unusable.

Backend enforcement of these overrides is not implemented in the current recommendation flow. The prototype panel includes additional force-open/full statuses whose final semantics still need agreement. A force-open label should not be interpreted as proof of free lots or silently bypass prediction/evidence requirements.

Likewise, prototype API-health displays and refresh/report controls are not proof of live monitoring, a protected refresh endpoint or durable report storage.

## 19. How we validate the system

### D44. Ask different tests to answer different questions

**Current decision.** We separate:

| Question | Appropriate evidence |
|---|---|
| Does the application implement its rules correctly? | Unit, workflow, boundary, basis-path, widget and integration tests. |
| Does the availability model make useful future estimates? | Held-out/prospective outcomes, compared with a baseline and broken down by conditions. |
| Do the ranking weights match driver preferences? | Driver-choice/preference evidence, plus sensitivity analysis. |
| Does the complete Android demo work on our phone? | Actual installation and on-device checks. |

Success in one category does not establish success in the others. In particular, data arriving from APIs and all software tests passing do not prove optimal ranking weights.

### D45. Record a forecast before observing its outcome

**Current decision.** Prospective evaluation records the forecast, issue time, target arrival, model version and known history before the target occurs. Later provider readings are used to evaluate it.

Our current prospective matcher uses the first later observation at/after the target within a five-minute tolerance, retaining unmatched cases. Provider readings are the comparison evidence; they are not independently observed proof that an individual driver found a suitable bay at the exact second of arrival.

For the probability model, Brier score measures how far the probability is from the later free/not-free outcome; lower is better. We compare against persistence: the simple assumption that a currently free/full carpark stays in that state. Paired comparisons use the same matched cases.

Earlier discussions called this “regression testing.” More precisely, it is predictive evaluation; software regression testing separately checks that code changes preserve behaviour.

### D46. Preserve a clear boundary between the supplied training process and our audit

**Current decision.** The model teammate has an independent historical HDB backfill/file-based training path. Our database/export tools provide persistent collected evidence, but the shipped model should not be described as trained exclusively from our Supabase tables.

Time-aware features and chronological validation are important because random splitting of nearby time-series readings can overstate performance. We read the teammate's held-out results, but did not independently reproduce raw-data parity/held-out training results without the ignored archives.

The prospective pilot on 17 October issued 576 forecasts and matched 297 later readings. Almost half remained unmatched, results varied by subgroup, and the 15-minute matched subset was very small. These limits explain why the pilot did not immediately justify enabling short/profile forecasts.

### D47. Test ranking behaviour and expose sensitivity

**Current decision.** The recorded studies checked bounded scores, sensible response to each factor, deterministic ties and stability under changes to weights and forecasts. The probability study includes 20,000 generated cases, 120,000 property comparisons, 15,000 weight-perturbation trials and 15,000 probability-perturbation trials.

These checks support claims such as “making only the price worse does not improve the score.” They also exposed close trade-offs that can change winner under modest changes. We did not interpret a desired winner in a constructed scenario as a measured human preference.

The Lab 4 evidence recorded 88 documented cases, 151 backend test methods, 108 model unit/service tests and 44 Flutter tests on 26 October, plus an Android build and a live workflow check. These are dated records, not a statement that the latest build has been rerun or tested on a physical phone today.

### D48. Keep displayed results consistent with the inputs that produced them

**Current decision.** Editing a selected place invalidates its old coordinates, and changing the preference or search inputs clears obsolete comparison results. A result map retains the locations belonging to that result rather than silently reading newly edited form fields.

We also guard duplicate submissions and ignore late responses after leaving the relevant screen. These choices prevent a successful network response from being shown against the wrong trip, or repeated taps from closing/navigating the wrong screen. Recoverable failures leave a retry/manual-input path instead of inventing a result.

Small-screen, keyboard, map-error and repeated-navigation checks support those interactions. They do not establish that no device-specific Android failure remains.

## 20. Important numerical policies in one place

These values serve different purposes. A probability threshold, a stale-data limit, a scoring reference and a search radius should not be described as the same kind of “confidence setting.”

| Setting | Current value | Reason / interpretation |
|---|---|---|
| Best overall weights | 0.40 / 0.30 / 0.20 / 0.10 | Explicit default trade-off; see section 11. |
| Focused-mode priority | 0.65, with 0.15 / 0.15 / 0.05 for the remaining factors | Stronger selected preference, not a strict single-factor sort. |
| Cost reference | $4 per requested parking hour | Halfway point for the normalized cost penalty, not a tariff or budget cap. |
| Walking reference | 500 m | Halfway comparison point, not a maximum walking filter. |
| Driving reference | 900 seconds / 15 minutes | Halfway comparison point, not the forecast horizon limit. |
| Minimum ranked arrival probability | 0.90 | Current model-card-aligned qualifying policy, not a guaranteed success rate. |
| High probability-band boundary | 0.99 | Label from the current model card, not a separate certainty estimate. |
| Enabled forecast horizon | 15-90 minutes | Current integration cohort; original evaluated targets were 15/30/45/60/90. |
| Recent source/history age | Up to 15 minutes for model/current-fallback use | Limits reliance on stale observations; not a provider freshness guarantee. |
| Device-fix age | Up to 2 minutes | Avoid routing from an old position; manual selection remains available. |
| Periodic collection default | Every 5 minutes | Practical history/API-workload balance; collecting faster does not force the provider to update. |
| Model-service current cache/poll | Approximately 60 seconds | Reuse current HDB readings without fetching afresh for every candidate. |
| Model-service memory history | Approximately 75 minutes | Supports the recent-history features and warm-up; not durable storage. |
| Prospective outcome-match tolerance | First source observation at/after target, within 5 minutes | Avoid arbitrary long-gap labels and retain missing outcomes. |
| Default candidate shortlist | Up to 3 within 1.5 km | Bound route calls and comparison scope. |
| Backend shortlist limits | Up to 5 candidates, radius up to 3 km | Bounded request work, not a promise that five qualify. |
| Requested stay limit | 1-1,440 minutes | Current request/calculator scope, separate from time until arrival. |
| URA tariff review/capture guard | Generally 2 days in the calculator | Freshness requirement tied to the daily refresh workflow. |
| Other tariff review guard | Generally 30 days in the calculator | Avoid indefinite reliance on an old reviewed policy. |
| Holiday-calendar scope | Loaded 2026 coverage | Other years need appropriate calendar coverage before quoting. |

The age/cadence/scale defaults are operational or design policies; the record does not contain experiments proving each exact number is optimal. We can explain the purpose of each without inventing that evidence.

Writing this record does not refresh the database or renew pricing evidence. For example, late-September policy facts may require review by the time this record is read if no later review has occurred. Check actual dates before a demo rather than disabling the safeguards.

## 21. How the project changed over time

| Earlier direction or wording | Current interpretation |
|---|---|
| Current availability was the common interim basis. | Arrival probability is now integrated for the supported HDB cohort; current readings remain separate evidence/fallback. |
| A future model might predict a number of free lots. | The shipped model predicts the chance of at least one free car lot. |
| Four modes or literal Lowest Cost / Shortest Walk were proposed. | The working app has three weighted profiles, named Best overall / Prioritise cheaper / Prioritise closer. |
| Optional manually intended arrival was discussed. | The implemented immediate-trip flow derives each arrival from its route. |
| Five results were described in earlier requirements. | The implementation defaults to a shortlist of three and permits at most five; fewer can qualify. |
| Driver login/register screens existed. | Driver search is anonymous; operator access is separate. |
| MySQL or an operator web console appeared in older notes. | The working database is PostgreSQL on Supabase, and the operator entry is in the Flutter app. |
| A conceptual OperatorAccount with roles was shown. | The prototype checks one configured operator credential; a complete server-account/session/authorization design is not implemented. |
| Preferences/vehicle limits/session history appeared as complete product features. | The planned scope is broader than the connected search; several controls remain prototypes. |
| “Cost” could be read as an hourly rate. | Recommendation cost is a supported total-stay estimate; the prototype tracker still has a separate simple hourly calculation. |
| A generic cost/walking/current-count score was used. | Forecast mode uses the probability penalty; the count penalty remains only for explicit current-only comparisons. |
| A previous report used a 0.5 free threshold. | The current model card and ranking integration use 0.9. Threshold-dependent historical results must be regenerated or labelled clearly. |

This ledger records the differences; it does not claim that every old document has already been updated or that every changed policy was formally minuted.

## 22. What is working and what remains a target

| Area | Current scope |
|---|---|
| HDB/LTA/URA collection and cleaning | Implemented; regular operation is owned separately from driver searches. |
| Persistent carpark evidence and tariff storage | Implemented; coverage, freshness and review conditions still apply. |
| Arrival-aware HDB prediction integration | Implemented within the enabled provider/mode/horizon cohort. |
| Source-backed recommendation cost engine | Implemented for supported rules and stays; not every published tariff or special case. |
| Three ranking modes | Connected through search and scoring, including the separately labelled current fallback. |
| Foreground device location, map and external navigation | Connected; actual device acceptance remains a separate verification activity. |
| Appearance preference | Persisted on the device. |
| Vehicle-specific filtering and user walking-limit enforcement | Visible/intended controls, not established as connected backend search filters. |
| Saved places, favourites, durable session/history and complete erasure | Planned or partly prototype; do not infer persistence/completeness from labels or success messages. |
| Parking tracker | One in-memory active session and a simple hourly running-cost estimate; not the full tariff engine. |
| Operator credential check and console entry gate | Implemented; complete authenticated server-side administration is not. |
| Real reports, effective overrides, health/refresh backend operations | Not complete; prototype panel interactions are not live enforcement. |
| Voice assistant, payments and reservations | Outside the current implemented scope. |

The safe product claim is that we have a working connected search/recommendation workflow with explicit limits. A completed screen does not establish that its planned backend or persistence exists.

## 23. Evidence limits and decisions to confirm

These are internal review points to resolve before turning this record into presentation claims:

1. **Weighted preference semantics:** confirm that Prioritise cheaper/closer is intended, rather than the strict minimum-cost/minimum-walk behaviour in some older notes.
2. **Weights and reference points:** confirm the three profiles as the team's selected initial policy. To claim empirically preferred values, collect driver-choice evidence and evaluate on choices not used to tune them.
3. **Risk preference after the threshold:** decide whether the current two-point maximum availability influence in Best overall is the desired trade-off among qualifying forecasts.
4. **Model evidence:** align the historical 0.5 versus current 0.9 threshold descriptions. Do not describe tests of code integration as a new held-out accuracy result.
5. **Cohort expansion:** obtain representative evidence before enabling under-15-minute, profile or URA/LTA forecasts. Keep the mixed, partly unmatched pilot in context.
6. **Provider labels and rates:** retain source-versus-retrieval distinctions and verify live freshness/review dates before demonstration.
7. **Prototype promises:** reconcile Preferences text, tracker amounts, erasure messages and operator-panel controls with what is actually enforced and persisted.
8. **Overrides:** agree on closure, corrected-rate, force-open and full-cap semantics before connecting them to recommendation eligibility.
9. **Deployment and privacy:** distinguish the laptop/USB demo from an HTTPS deployment with dedicated database permissions and complete operator sessions.
10. **Final demonstration:** rerun the selected build on the actual Android device and record the real demo video. The 26 October evidence does not substitute for that.

The positive framing is: **we chose explicit policies, tested the logic and investigated sensitivity; further preference and predictive validation can refine those policies.** This is stronger than claiming an exact number was scientifically determined when the record does not support that claim.

## 24. Concise explanations for a presentation

These are possible explanations of decisions, not a prescribed slide order or final script.

| Question | Defensible explanation |
|---|---|
| Why prediction? | “The driver needs a space when they arrive, so we evaluate availability at each carpark's estimated arrival time rather than relying only on the latest count.” |
| Why three modes? | “Different visits involve different cost-versus-walking priorities. We offer three clear trade-off profiles instead of requiring drivers to configure numerical weights.” |
| Why cost 0.40? | “We made cost the largest influence in our budget-conscious default, with walking close behind so a cheap option cannot ignore convenience. The values express our initial design policy, and we checked their behaviour and sensitivity.” |
| Why not give availability the biggest weight? | “A minimum predicted chance is checked before ranking. Within that qualifying group, we still reward higher probability while allowing price and convenience to decide the trade-off.” |
| Why 0.65 for cheaper/closer? | “It makes the selected priority substantially stronger while retaining the other considerations. These are priority modes, not claims of an absolute minimum.” |
| Why keep all three data sources? | “They overlap in coverage but provide different useful evidence. HDB gives source timestamps and synchronized capacity; other feeds add coverage and tariff/reference information.” |
| Why not one hourly price? | “The total charge depends on when the stay starts, how long it lasts and which charging rules apply. We calculate that stay and withhold unsupported estimates.” |
| Why a separate fallback? | “Current readings and future probabilities are different evidence. We keep their rankings clearly separated instead of making a missing prediction look like a successful forecast.” |
| Why OneMap plus external navigation? | “We use Singapore place search and routes for comparison, then hand turn-by-turn navigation to an external app so we can focus on the parking decision.” |
| Why separate collection and inference? | “Historical evidence, live forecasts and driver searches have different responsibilities. Keeping them separate lets us collect and evaluate data without retraining or collecting everything for each search.” |
| What did testing establish? | “It checks that the rules behave consistently and shows where small changes can affect a choice. Model accuracy and driver preference require their own evidence.” |
| What is our strongest claim? | “An explainable arrival-oriented parking comparison that combines supported stay costs, routed access and availability evidence, with clear handling when that evidence is insufficient.” |

Avoid replacing these explanations with claims of user-survey support, guaranteed spaces, universal pricing coverage, optimal weights or live administrative enforcement unless the team has the corresponding evidence and implementation.

## 25. Supporting project records

These links are for verification or deeper reading. The rationale above can be followed without reading source code.

| Record | What it supports |
|---|---|
| [Current backend overview](backend/README.md) | Connected workflow, ranking modes and scope limits. |
| [Runtime architecture](backend/ARCHITECTURE.md) | Component boundaries, request lifecycle and privacy/deployment status. |
| [Data contract](data-pipeline/DATA-CONTRACT.md) | Canonical identity, timestamps, cleaning, deduplication and source differences. |
| [Database guide](data-pipeline/SCHEMA.md) | What is stored and why; its row counts are explicitly dated. |
| [Collection instructions](data-pipeline/PERIODIC-COLLECTION.md) | Cadence, ownership and collector operating behaviour. |
| [Scoring rationale and original study](backend/validation/SCORING-VALIDATION.md) | Default rationale, fixed scales, mathematical and sensitivity checks; distinguish the older count policy. |
| [Current scoring configuration](backend/scoring.py) | Exact mode weights, penalty formula and deterministic tie handling. |
| [Probability-score study](backend/validation/results/probability-scoring.json) | Separate probability-policy behaviour and perturbation results. |
| [Model integration record](backend/MODEL-INTEGRATION.md) | Model output, enabled cohort, threshold discrepancy and validation limitations. |
| [Supplied HDB model overview](ml/README.md) | Model training/inference scope and published interpretation. |
| [Current model card](ml/models/model_card.json) | Model version, feature names and probability thresholds. |
| [URA/LTA experiment overview](ml_lta_ura/README.md) | Experimental transfer scope and limited provider evidence. |
| [Short-trip pilot](backend/validation/SHORT-TRIP-PILOT.md) | Why mixed prospective evidence did not automatically widen the integration cohort. |
| [Pricing calculator](backend/pricing.py) | Implemented guards, day/time rules, payment and cap behaviour. |
| [Recommendation workflow](backend/recommendation.py) | Shortlisting, eligibility, candidate-specific arrival, minute estimates and fallback. |
| [Device location](parkchoice_flutter/lib/services/device_location.dart) | Foreground location and freshness/error handling. |
| [Prototype session manager](parkchoice_flutter/lib/services/parking_session_manager.dart) | In-memory session and simple hourly running-cost boundary. |
| [Lab 4 traceability](lab4/TRACEABILITY.md) | Requirements, implementation, tests and unfinished areas. |
| [Recorded Lab 4 cases](lab4/evidence/test-results.json) | Dated executed cases, graph verification and source hashes. |
| [Recorded platform checks](lab4/evidence/platform-checks.json) | Dated model/Flutter/build evidence and pending device/video work. |

This record documents reasoning and context. It makes no database, pricing, model, code-behaviour or deployment changes and does not constitute a fresh live-service check.
