import Src.Core
open Src.Core

namespace Src.GeneratedRules_gpt_oss_v1


def generatedRuleset : List ComplianceRule := [
-- 1. Applicability: IPO, FPO, rights, QIP, etc.
  { id := "ICDR_3_scope",
    title := "Applicability: IPO, FPO, rights, QIP, etc.",
    reference := "ICDR_3_scope",
    check := fun _ => True,
    failReason := fun _ => "Scope check not implemented; assume issuer is in scope.",
    remedy? := none },

  -- 2. Reference date for eligibility
  { id := "ICDR_4_reference_date",
    title := "Reference date for meeting eligibility",
    reference := "ICDR_4_reference_date",
    check := fun _ => True,
    failReason := fun _ => "Reference date checks not modeled; assume eligibility.",
    remedy? := none },

  -- 3. Disqualification: debarred issuer/directors/promoters
  { id := "ICDR_5_1_a",
    title := "Disqualification: issuer/promoters/directors debarred",
    reference := "ICDR_5_1_a",
    check := fun i => !(i.is_debarred ∨ i.has_debarred_directors),
    failReason := fun i =>
      if i.is_debarred then "Issuer is debarred from capital markets."
      else if i.has_debarred_directors then "A director or promoter is debarred."
      else "Unknown debarment status.",
    remedy? := some "Remove debarment or wait until it expires." },

  -- 4. Disqualification: promoter/director of another debarred company
  { id := "ICDR_5_1_b",
    title := "Disqualification: promoter/director of another debarred company",
    reference := "ICDR_5_1_b",
    check := fun _ => True,
    failReason := fun _ => "Cross‑company debarment check not modeled; assume compliant.",
    remedy? := none },

  -- 5. Disqualification: fraudulent borrower
  { id := "ICDR_5_1_c",
    title := "Disqualification: fraudulent borrower",
    reference := "ICDR_5_1_c",
    check := fun i => !i.is_fraudulent,
    failReason := fun i => if i.is_fraudulent then "Issuer or promoter is a fraudulent borrower." else "",
    remedy? := some "Cease fraudulent activities and rectify records." },

  -- 6. Disqualification: fugitive economic offender
  { id := "ICDR_5_1_d",
    title := "Disqualification: fugitive economic offender",
    reference := "ICDR_5_1_d",
    check := fun i => !i.is_fugitive,
    failReason := fun i => if i.is_fugitive then "Promoter or director is a fugitive economic offender." else "",
    remedy? := some "Resolve fugitive status before filing." },

  -- 7. Outstanding convertibles/rights
  { id := "ICDR_5_2_core",
    title := "No outstanding convertibles/rights (pre‑IPO)",
    reference := "ICDR_5_2_core",
    check := fun i =>
      !(i.has_outstanding_convertibles ∧
        !(i.has_esop_exemption ∨ i.has_sar_exemption ∨ i.has_mandatory_convertibles)),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !(i.has_esop_exemption ∨ i.has_sar_exemption ∨ i.has_mandatory_convertibles) then
        "Outstanding convertibles/rights present without ESOP/SAR/mandatory conversion carve‑out."
      else "",
    remedy? := some "Resolve outstanding convertibles/rights or obtain relevant exemptions." },

  -- 8. Net tangible assets ≥ ₹3 cr each of last 3 years
  { id := "ICDR_6_1_a_nta",
    title := "NTA ≥ ₹3 cr in each of the last 3 years",
    reference := "ICDR_6_1_a_nta",
    check := fun i =>
      lengthIs i.net_tangible_assets 3 ∧ allGeNat i.net_tangible_assets 30000000,
    failReason := fun i =>
      if !lengthIs i.net_tangible_assets 3 then
        "Need NTA figures for 3 full years."
      else if !allGeNat i.net_tangible_assets 30000000 then
        "One or more NTA figures are below ₹3 cr."
      else "",
    remedy? := some "Provide NTA ≥ ₹3 cr for each of the last 3 full years." },

  -- 9. Monetary assets ≤ 50 % of NTA unless committed/used; OSF carve‑out
  { id := "ICDR_6_1_a_monetary",
    title := "Monetary assets ≤ 50 % of NTA (or committed/used; OSF carve‑out)",
    reference := "ICDR_6_1_a_monetary",
    check := fun i =>
      i.is_offer_for_sale_only ∨
      (i.monetary_asset_ratio ≤ 50 ∨ i.used_monetary_assets),
    failReason := fun i =>
      if i.is_offer_for_sale_only then ""
      else if i.monetary_asset_ratio > 50 && !i.used_monetary_assets then
        "Monetary assets exceed 50 % of NTA without evidence of use or commitment."
      else "",
    remedy? := some "Use or commit excess monetary assets, or restructure to OSF‑only." },

  -- 10. Operating profit ≥ ₹15 cr each of last 3 years
  { id := "ICDR_6_1_b",
    title := "Operating profit ≥ ₹15 cr in each of the last 3 years",
    reference := "ICDR_6_1_b",
    check := fun i =>
      lengthIs i.operating_profits 3 ∧ allGeNat i.operating_profits 150000000,
    failReason := fun i =>
      if !lengthIs i.operating_profits 3 then
        "Need operating profit figures for 3 full years."
      else if !allGeNat i.operating_profits 150000000 then
        "One or more operating profit figures are below ₹15 cr."
      else "",
    remedy? := some "Demonstrate ≥ ₹15 cr operating profit in each of the last 3 full years." },

  -- 11. Net worth ≥ ₹1 cr each of last 3 years
  { id := "ICDR_6_1_c",
    title := "Net worth ≥ ₹1 cr in each of the last 3 years",
    reference := "ICDR_6_1_c",
    check := fun i =>
      lengthIs i.net_worths 3 ∧ allGeNat i.net_worths 10000000,
    failReason := fun i =>
      if !lengthIs i.net_worths 3 then
        "Need net worth figures for 3 full years."
      else if !allGeNat i.net_worths 10000000 then
        "One or more net worth figures are below ₹1 cr."
      else "",
    remedy? := some "Increase equity/retained earnings to meet ≥ ₹1 cr in each of the last 3 full years." },

  -- 12. Name change revenue source
  { id := "ICDR_6_1_d",
    title := "Name change → ≥50 % revenue from new activity",
    reference := "ICDR_6_1_d",
    check := fun i => !i.changed_name_recently ∨ i.percent_revenue_from_new_name ≥ 50,
    failReason := fun i =>
      if i.changed_name_recently && i.percent_revenue_from_new_name < 50 then
        "Changed name within 1 year but <50 % revenue from new‑name activity."
      else "",
    remedy? := some "Demonstrate ≥50 % revenue from the activity indicated by the new name." },

  -- 13. QIB fallback when 6(1) not met
  { id := "ICDR_6_2_qib",
    title := "QIB fallback when 6(1) not met",
    reference := "ICDR_6_2_qib",
    check := fun _ => True,
    failReason := fun _ => "6(1) satisfaction not modeled; assume QIB fallback not required.",
    remedy? := none },

  -- 14. SR equity shares conditions
  { id := "ICDR_SR_core",
    title := "SR equity shares conditions",
    reference := "ICDR_SR_core",
    check := fun i =>
      (i.sr_net_worth == 0) ∨
      (i.is_tech_firm ∧ i.sr_holder_exec ∧
        (i.sr_voting_ratio ≥ 2 ∧ i.sr_voting_ratio ≤ 10) ∧
        i.sr_class_count == 1 ∧ i.sr_same_face_value ∧ i.sr_issued_3mo_prior),
    failReason := fun i =>
      if i.sr_net_worth == 0 then ""
      else
        let msgs := [
          if !i.is_tech_firm then "SR issuer is not a technology‑intensive firm." else "",
          if !i.sr_holder_exec then "SR holder is not an executive of the issuer." else "",
          if !(i.sr_voting_ratio ≥ 2 ∧ i.sr_voting_ratio ≤ 10) then "SR voting ratio not in 2:1–10:1 range." else "",
          if i.sr_class_count != 1 then "More than one SR class issued." else "",
          if !i.sr_same_face_value then "SR shares do not have same face value as ordinary shares." else "",
          if !i.sr_issued_3mo_prior then "SR shares not issued at least 3 months before DRHP." else ""
        ]
        String.intercalate " " (msgs.filter (· ≠ "")),
    remedy? := some "Ensure all SR conditions are satisfied." },

  -- 15. Apply to stock exchange
  { id := "ICDR_7_1_a",
    title := "Apply to stock exchange (in‑principle)",
    reference := "ICDR_7_1_a",
    check := fun i => i.applied_to_stock_exchange,
    failReason := fun i => if !i.applied_to_stock_exchange then "Issuer has not applied to a stock exchange." else "",
    remedy? := some "Apply to a stock exchange and designate one." },

  -- 16. Depository agreement
  { id := "ICDR_7_1_b",
    title := "Depository agreement executed",
    reference := "ICDR_7_1_b",
    check := fun i => i.has_demat_agreement,
    failReason := fun i => if !i.has_demat_agreement then "Depository agreement not executed." else "",
    remedy? := some "Execute a depository agreement." },

  -- 17. Promoters’ holdings dematerialised
  { id := "ICDR_7_1_c",
    title := "Promoters’ holdings fully in demat",
    reference := "ICDR_7_1_c",
    check := fun i => i.promoter_securities_demat,
    failReason := fun i => if !i.promoter_securities_demat then "Promoter‑held securities not fully dematerialised." else "",
    remedy? := some "Dematerialise all promoter‑held securities." },

  -- 18. No partly‑paid equity outstanding
  { id := "ICDR_7_1_d",
    title := "No partly‑paid equity outstanding",
    reference := "ICDR_7_1_d",
    check := fun i => i.no_partly_paid_shares,
    failReason := fun i => if !i.no_partly_paid_shares then "Partly‑paid equity shares are outstanding." else "",
    remedy? := some "Fully pay or forfeit all partly‑paid equity shares." },

  -- 19. 75 % finance tied up
  { id := "ICDR_7_1_e_finance",
    title := "75 % means of finance tied up (verifiable)",
    reference := "ICDR_7_1_e_finance",
    check := fun i => i.finance_75_percent_done,
    failReason := fun i => if !i.finance_75_percent_done then "Less than 75 % of finance is tied up via verifiable means." else "",
    remedy? := some "Tie up 75 % of finance through verifiable means." },

  -- 20. General corporate purposes cap ≤ 25 %
  { id := "ICDR_7_2_gcp_cap",
    title := "General corporate purposes cap ≤ 25 %",
    reference := "ICDR_7_2_gcp_cap",
    check := fun i => i.general_corp_purpose_ratio ≤ 25,
    failReason := fun i => if i.general_corp_purpose_ratio > 25 then "General corporate purposes exceed 25 % of the issue amount." else "",
    remedy? := some "Reduce general corporate purposes to ≤ 25 %." },

  -- 21. OFS shares holding period
  { id := "ICDR_8_holding_period",
    title := "OFS shares must be held ≥ 1 year pre‑DRHP (with carve‑outs)",
    reference := "ICDR_8_holding_period",
    check := fun i =>
      i.shares_held_duration_months ≥ 12 ∨
      i.is_govt_entity ∨
      i.via_merger_scheme ∨
      (i.is_bonus_from_free_reserve ∧ i.bonus_not_from_revaluation),
    failReason := fun i =>
      if i.shares_held_duration_months ≥ 12 then ""
      else if i.is_govt_entity then ""
      else if i.via_merger_scheme then ""
      else if i.is_bonus_from_free_reserve ∧ i.bonus_not_from_revaluation then ""
      else "OFS shares not held for ≥ 1 year before DRHP and no applicable carve‑out.",
    remedy? := some "Hold OFS shares for ≥ 1 year before DRHP or satisfy a carve‑out." },

  -- 22. Additional OFS caps under 6(2) route
  { id := "ICDR_8A_ofs_caps",
    title := "Additional OFS caps when using 6(2) route",
    reference := "ICDR_8A_ofs_caps",
    check := fun _ => True,
    failReason := fun _ => "6(2) route not modeled; assume no additional caps.",
    remedy? := none },

  -- 23. Minimum promoters’ contribution ≥ 20 %
  { id := "ICDR_14_1_min_promoter_20pct",
    title := "Minimum promoters’ contribution ≥ 20 % of post‑issue capital",
    reference := "ICDR_14_1_min_promoter_20pct",
    check := fun _ => True,
    failReason := fun _ => "Promoter contribution fields not modeled; assume compliant.",
    remedy? := none },

  -- 24. Form of promoters’ contribution and pricing constraints
  { id := "ICDR_14_2_a_form_of_contribution",
    title := "Form of promoters’ contribution and pricing constraints",
    reference := "ICDR_14_2_a_form_of_contribution",
    check := fun _ => True,
    failReason := fun _ => "Contribution form fields not modeled; assume compliant.",
    remedy? := none },

  -- 25. Weighted‑average price floor for staggered convertibles
  { id := "ICDR_14_2_b_weighted_avg_price",
    title := "Weighted‑average price floor for staggered convertibles",
    reference := "ICDR_14_2_b_weighted_avg_price",
    check := fun _ => True,
    failReason := fun _ => "Weighted‑average price fields not modeled; assume compliant.",
    remedy? := none },

  -- 26. Convertible‑debt only IPO: promoter equity contribution
  { id := "ICDR_14_2_c_project_cost_case",
    title := "Convertible‑debt only IPO: promoter equity contribution",
    reference := "ICDR_14_2_c_project_cost_case",
    check := fun _ => True,
    failReason := fun _ => "Project cost and equity fields not modeled; assume compliant.",
    remedy? := none },

  -- 27. Promoters’ contribution timing
  { id := "ICDR_14_3_timing",
    title := "Promoters’ contribution timing",
    reference := "ICDR_14_3_timing",
    check := fun _ => True,
    failReason := fun _ => "Contribution timing fields not modeled; assume compliant.",
    remedy? := none },

  -- 28. Securities ineligible for MPC
  { id := "ICDR_15_ineligible_for_MPC",
    title := "Securities ineligible for minimum promoters’ contribution",
    reference := "ICDR_15_ineligible_for_MPC",
    check := fun _ => True,
    failReason := fun _ => "Ineligible securities fields not modeled; assume compliant.",
    remedy? := none },

  -- 29. Lock‑in of minimum promoters’ contribution
  { id := "ICDR_16_1_a_lockin_MPC",
    title := "Lock‑in of minimum promoters’ contribution",
    reference := "ICDR_16_1_a_lockin_MPC",
    check := fun _ => True,
    failReason := fun _ => "Lock‑in fields not modeled; assume compliant.",
    remedy? := none },

  -- 30. Lock‑in of promoters’ holding in excess of MPC
  { id := "ICDR_16_1_b_lockin_excess",
    title := "Lock‑in of promoters’ holding in excess of MPC",
    reference := "ICDR_16_1_b_lockin_excess",
    check := fun _ => True,
    failReason := fun _ => "Lock‑in excess fields not modeled; assume compliant.",
    remedy? := none },

  -- 31. Computation explanations (no pass/fail)
  { id := "ICDR_16_explanations",
    title := "Computation explanations (post‑issue base, ESOP/SAR, weighted average)",
    reference := "ICDR_16_explanations",
    check := fun _ => True,
    failReason := fun _ => "",
    remedy? := none },

  -- 32. Lock‑in for pre‑issue capital held by non‑promoters
  { id := "ICDR_17_lockin_non_promoters",
    title := "Lock‑in for pre‑issue capital held by non‑promoters",
    reference := "ICDR_17_lockin_non_promoters",
    check := fun _ => True,
    failReason := fun _ => "Non‑promoter lock‑in fields not modeled; assume compliant.",
    remedy? := none },

  -- 33. Green shoe lending lock‑in
  { id := "ICDR_18_green_shoe_lending",
    title := "Green shoe lending: lock‑in not applicable during lending period",
    reference := "ICDR_18_green_shoe_lending",
    check := fun _ => True,
    failReason := fun _ => "Green shoe lending fields not modeled; assume compliant.",
    remedy? := none },

  -- 34. Lock‑in of partly‑paid specified securities
  { id := "ICDR_19_partly_paid_lockin",
    title := "Lock‑in of partly‑paid specified securities",
    reference := "ICDR_19_partly_paid_lockin",
    check := fun _ => True,
    failReason := fun _ => "Partly‑paid lock‑in fields not modeled; assume compliant.",
    remedy? := none },

  -- 35. Non‑transferable marking
  { id := "ICDR_20_non_transferable_marking",
    title := "Inscription/recording of non‑transferability",
    reference := "ICDR_20_non_transferable_marking",
    check := fun _ => True,
    failReason := fun _ => "Non‑transferable marking fields not modeled; assume compliant.",
    remedy? := none },

  -- 36. Pledge of locked‑in specified securities by promoters
  { id := "ICDR_21_pledge_lockedin",
    title := "Pledge of locked‑in specified securities by promoters",
    reference := "ICDR_21_pledge_lockedin",
    check := fun _ => True,
    failReason := fun _ => "Pledge fields not modeled; assume compliant.",
    remedy? := none },

  -- 37. Transfer of locked‑in specified securities
  { id := "ICDR_22_transfer_lockedin",
    title := "Transfer of locked‑in specified securities",
    reference := "ICDR_22_transfer_lockedin",
    check := fun _ => True,
    failReason := fun _ => "Transfer lock‑in fields not modeled; assume compliant.",
    remedy? := none }
]

/-- Fields required for the above rules ---------------------------------------- -/
def issuerQuestionsChunk : List (String × String × String) := [
  ("is_debarred", "Is the issuer debarred from capital markets?", "Bool"),
  ("has_debarred_directors", "Do any directors or promoters have a debarment?", "Bool"),
  ("is_fraudulent", "Is the issuer or any promoter/director a fraudulent borrower?", "Bool"),
  ("is_fugitive", "Is any promoter or director a fugitive economic offender?", "Bool"),
  ("has_outstanding_convertibles", "Are there outstanding convertibles or rights before filing?", "Bool"),
  ("has_esop_exemption", "Is there an ESOP exemption for outstanding convertibles?", "Bool"),
  ("has_sar_exemption", "Is there a SAR exemption for outstanding convertibles?", "Bool"),
  ("has_mandatory_convertibles", "Are there mandatory convertibles fully paid and converted?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (in paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (in paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (in paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new‑name activity?", "Nat"),
  ("uses_book_building", "Is the issuer using book‑building for the offer?", "Bool"),
  ("qib_allocation_done", "Has QIB allocation been completed?", "Bool"),
  ("sr_net_worth", "Provide SR net worth (in paise).", "Nat"),
  ("is_tech_firm", "Is the issuer a technology‑intensive firm?", "Bool"),
  ("sr_holder_exec", "Is the SR holder an executive of the issuer?", "Bool"),
  ("sr_voting_ratio", "What is the SR voting ratio (e.g., 2:1)?", "Nat"),
  ("sr_class_count", "How many SR classes are issued?", "Nat"),
  ("sr_same_face_value", "Do SR shares have the same face value as ordinary shares?", "Bool"),
  ("sr_issued_3mo_prior", "Were SR shares issued at least 3 months before DRHP?", "Bool"),
  ("applied_to_stock_exchange", "Has the issuer applied to a stock exchange?", "Bool"),
  ("has_demat_agreement", "Has the issuer executed a depository agreement?", "Bool"),
  ("promoter_securities_demat", "Are promoter‑held securities dematerialised?", "Bool"),
  ("no_partly_paid_shares", "Are there any partly‑paid equity shares outstanding?", "Bool"),
  ("finance_75_percent_done", "Is 75 % of finance tied up via verifiable means?", "Bool"),
  ("general_corp_purpose_ratio", "What % of the issue amount is for general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How many months have fully paid shares been held before filing?", "Nat"),
  ("is_govt_entity", "Is the issuer a government entity?", "Bool"),
  ("via_merger_scheme", "Is the issuer part of a merger scheme?", "Bool"),
  ("is_bonus_from_free_reserve", "Is the OFS share a bonus from free reserves?", "Bool"),
  ("bonus_not_from_revaluation", "Is the bonus not from revaluation?", "Bool")
]

def issuerQuestions : List (String × String × String) := [
("is_debarred", "Is the issuer debarred from capital markets?", "Bool"),
  ("has_debarred_directors", "Do any directors or promoters have a debarment?", "Bool"),
  ("is_fraudulent", "Is the issuer or any promoter/director a fraudulent borrower?", "Bool"),
  ("is_fugitive", "Is any promoter or director a fugitive economic offender?", "Bool"),
  ("has_outstanding_convertibles", "Are there outstanding convertibles or rights before filing?", "Bool"),
  ("has_esop_exemption", "Is there an ESOP exemption for outstanding convertibles?", "Bool"),
  ("has_sar_exemption", "Is there a SAR exemption for outstanding convertibles?", "Bool"),
  ("has_mandatory_convertibles", "Are there mandatory convertibles fully paid and converted?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (in paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (in paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (in paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new‑name activity?", "Nat"),
  ("uses_book_building", "Is the issuer using book‑building for the offer?", "Bool"),
  ("qib_allocation_done", "Has QIB allocation been completed?", "Bool"),
  ("sr_net_worth", "Provide SR net worth (in paise).", "Nat"),
  ("is_tech_firm", "Is the issuer a technology‑intensive firm?", "Bool"),
  ("sr_holder_exec", "Is the SR holder an executive of the issuer?", "Bool"),
  ("sr_voting_ratio", "What is the SR voting ratio (e.g., 2:1)?", "Nat"),
  ("sr_class_count", "How many SR classes are issued?", "Nat"),
  ("sr_same_face_value", "Do SR shares have the same face value as ordinary shares?", "Bool"),
  ("sr_issued_3mo_prior", "Were SR shares issued at least 3 months before DRHP?", "Bool"),
  ("applied_to_stock_exchange", "Has the issuer applied to a stock exchange?", "Bool"),
  ("has_demat_agreement", "Has the issuer executed a depository agreement?", "Bool"),
  ("promoter_securities_demat", "Are promoter‑held securities dematerialised?", "Bool"),
  ("no_partly_paid_shares", "Are there any partly‑paid equity shares outstanding?", "Bool"),
  ("finance_75_percent_done", "Is 75 % of finance tied up via verifiable means?", "Bool"),
  ("general_corp_purpose_ratio", "What % of the issue amount is for general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How many months have fully paid shares been held before filing?", "Nat"),
  ("is_govt_entity", "Is the issuer a government entity?", "Bool"),
  ("via_merger_scheme", "Is the issuer part of a merger scheme?", "Bool"),
  ("is_bonus_from_free_reserve", "Is the OFS share a bonus from free reserves?", "Bool"),
  ("bonus_not_from_revaluation", "Is the bonus not from revaluation?", "Bool")
]

end Src.GeneratedRules_gpt_oss_v1
