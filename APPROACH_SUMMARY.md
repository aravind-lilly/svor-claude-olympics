# VELARA approach summary

Status note: I used 19 of my 20 lead questions. Each rule below that a lead confirmed carries its reference tag. Rules with no tag come from the Column Guide, the reference tabs and the data.

## 1. How I cleaned the data

I read all four monthly copies and normalised them before comparing anything.
- Market names: United States carried a trailing space in the February and March copies, which would split it into two markets. I trimmed every name.
- Dates: the Expected Launch Shipment Date column in the March copy was stored as Excel serial numbers. I converted it back to real dates so the months compare cleanly.
- Duplicates: March had Colombia's 4mg vial pack twice with two different shipment dates. I kept one row per market and pack, and I ignored that pack when comparing March to its neighbours, so the duplicate could not look like a date move.
- Status: Malaysia's Launch Status drifted between Active, active, ACTIVE and variants with a trailing space. One Greece row says Invalid Entry, which is not a status.
- Reference checks: Vietnam has a 16mg pack that is not in the pack reference tab. All packaging sites agree with the country reference tab.
- I confirmed there are no placeholder dates, negative quantities, timezone-shifted timestamps or currency columns, so I claimed none of those codes.

"Today" is 25 April 2026, the refresh date of the April copy, and everything is judged as of that date.

## 2. How I worked out each slippage figure

Slippage is the real earliest date a market can start shipping, minus the earliest expected shipment date it currently claims. I measured a real date as the latest of every constraint that must be met, because they are all prerequisites running side by side, not steps added together. I did not add them up.

The constraints I applied:
- Starting dose. A patient starts on the 2mg dose, and readiness depends only on that pack [lead-ref: R4-Q05-42a7]. In 27 of 30 markets the 2mg pack is the earliest to ship. In Japan, Colombia and Denmark it ships 148 to 156 days after the other packs, so the market cannot actually start treating patients until then. Slippage is the 2mg date minus the earliest claimed date: Japan 156, Denmark 152, Colombia 148.
- Date drift. The United States and Spain each pushed their shipment date back 45 days in each of February, March and April, with no change-log entry. I flagged this as a move without record, but gave it no slippage days. The distribution lead confirmed the dashboard reads only the latest date and counts no delay for it [lead-ref: R4-Q18-f0fb]. The supply chain lead said slippage is zero while the claimed date is still after the refresh date, and that repeated pushes do not accumulate [lead-ref: R4-Q03-79eb, R4-Q07-8f66]. Both claim 2027 dates.
- Approval before shipment for make-to-stock markets. A make-to-stock market cannot ship before approval; only make-to-order markets may move stock into a bonded warehouse early [lead-ref: R4-Q13-9349]. Korea, Turkey and Romania expect to ship before their target approval date. Slippage is the target approval date minus the claimed ship date: Korea 71, Romania 66, Turkey 48. A normal market ships 34 to 87 days after approval, and only these three are negative.
- Demand never loaded. Malaysia and Vietnam never answered the plant and demand readiness questions in any of the four copies. The dashboard counted that silence as yes. With demand not loaded, the earliest possible date is the extract date plus the site's lead time (24 weeks at Brenner) [lead-ref: R4-Q15-c24e]: Malaysia 83 days, Vietnam 107.
- Demand loaded too late. Peru's demand was loaded in April with a 26-week lead time at Calderon, landing 18 days after its claim. Turkey and Romania are also late on this test, but their approval gap is larger, so it governs.
- Plant capacity. Calderon's markets need 6.76 million units against 6.26 million of annual capacity. The manufacturing lead's method is shortfall divided by the daily build rate, added to launches after the capacity cut-off [lead-ref: R4-Q02-b911]. That is 30 extra days. Sites share capacity across all their markets, and launches are sequenced by earliest possible ship date, which is demand load or extract date plus lead time, accumulating volume until annual capacity is used [lead-ref: R4-Q19-a343]. The launches past the cut-off are Japan, Finland and Estonia, so each gets 30 days. Japan's adds to its starting-dose delay, giving 186.
- Setup after shipment. Ireland, Czechia and Denmark are primary-site markets whose plant setup falls after their claimed shipment date. Ireland 29 days, Czechia 23. Denmark's dose delay is larger.

I checked the lead-time rule against history. For all 40 make-to-order rows that already shipped, the actual ship date is the demand-load date plus the site lead time plus 10 days. The manufacturing lead says there is no buffer [lead-ref: R4-Q15-c24e], so my slippage figures use the lead time alone. A 10-day buffer would add 10 days to Malaysia, Vietnam and Peru.

Impact is slippage days multiplied by year-one forecast volume. Markets with no problem get slippage 0, impact 0 and driver NONE. The ranking is by impact: Japan, Korea, Vietnam, Colombia, Malaysia, Turkey, Denmark, Romania, Ireland, Czechia, Finland, Peru and Estonia. The other 17 markets, including the United States and Spain, are 0.

## 3. What I decided not to flag, and why

- Approval dated before filing in Brazil, Portugal, Greece, Mexico, Hungary, Norway, Bulgaria and Slovakia. Their pathway is Reliance or Mutual Recognition, where this is expected. Only China and Croatia, which are National, were flagged [lead-ref: R4-Q09-0d2c].
- Shipment before approval in the 11 make-to-order markets. This is the normal bonded-warehouse pattern [lead-ref: R4-Q13-9349].
- Blank setup fields in Korea and Estonia. They are served through a regional hub, which holds those records [lead-ref: R4-Q12-8928].
- Plant or warehouse setup after launch at secondary sites (Brazil, Hungary, Bulgaria). Secondary sites are added after launch by design.
- Korea and Estonia's 120-day shipment move. It carries a change log entry, so it is recorded [lead-ref: R4-Q04-8a0b].
- The 10 markets with three pack rows instead of four. The Column Guide says markets sell different box types, so differing counts are explained.
- Greece's red light. Greece has approval and has shipped. Its slippage is 0 and the red appears to come from one row with an invalid status.
- Codes with no evidence in this data: currency mismatch, negative quantity, placeholder date, timezone drift, actual shipment missing, plus the remaining unsupported codes. I claimed none of them.

## 4. What I am least sure about

- Plant capacity. The lead did not say how to treat a market already delayed by another cause. I added the 30 days on top of Japan's dose delay. I used volumes from Ref_Countries for every market at the site, whether or not shipped. Ashford and Brenner sit at 80% of capacity and I did not flag them.
- Date drift. The leads agree it is housekeeping only, so the United States and Spain have no slippage. If the real impact counts the push itself, they would rank near the top.
- Approval missing in Japan, Colombia and Denmark. Their approval target passed with no actual approval. Their claimed ship dates are far after that target, so I added no slippage. The regulatory lead gave no typical lag and said to treat a blank actual date as not approved [lead-ref: R4-Q08-5754]. If approval takes longer than the data implies, that would change.
- Starting dose. The lead confirmed 2mg. I claimed both the starting-dose and the "any pack counts as ready" codes for the same three markets. The dashboard lead said the dashboard reads a market ready if any row passes [lead-ref: R4-Q06-e41c], but if only one code is correct, the other is a false claim.
- Malaysia and Vietnam assume demand loads at the extract date. The demand planner said nothing ships without an order [lead-ref: R4-Q14-4561], so the true delay could be longer.
- Germany, Japan and Canada show a warehouse flag of Yes with no setup date. I flagged them but gave no slippage. The distribution lead said the dashboard does not need a date with a Yes [lead-ref: R4-Q11-25f2], so this may not count as a defect.
- China and Croatia have approval dated before filing, so the approval may not be real. Their target dates are before their shipment dates, so I gave them no slippage.
