-- Auto-generated rules file: Chapter2_Part3.lean
-- Chapter II, Part III: PROMOTERS’ CONTRIBUTION

import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules

open Reglib.ICDR

/-! ## Regulation 14 -/
/-- Reg 14(1): The promoters of the issuer shall hold at least twenty per cent. of the post-issue capital:... -/
def reg_14_1 (issuer : Issuer) : Prop :=
  issuer.promoter_min_holding_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 14(1)(proviso): in case the post-issue shareholding of the promoters is less than twenty per cent., alternative investment funds or fore... -/
def reg_14_1_proviso (issuer : Issuer) : Prop :=
  issuer.alternative_contribution_max_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 14(1)(proviso)(2): the requirement of minimum promoters’ contribution shall not apply in case an issuer does not have any identifiable prom... -/
def reg_14_1_proviso_2 (issuer : Issuer) : Prop :=
  issuer.has_identifiable_promoter_reg14 = false

/-- Reg 14(1)(proviso)(2)(that): Provided further that the requirement of minimum promoters’ contribution shall not apply in case an issuer does not have... -/
def reg_14_1_proviso_2_that (issuer : Issuer) : Prop :=
  issuer.has_identifiable_promoter_reg14 = false

/-- Reg 14(2): The minimum promoters’ contribution shall be as follows:... -/
def reg_14_2 (issuer : Issuer) : Prop :=
  issuer.promoter_min_contribution_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 14(3): The promoters shall satisfy the requirements of this regulation at least one day prior to the date of opening of the iss... -/
def reg_14_3 (issuer : Issuer) : Prop :=
  issuer.promoter_requirements_compliance_date ≥ 0  -- TODO: set correct threshold

/-- Reg 14(4): In case the promoters have to subscribe to equity shares or convertible securities towards minimum promoters’ contributi... -/
def reg_14_4 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 14(4)(proviso): where the promoters’ contribution has already been brought in and utilised, the issuer shall give the cash flow statemen... -/
def reg_14_4_proviso (issuer : Issuer) : Prop :=
  issuer.has_promoter_contribution_disclosure = true

/-- Reg 14(4)(proviso)(2): where the minimum promoters’ contribution is more than one hundred crore rupees and the initial public offer is for part... -/
def reg_14_4_proviso_2 (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_min_crore ≥ 0  -- TODO: set correct threshold

/-- Reg 14(a): the promoters shall contribute twenty per cent. as stipulated in sub-regulation (1), as the case may be, either by way o... -/
def reg_14_a (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 14(a)(proviso): if the price of the equity shares allotted pursuant to conversion is not pre-determined and not disclosed in the offer d... -/
def reg_14_a_proviso (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_mechanism ≠ ""

/-- Reg 14(b): in case of any issue of convertible securities which are convertible or exchangeable on different dates and if the promo... -/
def reg_14_b (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_price_not_lower_than_weighted_avg = false

/-- Reg 14(c): subject to the provisions of clause (a) and (b) above, in case of an initial public offer of convertible debt instrument... -/
def reg_14_c (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_pct_project_cost ≥ 0  -- TODO: set correct threshold
  ∧ issuer.promoter_contribution_pct_issue_size ≥ 0  -- TODO: set correct threshold

/-- Reg 14(c)(proviso): if the project is to be implemented in stages, the promoters’ contribution shall be with respect to total equity partici... -/
def reg_14_c_proviso (issuer : Issuer) : Prop :=
  issuer.promoter_contribution_pct_till_stage ≥ 0  -- TODO: set correct threshold

/-- Combined Regulation 14 gate -/
def reg_14_eligible (issuer : Issuer) : Prop :=
  reg_14_1 issuer
  ∧ reg_14_2 issuer
  ∧ reg_14_a issuer
  ∧ reg_14_b issuer
  ∧ reg_14_c issuer
  ∧ reg_14_3 issuer

/-! ## Regulation 15 -/
/-- Reg 15(1): For the computation of minimum promoters’ contribution, the following specified securities shall not be eligible:... -/
def reg_15_1 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(1)(a): specified securities acquired during the preceding three years, if these are: acquired for consideration other than cash... -/
def reg_15_1_a (issuer : Issuer) : Prop :=
  issuer.is_revalued_assets_or_intangibles_capitalised_in_transaction = true

/-- Reg 15(1)(a)(i): acquired for consideration other than cash and revaluation of assets or capitalisation of intangible assets is involved ... -/
def reg_15_1_a_i (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(1)(a)(ii): resulting from a bonus issue by utilisation of revaluation reserves or unrealised profits of the issuer or from bonus is... -/
def reg_15_1_a_ii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(1)(b): specified securities acquired by the promoters and alternative investment funds or foreign venture capital investors or ... -/
def reg_15_1_b (issuer : Issuer) : Prop :=
  issuer.has_price_comparison_requirement = true

/-- Reg 15(a): Promoters’ contribution shall be computed on the basis of the post-issue expanded capital: assuming full proposed conver... -/
def reg_15_a (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(b): assuming exercise of all vested options, where any employee stock options [or stock appreciation rights] are outstanding... -/
def reg_15_b (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(proviso): nothing contained in this clause shall apply: if the promoters and alternative investment funds or foreign venture capit... -/
def reg_15_proviso (issuer : Issuer) : Prop :=
  issuer.non_individual_public_shareholder_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 15(proviso)(i): if the promoters and alternative investment funds or foreign venture capital investors or scheduled commercial banks or ... -/
def reg_15_proviso_i (issuer : Issuer) : Prop :=
  issuer.promoter_payment_difference = true

/-- Reg 15(proviso)(ii): if such specified securities are acquired in terms of the scheme under [***] sections 230 to 234 of the Companies Act, 2... -/
def reg_15_proviso_ii (issuer : Issuer) : Prop :=
  issuer.promoter_investment_period_years ≥ 0  -- TODO: set correct threshold

/-- Reg 15(proviso)(iii): to an initial public offer by a government company, statutory authority or corporation or any special purpose vehicle se... -/
def reg_15_proviso_iii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 15(proviso)(iv): to equity shares arising from the conversion or exchange of fully paid-up compulsorily convertible securities, including... -/
def reg_15_proviso_iv (issuer : Issuer) : Prop :=
  issuer.promoter_holding_period_years ≥ 0  -- TODO: set correct threshold

/-- Combined Regulation 15 gate -/
def reg_15_eligible (issuer : Issuer) : Prop :=
  reg_15_1_a issuer
  ∧ reg_15_1_b issuer

/-! ## Composite Chapter II Part III Gate -/

def chapter2_part3_eligible (issuer : Issuer) : Prop :=
  reg_14_eligible issuer
  ∧ reg_15_eligible issuer

end Reglib.ICDR.Rules
