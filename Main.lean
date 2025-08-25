set_option linter.unusedVariables false

structure Issuer where
  is_debarred : Bool
  has_debarred_directors : Bool
  is_fraudulent : Bool
  is_fugitive : Bool
  has_outstanding_convertibles : Bool
  has_esop_exemption : Bool
  has_sar_exemption : Bool
  has_mandatory_convertibles : Bool
  net_tangible_assets : List Nat
  monetary_asset_ratio : Nat
  used_monetary_assets : Bool
  is_offer_for_sale_only : Bool
  operating_profits : List Nat
  net_worths : List Nat
  changed_name_recently : Bool
  percent_revenue_from_new_name : Nat
  uses_book_building : Bool
  qib_allocation_done : Bool
  is_tech_firm : Bool
  sr_net_worth : Nat
  sr_holder_exec : Bool
  sr_voting_ratio : Nat
  sr_class_count : Nat
  sr_same_face_value : Bool
  sr_issued_3mo_prior : Bool
  applied_to_stock_exchange : Bool
  has_demat_agreement : Bool
  promoter_securities_demat : Bool
  no_partly_paid_shares : Bool
  finance_75_percent_done : Bool
  general_corp_purpose_ratio : Nat
  shares_fully_paid : Bool
  shares_held_duration_months : Nat
  is_govt_entity : Bool
  via_merger_scheme : Bool
  is_bonus_from_free_reserve : Bool
  underlying_held_1y : Bool
  bonus_not_from_revaluation : Bool

  /-- A rule with metadata (for audit/explanations) and a computable check. -/
structure ComplianceRule where
  id         : String          -- e.g. "SEBI ICDR 6(1)(b)"
  title      : String          -- short human title
  reference  : String          -- e.g. "ICDR 6(1)(b), 2018 (as amended)"
  check      : Issuer → Bool   -- machine-checkable predicate
  failReason : Issuer → String -- natural-language reason
  remedy?    : Option String   -- optional suggestion

/-- Pretty result of one rule. -/
structure RuleResult where
  id        : String
  title     : String
  reference : String
  passed    : Bool
  reason?   : Option String     -- present when failed
  deriving Repr

/-- Evaluate a single ComplianceRule against an Issuer. -/
def runRule (i : Issuer) (r : ComplianceRule) : RuleResult :=
  let ok := r.check i
  { id := r.id
  , title := r.title
  , reference := r.reference
  , passed := ok
  , reason? := if ok then none else some (
      r.failReason i ++ match r.remedy? with
                        | some s => "\nSuggested remedy: " ++ s
                        | none   => ""
    )
  }

/-- Helpers for common checks on lists of numbers (₹ in paise units). -/
def allGeNat (xs : List Nat) (n : Nat) : Bool :=
  xs.all (fun x => x ≥ n)

def lengthIs {α} (xs : List α) (k : Nat) : Bool :=
  xs.length == k


/-- Ruleset adapted from SEBI ICDR Regulations (anchors in comments). -/
def ruleset : List ComplianceRule :=
[
  -- Disqualifiers: ICDR 5(1)(a–d) + 5(2) carve-outs
  { id := "SEBI ICDR 5(1)"
  , title := "No debarments/defaulter/fraudulent/fugitive"
  , reference := "ICDR 5(1)"
  , check := fun i =>
      (!i.is_debarred)
      && (!i.has_debarred_directors)
      && (!i.is_fraudulent)
      && (!i.is_fugitive)
  , failReason := fun i =>
      let hits :=
        [ if i.is_debarred            then "Issuer/affiliates debarred" else ""
        , if i.has_debarred_directors then "Promoter/Director debarred" else ""
        , if i.is_fraudulent          then "Wilful defaulter / fraudulent borrower" else ""
        , if i.is_fugitive            then "Fugitive economic offender" else ""
        ].filter (fun s => s ≠ "")
      "Disqualifying condition(s): " ++ String.intercalate "; " hits
  , remedy? := some "Resolve disqualifications (expiry of debarment, remedial orders) before filing."
  },

  { id := "SEBI ICDR 5(2)"
  , title := "No outstanding convertibles (with ESOP/SAR/MandConv carve-outs)"
  , reference := "ICDR 5(2)"
  , check := fun i =>
      (!i.has_outstanding_convertibles)
      || i.has_esop_exemption
      || i.has_sar_exemption
      || i.has_mandatory_convertibles
  , failReason := fun _ =>
      "Outstanding convertibles/rights exist without falling under ESOP/SAR pre-exercise or mandatory conversion carve-outs."
  , remedy? := some "Ensure ESOPs/SARs are exercised pre-RHP and mandatory convertibles are converted by filing."
  },

  -- Eligibility 6(1)(a): NTA ≥ ₹3 cr each year AND ≤50% monetary assets unless used/committed OR OSF-only
  { id := "SEBI ICDR 6(1)(a)"
  , title := "Net tangible assets ≥ ₹3 cr; monetary assets ≤ 50% (or committed use) / OSF carve-out"
  , reference := "ICDR 6(1)(a)"
  , check := fun i =>
      let ntaOK  := (lengthIs i.net_tangible_assets 3) && allGeNat i.net_tangible_assets 30000000
      let moneyOK := (i.monetary_asset_ratio ≤ 50) || i.used_monetary_assets || i.is_offer_for_sale_only
      ntaOK && moneyOK
  , failReason := fun i =>
      let ntaMsg :=
        if !(lengthIs i.net_tangible_assets 3) then
          "Need 3 full-year NTA figures."
        else if !(allGeNat i.net_tangible_assets 30000000) then
          "Each year’s net tangible assets must be ≥ ₹3.0 crore."
        else ""
      let moneyMsg :=
        if i.is_offer_for_sale_only then "" else
        if i.monetary_asset_ratio > 50 && !i.used_monetary_assets then
          "Monetary assets exceed 50% of NTA without evidence of committed/actual use."
        else ""
      String.intercalate " " (["", ntaMsg, moneyMsg].filter (· ≠ ""))
  , remedy? := some "Demonstrate firm commitments/use of monetary assets, or restructure to OSF-only; ensure each NTA year ≥ ₹3 cr."
  },

  -- Eligibility 6(1)(b): avg operating profit ≥ ₹15 cr with profit in each of preceding 3 years
  { id := "SEBI ICDR 6(1)(b)"
  , title := "Operating profit: ≥ ₹15 cr in each of the last 3 years"
  , reference := "ICDR 6(1)(b)"
  , check := fun i =>
      (lengthIs i.operating_profits 3) && allGeNat i.operating_profits 150000000
  , failReason := fun i =>
    if !(lengthIs i.operating_profits 3) then
      "Need 3 full-year operating profit figures."
    else
      -- zipIdx: (value, index)
      let fails := i.operating_profits.zipIdx |>.filter (fun (x, idx) => x < 150000000)
      let years := fails.map (fun (_, idx) => s!"Year {idx + 1}")
      "Operating profit below ₹15 cr in: " ++ String.intercalate ", " years

  , remedy? := some "Demonstrate ≥ ₹15 cr operating profit in each of the last 3 full financial years (restated, consolidated)."
  },

  -- Eligibility 6(1)(c): net worth ≥ ₹1 cr in each of preceding 3 full years
  { id := "SEBI ICDR 6(1)(c)"
  , title := "Net worth: ≥ ₹1 cr in each of the last 3 years"
  , reference := "ICDR 6(1)(c)"
  , check := fun i =>
      (lengthIs i.net_worths 3) && allGeNat i.net_worths 10000000
  , failReason := fun i =>
    if !(lengthIs i.net_worths 3) then
      "Need 3 full-year net worth figures."
    else
      let fails := i.net_worths.zipIdx |>.filter (fun (x, idx) => x < 10000000)
      let years := fails.map (fun (_, idx) => s!"Year {idx + 1}")
      "Net worth below ₹1 cr in: " ++ String.intercalate ", " years
  , remedy? := some "Increase equity/retained earnings to meet ≥ ₹1 cr in each of the last 3 full years."
  },

  -- Eligibility 6(1)(d): name-change revenue condition
  { id := "SEBI ICDR 6(1)(d)"
  , title := "If name changed within 1 year: ≥50% revenue from new-line activity"
  , reference := "ICDR 6(1)(d)"
  , check := fun i =>
      (!i.changed_name_recently) || (i.percent_revenue_from_new_name ≥ 50)
  , failReason := fun i =>
      if i.changed_name_recently && i.percent_revenue_from_new_name < 50 then
        "Changed name within 1 year but <50% revenue from new-name activity in the preceding full year."
      else
        "Condition not met."
  , remedy? := some "Demonstrate ≥50% revenue from the activity indicated by the new name or defer filing."
  },

  -- General conditions (partial): Reg 7(1)(a–e) & 7(2) caps (lightweight checks on data we already track)
  { id := "SEBI ICDR 7(1)"
  , title := "Listing application, demat agreements, promoter holdings fully demat, no partly-paid"
  , reference := "ICDR 7(1); 7(2)"
  , check := fun i =>
      i.applied_to_stock_exchange
      && i.has_demat_agreement
      && i.promoter_securities_demat
      && i.no_partly_paid_shares
      && (i.general_corp_purpose_ratio ≤ 25)
  , failReason := fun i =>
      let msgs :=
        [ if !i.applied_to_stock_exchange     then "No in-principle listing approval applied." else ""
        , if !i.has_demat_agreement          then "No depository agreement executed." else ""
        , if !i.promoter_securities_demat    then "Promoter securities not fully in demat." else ""
        , if !i.no_partly_paid_shares        then "Outstanding partly-paid equity exists." else ""
        , if i.general_corp_purpose_ratio > 25 then "General corporate purposes exceed 25% cap." else ""
        ].filter (· ≠ "")
      String.intercalate " " msgs
  , remedy? := some "Obtain in-principle approvals, execute depository agreements, demat promoter holdings, forfeit/fully pay partly-paid shares, cap GCP ≤ 25%."
  }
]

/-- Run the ruleset and collect results. -/
def runAll (i : Issuer) : List RuleResult :=
  ruleset.map (runRule i)

/-- Compute overall eligibility: all rules that are applicable pass. -/
def overallEligible (results : List RuleResult) : Bool :=
  results.all (·.passed)

/-- Render a human-readable report. -/
def renderReport (results : List RuleResult) : String :=
  let (passed, failed) := results.partition (·.passed)
  let header := if failed.isEmpty then "✅ Eligible: All applicable rules satisfied\n"
                else "❌ Not Eligible: some rules failed\n"
  let showOne (r : RuleResult) : String :=
    if r.passed then
      s!"✅ {r.id} — {r.title}"
    else
      s!"❌ {r.id} — {r.title}\nReason: {r.reason?.getD "(no detail)"}\nRef: {r.reference}"
  header ++
  "\n— Failed —\n" ++ (if failed.isEmpty then "(none)\n" else String.intercalate "\n\n" (failed.map showOne)) ++
  "\n\n— Passed —\n" ++ (if passed.isEmpty then "(none)\n" else String.intercalate "\n" (passed.map showOne))

/-- Convenience: run and print. -/
def explainAll (i : Issuer) : String :=
  renderReport (runAll i)


-- def eligible_ipo (i : Issuer) : Bool :=
--   ¬i.is_debarred ∧
--   ¬i.has_debarred_directors ∧
--   ¬i.is_fraudulent ∧
--   ¬i.is_fugitive ∧
--   (¬i.has_outstanding_convertibles ∨ i.has_esop_exemption ∨ i.has_sar_exemption ∨ i.has_mandatory_convertibles) ∧
--   (i.net_tangible_assets.all (λ x => x ≥ 30000000) ∧ (i.monetary_asset_ratio ≤ 50 ∨ i.used_monetary_assets) ∨ i.is_offer_for_sale_only) ∧
--   (i.operating_profits.all (λ x => x ≥ 150000000)) ∧
--   (i.net_worths.all (λ x => x ≥ 10000000)) ∧
--   (¬i.changed_name_recently ∨ i.percent_revenue_from_new_name ≥ 50) ∨
--   (i.uses_book_building ∧ i.qib_allocation_done) ∧
--   (i.sr_net_worth ≤ 10000000000 ∧ i.is_tech_firm ∧ i.sr_holder_exec ∧ i.sr_issued_3mo_prior ∧ (2 ≤ i.sr_voting_ratio ∧ i.sr_voting_ratio ≤ 10) ∧ i.sr_class_count = 1 ∧ i.sr_same_face_value) ∧
--   i.applied_to_stock_exchange ∧ i.has_demat_agreement ∧ i.promoter_securities_demat ∧
--   i.no_partly_paid_shares ∧ i.finance_75_percent_done ∧ i.general_corp_purpose_ratio ≤ 25 ∧
--   (i.shares_held_duration_months ≥ 12 ∨ i.is_govt_entity ∨ i.via_merger_scheme ∨ (i.is_bonus_from_free_reserve ∧ i.underlying_held_1y ∧ ¬i.bonus_not_from_revaluation))

def red_herring_company : Issuer :=
{ is_debarred := false,
  has_debarred_directors := false,
  is_fraudulent := false,
  is_fugitive := false,
  has_outstanding_convertibles := true,
  has_esop_exemption := true,
  has_sar_exemption := false,
  has_mandatory_convertibles := false,
  net_tangible_assets := [1444453000, 1245410000, 1017140000],
  monetary_asset_ratio := 7,
  used_monetary_assets := false,
  is_offer_for_sale_only := false,
  operating_profits := [295329000, 242654000, 149189000],
  net_worths := [1493650000, 1280276000, 1043609000],
  changed_name_recently := false,
  percent_revenue_from_new_name := 0,
  uses_book_building := true,
  qib_allocation_done := true,
  is_tech_firm := false,
  sr_net_worth := 0,
  sr_holder_exec := false,
  sr_voting_ratio := 0,
  sr_class_count := 0,
  sr_same_face_value := true,
  sr_issued_3mo_prior := false,
  applied_to_stock_exchange := true,
  has_demat_agreement := true,
  promoter_securities_demat := true,
  no_partly_paid_shares := true,
  finance_75_percent_done := true,
  general_corp_purpose_ratio := 20,
  shares_fully_paid := true,
  shares_held_duration_months := 12,
  is_govt_entity := false,
  via_merger_scheme := false,
  is_bonus_from_free_reserve := false,
  underlying_held_1y := false,
  bonus_not_from_revaluation := true }

-- def failure_reasons (i : Issuer) : List String :=
--   []
--   ++ (if i.is_debarred then ["Debarred by SEBI or other regulators"] else [])
--   ++ (if i.has_debarred_directors then ["Promoter or director is debarred"] else [])
--   ++ (if i.operating_profits.length ≠ 3 ∨ ¬i.operating_profits.all (λ x => x ≥ 150000000)
--       then ["Operating profit for 3 years not ≥ ₹15 Cr"] else [])
--   ++ (if i.net_worths.length ≠ 3 ∨ ¬i.net_worths.all (λ x => x ≥ 10000000)
--       then ["Net worth for 3 years not ≥ ₹1 Cr"] else [])
--   ++ (if i.changed_name_recently ∧ i.percent_revenue_from_new_name < 50
--       then ["Changed name recently and <50% revenue from new name"] else [])

-- def explain_compliance (i : Issuer) : String :=
--   if eligible_ipo i then
--     "✅ Eligible: All conditions satisfied"
--   else
--     let fails := failure_reasons i
--     "❌ Not Eligible:\n" ++ String.intercalate "\n" (fails.map (λ r => "❌ " ++ r))


-- #eval explain_compliance red_herring_company
-- #eval explainAll red_herring_company

def main : IO Unit := do
  IO.println (explainAll red_herring_company)
