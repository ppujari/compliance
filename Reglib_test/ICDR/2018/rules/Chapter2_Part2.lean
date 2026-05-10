-- Auto-generated rules file: Chapter2_Part2.lean
-- Chapter II, Part II: ISSUE OF CONVERTIBLE DEBT INSTRUMENTS AND WARRANTS

import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules

open Reglib.ICDR

/-! ## Regulation 9 -/
/-- Reg 9: Provided that it is not in default of payment of interest or repayment of principal amount in respect of debt instrument... -/
def reg_9 (issuer : Issuer) : Prop :=
  issuer.no_default_payment_more_than_six_months = true

/-- Reg 9(proviso): it is not in default of payment of interest or repayment of principal amount in respect of debt instruments issued by it... -/
def reg_9_proviso (issuer : Issuer) : Prop :=
  issuer.no_default_on_debt_payments_months ≥ 0  -- TODO: set correct threshold

/-! ## Regulation 10 -/
/-- Reg 10(1): In addition to other requirements laid down in these regulations, an issuer making an initial public offer of convertibl... -/
def reg_10_1 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 10(1)(a): it has obtained credit rating from at least one credit rating agency;... -/
def reg_10_1_a (issuer : Issuer) : Prop :=
  issuer.has_credit_rating_from_one_agency = true

/-- Reg 10(1)(b): it has appointed at least one debenture trustee in accordance with the provisions of the Companies Act, 2013 and the Sec... -/
def reg_10_1_b (issuer : Issuer) : Prop :=
  issuer.has_appointed_debenture_trustee = true

/-- Reg 10(1)(c): it shall create a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules ma... -/
def reg_10_1_c (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 10(1)(d): if the issuer proposes to create a charge or security on its assets in respect of secured convertible debt instruments, ... -/
def reg_10_1_d (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 10(1)(d)(i): such assets are sufficient to discharge the principal amount at all times;... -/
def reg_10_1_d_i (issuer : Issuer) : Prop :=
  issuer.assets_sufficient_principal_discharge = true

/-- Reg 10(1)(d)(ii): such assets are free from any encumbrance;... -/
def reg_10_1_d_ii (issuer : Issuer) : Prop :=
  issuer.is_free_from_encumbrance = true

/-- Reg 10(1)(d)(iii): where security is already created on such assets in favour of any existing lender or security trustee or the issue of co... -/
def reg_10_1_d_iii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 10(1)(d)(iv): the security or asset cover shall be arrived at after reduction of the liabilities having a first or prior charge, in ca... -/
def reg_10_1_d_iv (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 10(2): The issuer shall redeem the convertible debt instruments in terms of the offer document.... -/
def reg_10_2 (issuer : Issuer) : Prop :=
  issuer.is_redeeming_convertible_debt_instruments = true

/-- Combined Regulation 10 gate -/
def reg_10_eligible (issuer : Issuer) : Prop :=
  reg_10_1_a issuer
  ∧ reg_10_1_b issuer
  ∧ reg_10_1_d_i issuer
  ∧ reg_10_1_d_ii issuer
  ∧ reg_10_2 issuer

/-! ## Regulation 11 -/
/-- Reg 11(1): The issuer shall not convert its optionally convertible debt instruments into equity shares unless the holders of such c... -/
def reg_11_1 (issuer : Issuer) : Prop :=
  issuer.has_positive_consent_from_holders = false

/-- Reg 11(2): Where the value of the convertible portion of any listed convertible debt instruments issued by an issuer exceeds ten cr... -/
def reg_11_2 (issuer : Issuer) : Prop :=
  issuer.convertible_debt_value_threshold ≥ 0  -- TODO: set correct threshold

/-- Reg 11(3): Where an option is to be given to the holders of the convertible debt instruments in terms of sub-regulation (2) and if ... -/
def reg_11_3 (issuer : Issuer) : Prop :=
  issuer.convertible_debt_redemption_period_months ≥ 0  -- TODO: set correct threshold

/-- Reg 11(4): The provision of sub-regulation (2) shall not apply if such redemption is as per the disclosures made in the offer docum... -/
def reg_11_4 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Combined Regulation 11 gate -/
def reg_11_eligible (issuer : Issuer) : Prop :=
  reg_11_1 issuer
  ∧ reg_11_2 issuer
  ∧ reg_11_3 issuer

/-! ## Regulation 12 -/
/-- Reg 12: An issuer shall not issue convertible debt instruments for financing or for providing loans to or for acquiring shares o... -/
def reg_12 (issuer : Issuer) : Prop :=
  issuer.no_convertible_debt_for_promoter_group_financing = false

/-- Reg 12(proviso): Provided that an issuer shall be eligible to issue fully convertible debt instruments if the period of conversion is les... -/
def reg_12_proviso (issuer : Issuer) : Prop :=
  issuer.convertible_debt_period_months ≥ 0  -- TODO: set correct threshold

/-! ## Regulation 13 -/
/-- Reg 13: An issuer shall be eligible to issue warrants in an initial public offer subject to the following:... -/
def reg_13 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 13(proviso): Provided that in case the exercise price of warrants is based on a formula, twenty-five per cent. consideration amount b... -/
def reg_13_proviso (issuer : Issuer) : Prop :=
  issuer.warrant_formula_consideration_pct ≥ 0  -- TODO: set correct threshold

/-! ## Composite Chapter II Part II Gate -/

def chapter2_part2_eligible (issuer : Issuer) : Prop :=
  reg_10_eligible issuer
  ∧ reg_11_eligible issuer

end Reglib.ICDR.Rules
