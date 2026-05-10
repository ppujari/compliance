import Lean
import Lean.Data.Json

namespace Src.Core_auto_debug_v8
open Lean

set_option linter.unusedVariables false

/-- Issuer data model used by compliance rules (auto-generated). -/
structure Issuer where
  companies_act_approvals : List (Nat × Nat)
  consent_for_conversion : Bool
  convertible_debt_value : Nat
  credit_rating : Bool
  debenture_redemption_reserve : Bool
  debenture_trustee : List Nat
  default_payment_status : Bool
  employee_stock_options_or_SARs_exercise : Bool
  government_ipos : List Nat
  lock_in_period : Nat
  locked_in_securities : List Nat
  monetary_assets : Nat
  net_tangible_assets : List Nat
  net_worth : List Nat
  operating_profits : List Nat
  promoter_contribution_computation_method : List (String × String)
  promoter_contribution_undisclosed : Bool
  promoter_payments : List (Nat × Nat)
  promoter_transactions : List (Nat × Nat)
  securities_held_by_promoters : OptionList Nat
  securities_ineligible : List Nat
  specified_securities : List Nat
  sr_equity_shares : Bool
  deriving Repr, ToJson

/-- Input-friendly variant with optional fields for JSON decoding (auto-generated). -/
structure IssuerInput where
  companies_act_approvals : Option (List (Nat × Nat)) := none
  consent_for_conversion : Option Bool := none
  convertible_debt_value : Option Nat := none
  credit_rating : Option Bool := none
  debenture_redemption_reserve : Option Bool := none
  debenture_trustee : Option (List Nat) := none
  default_payment_status : Option Bool := none
  employee_stock_options_or_SARs_exercise : Option Bool := none
  government_ipos : Option (List Nat) := none
  lock_in_period : Option Nat := none
  locked_in_securities : Option (List Nat) := none
  monetary_assets : Option Nat := none
  net_tangible_assets : Option (List Nat) := none
  net_worth : Option (List Nat) := none
  operating_profits : Option (List Nat) := none
  promoter_contribution_computation_method : Option (List (String × String)) := none
  promoter_contribution_undisclosed : Option Bool := none
  promoter_payments : Option (List (Nat × Nat)) := none
  promoter_transactions : Option (List (Nat × Nat)) := none
  securities_held_by_promoters : Option (OptionList Nat) := none
  securities_ineligible : Option (List Nat) := none
  specified_securities : Option (List Nat) := none
  sr_equity_shares : Option Bool := none
  deriving Repr, FromJson

/-- Normalize an IssuerInput by filling defaults for missing fields (auto-generated). -/
def IssuerInput.normalize (x : IssuerInput) : Issuer :=
  { companies_act_approvals := x.companies_act_approvals.getD []
  , consent_for_conversion := x.consent_for_conversion.getD false
  , convertible_debt_value := x.convertible_debt_value.getD 0
  , credit_rating := x.credit_rating.getD false
  , debenture_redemption_reserve := x.debenture_redemption_reserve.getD false
  , debenture_trustee := x.debenture_trustee.getD []
  , default_payment_status := x.default_payment_status.getD false
  , employee_stock_options_or_SARs_exercise := x.employee_stock_options_or_SARs_exercise.getD false
  , government_ipos := x.government_ipos.getD []
  , lock_in_period := x.lock_in_period.getD 0
  , locked_in_securities := x.locked_in_securities.getD []
  , monetary_assets := x.monetary_assets.getD 0
  , net_tangible_assets := x.net_tangible_assets.getD []
  , net_worth := x.net_worth.getD []
  , operating_profits := x.operating_profits.getD []
  , promoter_contribution_computation_method := x.promoter_contribution_computation_method.getD []
  , promoter_contribution_undisclosed := x.promoter_contribution_undisclosed.getD false
  , promoter_payments := x.promoter_payments.getD []
  , promoter_transactions := x.promoter_transactions.getD []
  , securities_held_by_promoters := x.securities_held_by_promoters.getD ""
  , securities_ineligible := x.securities_ineligible.getD []
  , specified_securities := x.specified_securities.getD []
  , sr_equity_shares := x.sr_equity_shares.getD false
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

end Src.Core_auto_debug_v8
