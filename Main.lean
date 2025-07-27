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

def eligible_ipo (i : Issuer) : Bool :=
  ¬i.is_debarred ∧
  ¬i.has_debarred_directors ∧
  ¬i.is_fraudulent ∧
  ¬i.is_fugitive ∧
  (¬i.has_outstanding_convertibles ∨ i.has_esop_exemption ∨ i.has_sar_exemption ∨ i.has_mandatory_convertibles) ∧
  (i.net_tangible_assets.all (λ x => x ≥ 30000000) ∧ (i.monetary_asset_ratio ≤ 50 ∨ i.used_monetary_assets) ∨ i.is_offer_for_sale_only) ∧
  (i.operating_profits.all (λ x => x ≥ 150000000)) ∧
  (i.net_worths.all (λ x => x ≥ 10000000)) ∧
  (¬i.changed_name_recently ∨ i.percent_revenue_from_new_name ≥ 50) ∨
  (i.uses_book_building ∧ i.qib_allocation_done) ∧
  (i.sr_net_worth ≤ 10000000000 ∧ i.is_tech_firm ∧ i.sr_holder_exec ∧ i.sr_issued_3mo_prior ∧ (2 ≤ i.sr_voting_ratio ∧ i.sr_voting_ratio ≤ 10) ∧ i.sr_class_count = 1 ∧ i.sr_same_face_value) ∧
  i.applied_to_stock_exchange ∧ i.has_demat_agreement ∧ i.promoter_securities_demat ∧
  i.no_partly_paid_shares ∧ i.finance_75_percent_done ∧ i.general_corp_purpose_ratio ≤ 25 ∧
  (i.shares_held_duration_months ≥ 12 ∨ i.is_govt_entity ∨ i.via_merger_scheme ∨ (i.is_bonus_from_free_reserve ∧ i.underlying_held_1y ∧ ¬i.bonus_not_from_revaluation))

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

def failure_reasons (i : Issuer) : List String :=
  []
  ++ (if i.is_debarred then ["Debarred by SEBI or other regulators"] else [])
  ++ (if i.has_debarred_directors then ["Promoter or director is debarred"] else [])
  ++ (if i.operating_profits.length ≠ 3 ∨ ¬i.operating_profits.all (λ x => x ≥ 150000000)
      then ["Operating profit for 3 years not ≥ ₹15 Cr"] else [])
  ++ (if i.net_worths.length ≠ 3 ∨ ¬i.net_worths.all (λ x => x ≥ 10000000)
      then ["Net worth for 3 years not ≥ ₹1 Cr"] else [])
  ++ (if i.changed_name_recently ∧ i.percent_revenue_from_new_name < 50
      then ["Changed name recently and <50% revenue from new name"] else [])

def explain_compliance (i : Issuer) : String :=
  if eligible_ipo i then
    "✅ Eligible: All conditions satisfied"
  else
    let fails := failure_reasons i
    "❌ Not Eligible:\n" ++ String.intercalate "\n" (fails.map (λ r => "❌ " ++ r))


#eval explain_compliance red_herring_company