-- Auto-generated rules file: Chapter2_Part4.lean
-- Chapter II, Part IV: LOCK-IN AND RESTRICTIONS ON TRANSFERABILITY

import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules

open Reglib.ICDR

/-! ## Regulation 16 -/
/-- Reg 16: The specified securities held by the promoters shall not be transferable (hereinafter referred to as “lock-in”) for the ... -/
def reg_16 (issuer : Issuer) : Prop :=
  issuer.promoter_lock_in_period_months ≥ 0  -- TODO: set correct threshold

/-- Reg 16(1): minimum promoters’ contribution including contribution made by alternative investment funds or foreign venture capital i... -/
def reg_16_1 (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_lock_in_months ≥ 0  -- TODO: set correct threshold

/-- Reg 16(1)(proviso): in case the majority of the issue proceeds excluding the portion of offer for sale is proposed to be utilized for capita... -/
def reg_16_1_proviso (issuer : Issuer) : Prop :=
  issuer.lock_in_period_for_capital_expenditure_years ≥ 0  -- TODO: set correct threshold

/-- Reg 16(b): promoters’ holding in excess of minimum promoters’ contribution shall be locked-in for a period of [six months] from the... -/
def reg_16_b (issuer : Issuer) : Prop :=
  issuer.ofs_holding_period_months_reg16 ≥ 0  -- TODO: set correct threshold

/-- Reg 16(explanation): For the purpose of this sub-regulation, “capital expenditure” shall include civil work, miscellaneous fixed assets, purc... -/
def reg_16_explanation (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Combined Regulation 16 gate -/
def reg_16_eligible (issuer : Issuer) : Prop :=
  reg_16 issuer
  ∧ reg_16_1 issuer
  ∧ reg_16_b issuer

/-! ## Regulation 17 -/
/-- Reg 17: The entire pre-issue capital held by persons other than the promoters shall be locked-in for a period of six months from... -/
def reg_17 (issuer : Issuer) : Prop :=
  issuer.non_promoter_lock_in_period_months ≥ 0  -- TODO: set correct threshold

/-- Reg 17(a): equity shares allotted to employees, whether currently an employee or not, under an employee stock option or employee st... -/
def reg_17_a (issuer : Issuer) : Prop :=
  issuer.has_made_full_disclosures_in_schedule_vi_part_a = true

/-- Reg 17(b): equity shares held by a venture capital fund or alternative investment fund of category I or Category II or a foreign ve... -/
def reg_17_b (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 17(explanation)(i): For the purpose of clause (c), in case such equity shares have resulted pursuant to conversion of fully paid-up compulso... -/
def reg_17_explanation_i (issuer : Issuer) : Prop :=
  issuer.holding_period_months_reg17 ≥ 0  -- TODO: set correct threshold

/-- Reg 17(explanation)(ii): For the purpose of clause (c), in case such equity shares have resulted pursuant to a bonus issue, then the holding peri... -/
def reg_17_explanation_ii (issuer : Issuer) : Prop :=
  issuer.bonus_issue_holding_period_months ≥ 0  -- TODO: set correct threshold

/-- Reg 17(explanation)(ii)(a): that the bonus shares being issued out of free reserves and share premium existing in the books of account as at the end... -/
def reg_17_explanation_ii_a (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 17(explanation)(ii)(b): that the bonus shares not being issued by utilisation of revaluation reserves or unrealized profits of the issuer.... -/
def reg_17_explanation_ii_b (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 17(explanation)(iii): For the purpose of clauses (a) and (b), equity shares shall include any equity shares allotted pursuant to a bonus issue... -/
def reg_17_explanation_iii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 17(proviso): nothing contained in this regulation shall apply to: a) equity shares allotted to employees, whether currently an employ... -/
def reg_17_proviso (issuer : Issuer) : Prop :=
  issuer.has_full_disclosures_for_employee_stock_schemes = true

/-- Reg 17(proviso): such equity shares shall be locked in for a period of at least six months from the date of purchase by the venture capit... -/
def reg_17_proviso (issuer : Issuer) : Prop :=
  issuer.ofs_holding_period_months_reg17 ≥ 0  -- TODO: set correct threshold

/-- Reg 17(proviso)(2): the equity shares allotted to the employees shall be subject to the provisions of lock-in as specified under the [Securi... -/
def reg_17_proviso_2 (issuer : Issuer) : Prop :=
  issuer.employee_equity_lock_in_months ≥ 0  -- TODO: set correct threshold

/-- Combined Regulation 17 gate -/
def reg_17_eligible (issuer : Issuer) : Prop :=
  reg_17_a issuer
  ∧ reg_17 issuer

/-! ## Regulation 18 -/
/-- Reg 18: The lock-in provisions shall not apply with respect to the specified securities lent to stabilising agent for the purpos... -/
def reg_18 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 18(proviso): Provided that the specified securities shall be locked-in for the remaining period from the date on which they are retur... -/
def reg_18_proviso (issuer : Issuer) : Prop :=
  issuer.ofs_holding_period_remaining_months ≥ 0  -- TODO: set correct threshold

/-! ## Regulation 19 -/
/-- Reg 19: If the specified securities which are subject to lock-in are partly paid-up and the amount called-up on such specified s... -/
def reg_19 (issuer : Issuer) : Prop :=
  issuer.ofs_holding_period_years_reg19 ≥ 0  -- TODO: set correct threshold

/-! ## Regulation 20 -/
/-- Reg 20: The certificates of specified securities which are subject to lock-in shall contain the inscription “non-transferable” a... -/
def reg_20 (issuer : Issuer) : Prop :=
  issuer.has_depository_lock_in_record = true

/-! ## Regulation 21 -/
/-- Reg 21: Specified securities[, except SR equity shares,] held by the promoters and locked-in may be pledged as a collateral secu... -/
def reg_21 (issuer : Issuer) : Prop :=
  issuer.is_promoter_securities_pledged = false

/-- Reg 21(proviso): Provided that such lock-in shall continue pursuant to the invocation of the pledge and such transferee shall not be elig... -/
def reg_21_proviso (issuer : Issuer) : Prop :=
  issuer.has_lock_in_period_reg21 = false

/-! ## Regulation 22 -/
/-- Reg 22: Subject to the provisions of Securities and Exchange Board of India (Substantial Acquisition of shares and Takeovers) Re... -/
def reg_22 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 22(proviso): Provided that the lock-in on such specified securities shall continue for the remaining period with the transferee and s... -/
def reg_22_proviso (issuer : Issuer) : Prop :=
  issuer.has_lock_in_period_reg22 = false

/-! ## Composite Chapter II Part IV Gate -/

def chapter2_part4_eligible (issuer : Issuer) : Prop :=
  reg_16_eligible issuer
  ∧ reg_17_eligible issuer

end Reglib.ICDR.Rules
