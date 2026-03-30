import Lean
import Lean.Data.Json

namespace Src.Core_auto
open Lean

set_option linter.unusedVariables false

/-- Issuer data model used by compliance rules (auto-generated). -/
structure Issuer where
  agreement_with_depository : Bool
  appointed_debenture_trustee : Bool
  conditions : List Nat
  credit_rating : Bool
  default_payment_or_repayments : Option Nat
  eligible_for_cdi_without_equity_ipo : Bool
  exceptions : List String
  fully_paid_up_equity_shares : Bool
  general_corporate_purposes : Nat
  holding_period : Nat
  holding_period_at_draft : Bool
  lead_manager_appointment : Bool
  lock_in_period : Nat
  net_tangible_assets : List Nat
  net_worth : List Nat
  operating_profits : List Nat
  option_not_convert_if_conversion_price_not_determined : Option (List Nat)
  other_unidentified_objects : Option Nat
  promoter_specified_securities_dematerialised : Bool
  securities : List Nat
  securities_held_by_promoters : List Nat
  specified_securities_ineligible : Bool
  upfront_payment : Nat
  warrant_exercise_price : Option String
  warrant_non_exercise : Option Nat
  warrant_tenure : Nat
  deriving Repr, ToJson

/-- Input-friendly variant with optional fields for JSON decoding (auto-generated). -/
structure IssuerInput where
  agreement_with_depository : Option Bool := none
  appointed_debenture_trustee : Option Bool := none
  conditions : Option (List Nat) := none
  credit_rating : Option Bool := none
  default_payment_or_repayments : Option Nat := none
  eligible_for_cdi_without_equity_ipo : Option Bool := none
  exceptions : Option (List String) := none
  fully_paid_up_equity_shares : Option Bool := none
  general_corporate_purposes : Option Nat := none
  holding_period : Option Nat := none
  holding_period_at_draft : Option Bool := none
  lead_manager_appointment : Option Bool := none
  lock_in_period : Option Nat := none
  net_tangible_assets : Option (List Nat) := none
  net_worth : Option (List Nat) := none
  operating_profits : Option (List Nat) := none
  option_not_convert_if_conversion_price_not_determined : Option (List Nat) := none
  other_unidentified_objects : Option Nat := none
  promoter_specified_securities_dematerialised : Option Bool := none
  securities : Option (List Nat) := none
  securities_held_by_promoters : Option (List Nat) := none
  specified_securities_ineligible : Option Bool := none
  upfront_payment : Option Nat := none
  warrant_exercise_price : Option String := none
  warrant_non_exercise : Option Nat := none
  warrant_tenure : Option Nat := none
  deriving Repr, FromJson

/-- Normalize an IssuerInput by filling defaults for missing fields (auto-generated). -/
def IssuerInput.normalize (x : IssuerInput) : Issuer :=
  { agreement_with_depository := x.agreement_with_depository.getD false
  , appointed_debenture_trustee := x.appointed_debenture_trustee.getD false
  , conditions := x.conditions.getD []
  , credit_rating := x.credit_rating.getD false
  , default_payment_or_repayments := x.default_payment_or_repayments.getD 0
  , eligible_for_cdi_without_equity_ipo := x.eligible_for_cdi_without_equity_ipo.getD false
  , exceptions := x.exceptions.getD []
  , fully_paid_up_equity_shares := x.fully_paid_up_equity_shares.getD false
  , general_corporate_purposes := x.general_corporate_purposes.getD 0
  , holding_period := x.holding_period.getD 0
  , holding_period_at_draft := x.holding_period_at_draft.getD false
  , lead_manager_appointment := x.lead_manager_appointment.getD false
  , lock_in_period := x.lock_in_period.getD 0
  , net_tangible_assets := x.net_tangible_assets.getD []
  , net_worth := x.net_worth.getD []
  , operating_profits := x.operating_profits.getD []
  , option_not_convert_if_conversion_price_not_determined := x.option_not_convert_if_conversion_price_not_determined.getD []
  , other_unidentified_objects := x.other_unidentified_objects.getD 0
  , promoter_specified_securities_dematerialised := x.promoter_specified_securities_dematerialised.getD false
  , securities := x.securities.getD []
  , securities_held_by_promoters := x.securities_held_by_promoters.getD []
  , specified_securities_ineligible := x.specified_securities_ineligible.getD false
  , upfront_payment := x.upfront_payment.getD 0
  , warrant_exercise_price := x.warrant_exercise_price.getD ""
  , warrant_non_exercise := x.warrant_non_exercise.getD 0
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

end Src.Core_auto
