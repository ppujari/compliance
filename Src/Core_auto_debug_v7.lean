import Lean
import Lean.Data.Json

namespace Src.Core_auto_debug_v7
open Lean

set_option linter.unusedVariables false

/-- Issuer data model used by compliance rules (auto-generated). -/
structure Issuer where
  consent_for_conversion : Bool
  contribution_method : String
  convertible_securities : List Nat
  credit_rating : Bool
  debenture_redemption_reserve : Bool
  debenture_trustee : List Nat
  default_payment_status : Bool
  finance_arrangements : List Nat
  fully_paid_up_equity_shares : Bool
  lock_in_period : Nat
  max_sale_unidentified_targets : Nat
  min_holding_period : Nat
  net_tangible_assets : Nat
  net_worth : List Nat
  operating_profits : List Nat
  promoter_contribution : Nat
  promoter_securities_dematerialised : Bool
  securities_held_by_promoters : OptionList Nat
  securities_ineligible : List Nat
  specified_securities : List Nat
  upfront_payment : Nat
  warrant_exercise_price : String
  warrant_tenure : Nat
  deriving Repr, ToJson

/-- Input-friendly variant with optional fields for JSON decoding (auto-generated). -/
structure IssuerInput where
  consent_for_conversion : Option Bool := none
  contribution_method : Option String := none
  convertible_securities : Option (List Nat) := none
  credit_rating : Option Bool := none
  debenture_redemption_reserve : Option Bool := none
  debenture_trustee : Option (List Nat) := none
  default_payment_status : Option Bool := none
  finance_arrangements : Option (List Nat) := none
  fully_paid_up_equity_shares : Option Bool := none
  lock_in_period : Option Nat := none
  max_sale_unidentified_targets : Option Nat := none
  min_holding_period : Option Nat := none
  net_tangible_assets : Option Nat := none
  net_worth : Option (List Nat) := none
  operating_profits : Option (List Nat) := none
  promoter_contribution : Option Nat := none
  promoter_securities_dematerialised : Option Bool := none
  securities_held_by_promoters : Option (OptionList Nat) := none
  securities_ineligible : Option (List Nat) := none
  specified_securities : Option (List Nat) := none
  upfront_payment : Option Nat := none
  warrant_exercise_price : Option String := none
  warrant_tenure : Option Nat := none
  deriving Repr, FromJson

/-- Normalize an IssuerInput by filling defaults for missing fields (auto-generated). -/
def IssuerInput.normalize (x : IssuerInput) : Issuer :=
  { consent_for_conversion := x.consent_for_conversion.getD false
  , contribution_method := x.contribution_method.getD ""
  , convertible_securities := x.convertible_securities.getD []
  , credit_rating := x.credit_rating.getD false
  , debenture_redemption_reserve := x.debenture_redemption_reserve.getD false
  , debenture_trustee := x.debenture_trustee.getD []
  , default_payment_status := x.default_payment_status.getD false
  , finance_arrangements := x.finance_arrangements.getD []
  , fully_paid_up_equity_shares := x.fully_paid_up_equity_shares.getD false
  , lock_in_period := x.lock_in_period.getD 0
  , max_sale_unidentified_targets := x.max_sale_unidentified_targets.getD 0
  , min_holding_period := x.min_holding_period.getD 0
  , net_tangible_assets := x.net_tangible_assets.getD 0
  , net_worth := x.net_worth.getD []
  , operating_profits := x.operating_profits.getD []
  , promoter_contribution := x.promoter_contribution.getD 0
  , promoter_securities_dematerialised := x.promoter_securities_dematerialised.getD false
  , securities_held_by_promoters := x.securities_held_by_promoters.getD ""
  , securities_ineligible := x.securities_ineligible.getD []
  , specified_securities := x.specified_securities.getD []
  , upfront_payment := x.upfront_payment.getD 0
  , warrant_exercise_price := x.warrant_exercise_price.getD ""
  , warrant_tenure := x.warrant_tenure.getD 0
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

end Src.Core_auto_debug_v7
