#!/usr/bin/env python3
"""
solve.py — VELARA launch-readiness audit.

Reads the four monthly tracker extracts + dashboard, cross-checks them against the reference tabs,
and prints ONE JSON object (findings + risk_ranking) to stdout.

Usage:
    python3 solve.py <pack_dir> [out_dir]

If out_dir is given, findings.csv and risk_ranking.csv are also written there.
All diagnostics go to stderr. Rules are derived from the data (no hardcoded country names).
"""
import csv
import json
import math
import os
import re
import sys

import pandas as pd

C_COUNTRY, C_STATUS, C_SKU, C_DOSE = "Country", "Launch Status", "SKU", "Dose"
C_SUB, C_TGT, C_APP = "Actual Submission Date", "Target Approval Date", "Actual Approval Date"
C_EXP, C_ACT = "Expected Launch Shipment Date", "Actual Launch Shipment Date"
C_DEM, C_PATH, C_ROUTE, C_SITE, C_ROLE = (
    "Demand Strategy", "Regulatory Pathway", "Supply Route", "Packaging Site", "Site Role")
C_PLY, C_PLD = "Product Code Set Up At Plant?", "Plant Setup Date"
C_WHY, C_WHD = "Product Code Set Up At Warehouse?", "Warehouse Setup Date"
C_DLY, C_DLD = "Demand Loaded In Planning System?", "Demand Loaded Date"
C_LOG, C_REF = "Shipment Date Change Log", "RefreshDate"
DATE_COLS = ["Planned Submission", C_SUB, C_TGT, C_APP, C_EXP, C_ACT, C_PLD, C_WHD, C_DLD, C_REF]
KEY = [C_COUNTRY, C_SKU]


def log(*a):
    print(*a, file=sys.stderr)


def is_yes(v):
    return isinstance(v, str) and v.strip().lower() == "yes"


def blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT or (
        isinstance(v, str) and not v.strip())


def serial_to_ts(x):
    return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(x))


def load(pack_dir):
    sheets = pd.read_excel(os.path.join(pack_dir, "VELARA_tracker.xlsx"), sheet_name=None)
    raw, clean = {}, {}
    tabs = sorted(k for k in sheets if re.match(r"Tracker_\d{4}_\d{2}$", k))
    numeric_cols = set()
    for k in tabs:
        df = sheets[k].copy()
        raw[k] = df.copy()
        for c in DATE_COLS:
            if c in df.columns and pd.api.types.is_numeric_dtype(df[c]) and df[c].notna().any():
                numeric_cols.add(c)
                df[c] = df[c].map(lambda x: serial_to_ts(x) if not pd.isna(x) else pd.NaT)
        clean[k] = df
    return sheets, raw, clean, tabs, numeric_cols


def norm_country(df):
    df = df.copy()
    df[C_COUNTRY] = df[C_COUNTRY].astype(str).str.strip()
    return df


def main(pack_dir, out_dir=None):
    sheets, raw, clean, tabs, numeric_cols = load(pack_dir)
    latest = tabs[-1]
    cur = norm_country(clean[latest])
    today = cur[C_REF].max()
    log("latest", latest, "today", today.date())

    ref_c = sheets["Ref_Countries"].copy()
    ref_c.columns = ["country", "vol", "tier", "site"]
    ref_c["country"] = ref_c["country"].astype(str).str.strip()
    vol = ref_c.set_index("country")["vol"].to_dict()
    ref_sku = set(sheets["Ref_SKUs"]["SKU"])
    ref_sku_dose = sheets["Ref_SKUs"].set_index("SKU")["Dose"].to_dict()
    sites = sheets["Ref_Sites"].copy()
    sites.columns = ["site", "loc", "lead_wk", "cap", "status"]
    lead_days = {r.site: int(r.lead_wk) * 7 for r in sites.itertuples()}
    cap = {r.site: r.cap for r in sites.itertuples()}

    dash = pd.read_csv(os.path.join(pack_dir, "dashboard_status.csv"))
    countries = list(dash["country"].astype(str).str.strip())
    for c in ref_c["country"]:
        if c not in countries:
            countries.append(c)

    F = []  # findings

    def add(code, where, proof):
        where = sorted(set(where))
        if where:
            F.append({"what": code, "where": ";".join(where), "proof": proof[:200]})

    # ---------------- cleaning / hygiene findings (all tabs) ----------------
    ws, drift, invalid, dup = set(), set(), set(), set()
    for k in tabs:
        r = raw[k]
        ws |= {str(c).strip() for c in r[C_COUNTRY] if str(c) != str(c).strip()}
        st = r[C_STATUS].astype(str)
        base = st.str.strip().str.lower()
        common = base.mode().iat[0]
        for c, s_raw, b in zip(r[C_COUNTRY].astype(str).str.strip(), st, base):
            if b == common and s_raw != "Active" and common == "active":
                drift.add(c)
            elif b != common:
                invalid.add(c)
        d = norm_country(clean[k])
        g = d[d.duplicated(KEY, keep=False)]
        for (c, sku), grp in g.groupby(KEY):
            if len(grp.drop_duplicates()) > 1:
                dup.add(c)
    add("COUNTRY_NAME_WHITESPACE", ws, "Name has trailing space in some monthly tabs, splitting the market in a group-by")
    add("STATUS_VALUE_DRIFT", drift, "Launch Status is 'Active' with inconsistent casing/whitespace (active / ACTIVE / trailing space)")
    add("STATUS_INVALID_ENTRY", invalid, "Launch Status holds a non-status value ('Invalid Entry') on a row of an otherwise active market")
    add("DATE_STORED_AS_NUMBER", numeric_cols, "Column loads as Excel serial integers in at least one monthly tab; converted to dates")
    add("DUPLICATE_ROW", dup, "Same market+SKU appears twice in one extract with conflicting expected shipment dates")

    bad_sku = cur[~cur[C_SKU].isin(ref_sku)]
    add("SKU_NOT_IN_REFERENCE", bad_sku[C_COUNTRY], "SKU(s) " + ",".join(sorted(set(bad_sku[C_SKU]))) + " missing from Ref_SKUs")

    # ---------------- work on de-duplicated latest extract ----------------
    cur = cur.drop_duplicates(KEY, keep="last").reset_index(drop=True)
    direct = cur[C_ROUTE].astype(str).str.strip().str.lower() == "direct"
    primary = cur[C_ROLE].astype(str).str.strip().str.lower() == "primary"
    mts = cur[C_DEM].astype(str).str.strip().str.upper() == "MTS"
    national = cur[C_PATH].astype(str).str.strip().str.lower() == "national"
    shipped = cur[C_ACT].notna()

    # approval
    m = national & cur[C_APP].notna() & cur[C_SUB].notna() & (cur[C_APP] < cur[C_SUB])
    add("APPROVAL_BEFORE_SUBMISSION", cur[m][C_COUNTRY],
        "National-pathway approval date precedes own filing date (Reliance/Mutual Recognition markets excluded: legitimate)")
    m = cur[C_APP].isna() & (cur[C_TGT] < today)
    approval_missing = set(cur[m][C_COUNTRY])
    add("APPROVAL_TARGET_NOT_ACTUAL", approval_missing,
        "Target approval date already passed on %s but Actual Approval Date is blank" % today.date())

    # readiness blanks (direct markets only; Via Hub blanks are legitimate)
    flags = [(C_PLY, C_PLD), (C_WHY, C_WHD), (C_DLY, C_DLD)]
    m = direct & cur[[C_PLY, C_DLY]].isna().any(axis=1)
    add("BLANK_TREATED_AS_PASS", cur[m][C_COUNTRY],
        "Direct-supply market never answered plant/demand readiness (blank, not No); dashboard counts silence as yes")
    m = direct & cur[C_DLY].isna() & cur[C_DLD].isna()
    never_loaded = set(cur[m][C_COUNTRY])
    add("DEMAND_NEVER_LOADED", never_loaded, "No demand-loaded flag or date in any extract for a direct-supply market")
    m = pd.Series(False, index=cur.index)
    for fy, fd in flags:
        m |= direct & cur[fy].map(is_yes) & cur[fd].isna()
    add("FLAG_YES_BUT_NO_DATE", cur[m][C_COUNTRY], "Readiness flag is Yes but its setup/load date is blank (direct-supply market)")

    # demand loaded too late
    lead = cur[C_SITE].map(lead_days)
    cur["_dl_ready"] = cur[C_DLD] + pd.to_timedelta(lead, unit="D")
    m = cur[C_DLD].notna() & ~shipped & (cur["_dl_ready"] > cur[C_EXP])
    add("DEMAND_LOADED_TOO_LATE", cur[m][C_COUNTRY], "Demand loaded + site lead time lands after the expected shipment date")

    # setup after shipment (primary sites only; secondary sites are set up after launch by design)
    m = primary & ~shipped & (((cur[C_PLD] > cur[C_EXP])) | (cur[C_WHD] > cur[C_EXP]))
    add("SETUP_DATE_AFTER_SHIPMENT", cur[m][C_COUNTRY], "Primary-site plant/warehouse setup falls after expected shipment (Secondary sites excluded by design)")

    # shipment before approval: MTS only (MTO may ship into bonded warehouse)
    appdate = cur[C_APP].fillna(cur[C_TGT])
    m = mts & (((cur[C_EXP] < appdate) & ~shipped) | (cur[C_ACT] < cur[C_APP]))
    add("SHIPMENT_BEFORE_APPROVAL", cur[m][C_COUNTRY], "MTS market expects/ships before approval; MTO bonded-warehouse pattern excluded")

    m = ~shipped & (cur[C_EXP] < today)
    add("DATE_PASSED_NO_REPLAN", cur[m][C_COUNTRY], "Expected shipment date already passed with no actual shipment")
    m = shipped.eq(False) & cur[C_EXP].lt(today) & False
    # shipment missing: expected date passed, nothing shipped (same condition; claimed only if distinct)
    # (left to DATE_PASSED_NO_REPLAN to avoid double counting)

    # starting dose
    doses = sorted(set(ref_sku_dose.values()), key=lambda d: int(re.sub(r"\D", "", d)))
    start_dose = doses[0]
    drow = cur[C_DOSE].astype(str).str.upper()
    claim = cur.groupby(C_COUNTRY)[C_EXP].min()
    startd = cur[drow == start_dose].groupby(C_COUNTRY)[C_EXP].min()
    late_start = {c for c in claim.index if c in startd.index and startd[c] > claim[c]}
    add("STARTING_DOSE_UNAVAILABLE", late_start, "%s initiation-dose pack ships later than the market's other packs; patients cannot start" % start_dose)
    add("ROLLUP_ANY_NOT_ALL", late_start, "Dashboard reads market ready when any pack is ready, but initiation-dose pack is not")

    # plant capacity: site over its annual capacity -> name the unshipped markets in its most congested quarter
    # [lead-ref: R4-Q02-b911] shortfall / daily build rate = extra days, applied to launches after the capacity cut-off
    cap_bad, cap_delay = [], {}
    shipped_c = set(cur[shipped][C_COUNTRY])
    for site, g in ref_c.groupby("site"):
        tot = g["vol"].sum()
        if site in cap and tot > cap[site]:
            extra = int(math.ceil((tot - cap[site]) / (cap[site] / 365.0)))
            # [lead-ref: R4-Q19-a343] sequence by earliest possible ship date: demand load (or extract date) + site lead time
            def earliest(c):
                rows = cur[cur[C_COUNTRY] == c]
                ds = [r[C_ACT] if pd.notna(r[C_ACT]) else (r[C_DLD] if pd.notna(r[C_DLD]) else today) + pd.Timedelta(days=lead_days.get(r[C_SITE], 0))
                      for _, r in rows.iterrows()]
                return min(ds)
            seq = sorted((c for c in g["country"] if c in claim.index), key=earliest)
            run = 0
            for c in seq:
                run += vol[c]
                if run > cap[site] and c not in shipped_c:
                    cap_bad.append(c)
                    cap_delay[c] = extra
            log("capacity exceeded", site, tot, cap[site], "extra days", extra, "after cut-off", cap_bad)
    add("PLANT_CAPACITY_EXCEEDED", cap_bad, "Site need exceeds annual capacity; launches after the cut-off slip by shortfall/daily build rate")

    # ---------------- unrecorded date moves across extracts ----------------
    first_exp, drift_days, moved = {}, {}, set()
    prev, prev_dup = None, set()
    for k in tabs:
        full = norm_country(clean[k])
        dupkeys = set(map(tuple, full[full.duplicated(KEY, keep=False)][KEY].values))
        d = full.drop_duplicates(KEY, keep="last").set_index(KEY)
        if prev is not None:
            for idx in d.index.intersection(prev.index):
                if idx in dupkeys or idx in prev_dup:
                    continue
                a, b = prev.at[idx, C_EXP], d.at[idx, C_EXP]
                if pd.notna(a) and pd.notna(b) and a != b and blank(d.at[idx, C_LOG]):
                    moved.add(idx[0])
        prev, prev_dup = d, dupkeys
    base_tab = norm_country(clean[tabs[0]]).drop_duplicates(KEY, keep="last")
    b_claim = base_tab.groupby(C_COUNTRY)[C_EXP].min()
    for c in moved:
        drift_days[c] = int((claim[c] - b_claim[c]).days)
    add("DATE_MOVED_WITHOUT_RECORD", moved,
        "Expected shipment date moved between monthly extracts with no Shipment Date Change Log entry (logged moves excluded)")

    # ---------------- slippage per country ----------------
    def row_real(r, use):
        """earliest feasible date for one row under the selected set of constraints"""
        d = r[C_EXP]
        ld = lead_days.get(r[C_SITE], 0)
        if r[C_ACT] is not pd.NaT and pd.notna(r[C_ACT]):
            return d
        if "setup" in use and str(r[C_ROLE]).strip().lower() == "primary":
            for c in (C_PLD, C_WHD):
                if pd.notna(r[c]):
                    d = max(d, r[c])
        if "demand" in use and pd.notna(r[C_DLD]):
            d = max(d, r[C_DLD] + pd.Timedelta(days=ld))
        if "never" in use and str(r[C_ROUTE]).strip().lower() == "direct" and blank(r[C_DLD]) and not is_yes(r[C_DLY]):
            d = max(d, today + pd.Timedelta(days=ld))
        if "approval" in use and str(r[C_DEM]).strip().upper() == "MTS" and blank(r[C_APP]) and pd.notna(r[C_TGT]):
            if r[C_TGT] >= today:
                d = max(d, r[C_TGT])
        return d

    def launch_real(g, use):
        reals = g.apply(lambda r: row_real(r, use), axis=1)
        sd = g[g[C_DOSE].astype(str).str.upper() == start_dose]
        floor = reals.min()
        if "dose" in use and len(sd):
            return max(reals[sd.index].min(), floor)
        return floor

    causes = [
        ("DEMAND_NEVER_LOADED", {"never"}),
        ("DEMAND_LOADED_TOO_LATE", {"demand"}),
        ("SETUP_DATE_AFTER_SHIPMENT", {"setup"}),
        ("SHIPMENT_BEFORE_APPROVAL", {"approval"}),
        ("STARTING_DOSE_UNAVAILABLE", {"dose"}),
    ]
    all_use = {"never", "demand", "setup", "approval", "dose"}
    ranking = []
    for c in countries:
        g = cur[cur[C_COUNTRY] == c]
        if g.empty:
            ranking.append(dict(country=c, slippage_days=0, driver="NONE", evidence="no tracker rows"))
            continue
        cl = g[C_EXP].min()
        total = max(0, (launch_real(g, all_use) - cl).days)
        parts = {}
        for code, use in causes:
            parts[code] = max(0, (launch_real(g, use) - cl).days)
        # unrecorded drift is housekeeping only: slippage exists only once a claimed date is behind RefreshDate
        if c in cap_delay:
            parts["PLANT_CAPACITY_EXCEEDED"] = cap_delay[c]
            total += cap_delay[c]
        driver = "NONE"
        if total > 0:
            driver = max(parts, key=lambda k: parts[k])
        ev = {
            "NONE": "no problem found" if c not in approval_missing else "approval target passed, no ship-date effect",
            "DATE_MOVED_WITHOUT_RECORD": "expected ship date pushed %d days across Jan-Apr extracts with no change-log entry; claimed %s" % (drift_days.get(c, 0), cl.date()),
            "PLANT_CAPACITY_EXCEEDED": "site over annual capacity; launch falls after the capacity cut-off, +%d days (shortfall / daily build rate)" % cap_delay.get(c, 0),
            "STARTING_DOSE_UNAVAILABLE": "%s pack ships %s vs market claim %s; no patient can start before it" % (start_dose, startd.get(c, pd.NaT).date() if c in startd.index else "?", cl.date()),
            "DEMAND_NEVER_LOADED": "demand never loaded; earliest = today + site lead time; claimed %s" % cl.date(),
            "DEMAND_LOADED_TOO_LATE": "demand loaded + site lead time later than claimed %s by %d days" % (cl.date(), total),
            "SETUP_DATE_AFTER_SHIPMENT": "plant/warehouse setup after claimed ship %s; earliest = setup date" % cl.date(),
            "SHIPMENT_BEFORE_APPROVAL": "MTS cannot ship before target approval; claimed %s, earliest = approval target" % cl.date(),
        }[driver]
        ranking.append(dict(country=c, slippage_days=int(total), driver=driver, evidence=ev[:300]))

    for r in ranking:
        r["impact_score"] = int(r["slippage_days"] * float(vol.get(r["country"], 0)))
    ranking.sort(key=lambda r: (-r["impact_score"], -r["slippage_days"], -float(vol.get(r["country"], 0))))
    for i, r in enumerate(ranking, 1):
        r["rank"] = i
    ranking = [{k: r[k] for k in ("country", "rank", "slippage_days", "impact_score", "driver", "evidence")} for r in ranking]

    out = {"findings": F, "risk_ranking": ranking}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "findings.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, ["what", "where", "proof"])
            w.writeheader()
            w.writerows(F)
        with open(os.path.join(out_dir, "risk_ranking.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, ["country", "rank", "slippage_days", "impact_score", "driver", "evidence"])
            w.writeheader()
            w.writerows(ranking)
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
