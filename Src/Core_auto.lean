import Lean
import Lean.Data.Json

namespace Src.Core_auto
open Lean

set_option linter.unusedVariables false

/-- Issuer data model used by compliance rules (auto-generated). -/
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
  deriving Repr, ToJson

/-- Input-friendly variant with optional fields for JSON decoding (auto-generated). -/
structure IssuerInput where
  is_debarred : Option Bool := none
  has_debarred_directors : Option Bool := none
  is_fraudulent : Option Bool := none
  is_fugitive : Option Bool := none
  has_outstanding_convertibles : Option Bool := none
  has_esop_exemption : Option Bool := none
  has_sar_exemption : Option Bool := none
  has_mandatory_convertibles : Option Bool := none
  net_tangible_assets : Option (List Nat) := none
  monetary_asset_ratio : Option Nat := none
  used_monetary_assets : Option Bool := none
  is_offer_for_sale_only : Option Bool := none
  operating_profits : Option (List Nat) := none
  net_worths : Option (List Nat) := none
  changed_name_recently : Option Bool := none
  percent_revenue_from_new_name : Option Nat := none
  uses_book_building : Option Bool := none
  qib_allocation_done : Option Bool := none
  is_tech_firm : Option Bool := none
  sr_net_worth : Option Nat := none
  sr_holder_exec : Option Bool := none
  sr_voting_ratio : Option Nat := none
  sr_class_count : Option Nat := none
  sr_same_face_value : Option Bool := none
  sr_issued_3mo_prior : Option Bool := none
  applied_to_stock_exchange : Option Bool := none
  has_demat_agreement : Option Bool := none
  promoter_securities_demat : Option Bool := none
  no_partly_paid_shares : Option Bool := none
  finance_75_percent_done : Option Bool := none
  general_corp_purpose_ratio : Option Nat := none
  shares_fully_paid : Option Bool := none
  shares_held_duration_months : Option Nat := none
  is_govt_entity : Option Bool := none
  via_merger_scheme : Option Bool := none
  is_bonus_from_free_reserve : Option Bool := none
  underlying_held_1y : Option Bool := none
  bonus_not_from_revaluation : Option Bool := none
  deriving Repr, FromJson

/-- Normalize an IssuerInput by filling defaults for missing fields (auto-generated). -/
def IssuerInput.normalize (x : IssuerInput) : Issuer :=
  { is_debarred := x.is_debarred.getD false
  , has_debarred_directors := x.has_debarred_directors.getD false
  , is_fraudulent := x.is_fraudulent.getD false
  , is_fugitive := x.is_fugitive.getD false
  , has_outstanding_convertibles := x.has_outstanding_convertibles.getD false
  , has_esop_exemption := x.has_esop_exemption.getD false
  , has_sar_exemption := x.has_sar_exemption.getD false
  , has_mandatory_convertibles := x.has_mandatory_convertibles.getD false
  , net_tangible_assets := x.net_tangible_assets.getD []
  , monetary_asset_ratio := x.monetary_asset_ratio.getD 0
  , used_monetary_assets := x.used_monetary_assets.getD false
  , is_offer_for_sale_only := x.is_offer_for_sale_only.getD false
  , operating_profits := x.operating_profits.getD []
  , net_worths := x.net_worths.getD []
  , changed_name_recently := x.changed_name_recently.getD false
  , percent_revenue_from_new_name := x.percent_revenue_from_new_name.getD 0
  , uses_book_building := x.uses_book_building.getD false
  , qib_allocation_done := x.qib_allocation_done.getD false
  , is_tech_firm := x.is_tech_firm.getD false
  , sr_net_worth := x.sr_net_worth.getD 0
  , sr_holder_exec := x.sr_holder_exec.getD false
  , sr_voting_ratio := x.sr_voting_ratio.getD 0
  , sr_class_count := x.sr_class_count.getD 0
  , sr_same_face_value := x.sr_same_face_value.getD false
  , sr_issued_3mo_prior := x.sr_issued_3mo_prior.getD false
  , applied_to_stock_exchange := x.applied_to_stock_exchange.getD false
  , has_demat_agreement := x.has_demat_agreement.getD false
  , promoter_securities_demat := x.promoter_securities_demat.getD false
  , no_partly_paid_shares := x.no_partly_paid_shares.getD false
  , finance_75_percent_done := x.finance_75_percent_done.getD false
  , general_corp_purpose_ratio := x.general_corp_purpose_ratio.getD 0
  , shares_fully_paid := x.shares_fully_paid.getD false
  , shares_held_duration_months := x.shares_held_duration_months.getD 0
  , is_govt_entity := x.is_govt_entity.getD false
  , via_merger_scheme := x.via_merger_scheme.getD false
  , is_bonus_from_free_reserve := x.is_bonus_from_free_reserve.getD false
  , underlying_held_1y := x.underlying_held_1y.getD false
  , bonus_not_from_revaluation := x.bonus_not_from_revaluation.getD false
  }

/-- Custom FromJson instance: decode via IssuerInput and normalize. -/
instance : FromJson Issuer where
  fromJson? j := do
    let inp ← fromJson? (α := IssuerInput) j
    pure (IssuerInput.normalize inp)

/-- One compliance rule with a predicate and metadata. -/
structure ComplianceRule where
  id         : String
  title      : String
  reference  : String
  check      : Issuer → Bool
  failReason : Issuer → String
  remedy?    : Option String

/-- Result of running one rule against an Issuer. -/
structure RuleResult where
  id        : String
  title     : String
  reference : String
  passed    : Bool
  reason?   : Option String
  deriving Repr, ToJson, FromJson

/-- Apply a single rule to an issuer. -/
def runRule (i : Issuer) (r : ComplianceRule) : RuleResult :=
  let ok := r.check i
  { id := r.id
  , title := r.title
  , reference := r.reference
  , passed := ok
  , reason? :=
      if ok then none
      else
        some (
          r.failReason i ++
          match r.remedy? with
          | some s => "\nSuggested remedy: " ++ s
          | none   => ""
        )
  }

/-- Helpers used inside rules. -/
def allGeNat (xs : List Nat) (n : Nat) : Bool :=
  xs.all (fun x => x ≥ n)

def lengthIs {α} (xs : List α) (k : Nat) : Bool :=
  xs.length == k

end Src.Core_auto
