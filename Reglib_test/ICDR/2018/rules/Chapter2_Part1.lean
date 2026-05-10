-- Auto-generated rules file: Chapter2_Part1.lean
-- Chapter II, Part I: ELIGIBILITY REQUIREMENTS

import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules

open Reglib.ICDR

/-! ## Regulation 4 -/
/-- Reg 4: Unless otherwise provided in this Chapter, an issuer making an initial public offer of specified securities shall satisf... -/
def reg_4 (issuer : Issuer) : Prop :=
  issuer.is_conditions_satisfied_filing_date = true

/-! ## Regulation 5 -/
/-- Reg 5(1)(a): if the issuer, any of its promoters, promoter group or directors or selling shareholders are debarred from accessing the... -/
def reg_5_1_a (issuer : Issuer) : Prop :=
  issuer.is_debarred = false

/-- Reg 5(1)(b): if any of the promoters or directors of the issuer is a promoter or director of any other company which is debarred from... -/
def reg_5_1_b (issuer : Issuer) : Prop :=
  issuer.has_debarred_promoter_or_director = false

/-- Reg 5(1)(c): if the issuer or any of its promoters or directors is a [wilful defaulter or a fraudulent borrower.]... -/
def reg_5_1_c (issuer : Issuer) : Prop :=
  issuer.is_wilful_defaulter_or_fraudulent_borrower = false

/-- Reg 5(1)(d): if any of its promoters or directors is a fugitive economic offender.... -/
def reg_5_1_d (issuer : Issuer) : Prop :=
  issuer.has_fugitive_economic_offender_promoter_or_director = false

/-- Reg 5(2): An issuer shall not be eligible to make an initial public offer if there are any outstanding convertible securities or a... -/
def reg_5_2 (issuer : Issuer) : Prop :=
  issuer.has_outstanding_convertible_securities_or_options = false

/-- Reg 5(explanation): The restrictions under (a) and (b) above shall not apply to the persons or entities mentioned therein, who were debarred... -/
def reg_5_explanation (issuer : Issuer) : Prop :=
  issuer.is_debarment_period_over = false

/-- Combined Regulation 5 gate -/
def reg_5_eligible (issuer : Issuer) : Prop :=
  reg_5_1_a issuer
  ∧ reg_5_1_b issuer
  ∧ reg_5_1_c issuer
  ∧ reg_5_1_d issuer
  ∧ reg_5_2 issuer

/-! ## Regulation 6 -/
/-- Reg 6(1)(a): it has net tangible assets of at least three crore rupees, calculated on a restated and consolidated basis, in each of t... -/
def reg_6_1_a (issuer : Issuer) : Prop :=
  (issuer.net_tangible_assets_3yr.length = 3 ∧ issuer.net_tangible_assets_3yr.all (· ≥ 1))

/-- Reg 6(1)(b): it has an average operating profit of at least fifteen crore rupees, calculated on a restated and consolidated basis, du... -/
def reg_6_1_b (issuer : Issuer) : Prop :=
  (issuer.operating_profit_avg_crore.length = 3 ∧ issuer.operating_profit_avg_crore.all (· ≥ 1))
  ∧ (issuer.operating_profit_each_year.length = 3 ∧ issuer.operating_profit_each_year.all (· ≥ 1))

/-- Reg 6(1)(c): it has a net worth of at least one crore rupees in each of the preceding three full years (of twelve months each), calcu... -/
def reg_6_1_c (issuer : Issuer) : Prop :=
  (issuer.net_worth_3yr.length = 3 ∧ issuer.net_worth_3yr.all (· ≥ 1))

/-- Reg 6(1)(d): if it has changed its name within the last one year, at least fifty per cent. of the revenue, calculated on a restated a... -/
def reg_6_1_d (issuer : Issuer) : Prop :=
  issuer.revenue_from_new_activity_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 6(1)(proviso): if more than fifty per cent. of the net tangible assets are held in monetary assets, the issuer has utilised or made fir... -/
def reg_6_1_proviso (issuer : Issuer) : Prop :=
  issuer.net_tangible_assets_pct_monetary ≥ 0  -- TODO: set correct threshold

/-- Reg 6(1)(proviso)(2): the limit of fifty per cent. on monetary assets shall not be applicable in case the initial public offer is made entirel... -/
def reg_6_1_proviso_2 (issuer : Issuer) : Prop :=
  issuer.is_initial_public_offer_entirely_ofs = false

/-- Reg 6(2): An issuer not satisfying the condition stipulated in sub-regulation (1) shall be eligible to make an initial public offe... -/
def reg_6_2 (issuer : Issuer) : Prop :=
  issuer.ipo_book_building_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3): The amount for: (i) general corporate purposes, and (ii) such objects where the issuer company has not identified acquis... -/
def reg_6_3 (issuer : Issuer) : Prop :=
  issuer.unidentified_objects_pct_limit ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(i): the issuer shall be intensive in the use of technology, information technology, intellectual property, data analytics, b... -/
def reg_6_3_i (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 6(3)(ii): the net worth of the SR shareholder, as determined by a Registered Valuer, shall not be more than rupees one thousand cr... -/
def reg_6_3_ii (issuer : Issuer) : Prop :=
  issuer.sr_shareholder_net_worth_max_crore ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(iii): The SR shares were issued only to the promoters/ founders who hold an executive position in the issuer company;... -/
def reg_6_3_iii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 6(3)(iv): the issue of SR equity shares had been authorized by a special resolution passed at a general meeting of the shareholder... -/
def reg_6_3_iv (issuer : Issuer) : Prop :=
  issuer.has_special_resolution_authorization = true

/-- Reg 6(3)(iv)(b): ratio of voting rights of SR equity shares vis-à-vis the ordinary shares,... -/
def reg_6_3_iv_b (issuer : Issuer) : Prop :=
  issuer.sr_equity_voting_rights_ratio ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(ix): The SR equity shares shall be equivalent to ordinary equity shares in all respects, except for having superior voting ri... -/
def reg_6_3_ix (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 6(3)(proviso): Provided that the amount raised for such objects where the issuer company has not identified acquisition or investment t... -/
def reg_6_3_proviso (issuer : Issuer) : Prop :=
  issuer.unspecified_use_funds_pct_limit ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(proviso)(2): Provided further that such limits shall not apply if the proposed acquisition or strategic investment object has been id... -/
def reg_6_3_proviso_2 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 6(3)(v): the SR equity shares have been issued prior to the filing of draft red herring prospectus and held for a period of at le... -/
def reg_6_3_v (issuer : Issuer) : Prop :=
  issuer.sr_shares_holding_period_months ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(vi): The SR equity shares shall have voting rights in the ratio of a minimum of 2:1 upto a maximum of 10:1 compared to ordina... -/
def reg_6_3_vi (issuer : Issuer) : Prop :=
  issuer.sr_equity_voting_ratio_min ≥ 0  -- TODO: set correct threshold
  ∧ issuer.sr_equity_voting_ratio_max ≥ 0  -- TODO: set correct threshold

/-- Reg 6(3)(vii): The SR equity shares shall have the same face value as the ordinary shares;... -/
def reg_6_3_vii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 6(3)(viii): The issuer shall only have one class of SR equity shares;... -/
def reg_6_3_viii (issuer : Issuer) : Prop :=
  issuer.has_only_one_sr_equity_class = true

/-- Combined Regulation 6 gate -/
def reg_6_eligible (issuer : Issuer) : Prop :=
  reg_6_1_a issuer
  ∧ reg_6_1_b issuer
  ∧ reg_6_1_c issuer
  ∧ reg_6_1_d issuer
  ∧ reg_6_2 issuer
  ∧ reg_6_3_ii issuer
  ∧ reg_6_3_iv_b issuer
  ∧ reg_6_3_iv issuer
  ∧ reg_6_3_v issuer
  ∧ reg_6_3_vi issuer
  ∧ reg_6_3_viii issuer
  ∧ reg_6_3 issuer

/-! ## Regulation 7 -/
/-- Reg 7(1)(a): it has made an application to one or more stock exchanges to seek an in-principle approval for listing of its specified ... -/
def reg_7_1_a (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 7(1)(b): it has entered into an agreement with a depository for dematerialisation of the specified securities already issued and ... -/
def reg_7_1_b (issuer : Issuer) : Prop :=
  issuer.has_depository_agreement = true

/-- Reg 7(1)(c): all its specified securities held by the promoters are in dematerialised form prior to filing of the offer document;... -/
def reg_7_1_c (issuer : Issuer) : Prop :=
  issuer.promoter_shares_dematerialised = true

/-- Reg 7(1)(d): all its existing partly paid-up equity shares have either been fully paid-up or have been forfeited;... -/
def reg_7_1_d (issuer : Issuer) : Prop :=
  issuer.is_partly_paid_up_shares_forfeited_or_paid_up = true

/-- Reg 7(1)(e): it has made firm arrangements of finance through verifiable means towards seventy five per cent. of the stated means of ... -/
def reg_7_1_e (issuer : Issuer) : Prop :=
  issuer.firm_financial_arrangements_pct ≥ 0  -- TODO: set correct threshold

/-- Reg 7(2): The amount for general corporate purposes, as mentioned in objects of the issue in the draft offer document and the offe... -/
def reg_7_2 (issuer : Issuer) : Prop :=
  issuer.general_corporate_purpose_pct_limit ≥ 0  -- TODO: set correct threshold

/-- Reg 7(explanation): In case of an issuer formed out of a division of an existing company, the track record of distributable profits of the d... -/
def reg_7_explanation (issuer : Issuer) : Prop :=
  issuer.is_financial_statement_compliance_llp_or_pf = true

/-- Reg 7(explanation)(a): adequate disclosures are made in the financial statements as required to be made by the issuer as per schedule III of th... -/
def reg_7_explanation_a (issuer : Issuer) : Prop :=
  issuer.has_required_financial_disclosures = true

/-- Reg 7(explanation)(b): the financial statements are duly certified by the statutory auditor stating that: (i) the accounts and the disclosures ... -/
def reg_7_explanation_b (issuer : Issuer) : Prop :=
  issuer.is_statutory_auditor_certified = true

/-- Reg 7(explanation)(b)(ii): the applicable accounting standards have been followed;... -/
def reg_7_explanation_b_ii (issuer : Issuer) : Prop :=
  issuer.has_followed_accounting_standards = true

/-- Reg 7(explanation)(b)(iii): the financial statements present a true and fair view of the firm’s accounts;... -/
def reg_7_explanation_b_iii (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Combined Regulation 7 gate -/
def reg_7_eligible (issuer : Issuer) : Prop :=
  reg_7_1_b issuer
  ∧ reg_7_1_c issuer
  ∧ reg_7_1_d issuer
  ∧ reg_7_1_e issuer
  ∧ reg_7_2 issuer

/-! ## Regulation 8 -/
/-- Reg 8: Only such fully paid-up equity shares may be offered for sale to the public, which have been held by the sellers for a p... -/
def reg_8 (issuer : Issuer) : Prop :=
  issuer.ofs_holding_period_years_reg8 ≥ 0  -- TODO: set correct threshold

/-- Reg 8(1): in case the equity shares received on conversion or exchange of fully paid-up compulsorily convertible securities includ... -/
def reg_8_1 (issuer : Issuer) : Prop :=
  issuer.holding_period_years ≥ 0  -- TODO: set correct threshold

/-- Reg 8(2): Provided further that such holding period of one year shall be required to be complied with at the time of filing of the... -/
def reg_8_2 (issuer : Issuer) : Prop :=
  issuer.holding_period_months_reg8 ≥ 0  -- TODO: set correct threshold

/-- Reg 8(explanation): If the equity shares arising out of the conversion or exchange of the fully paid-up compulsorily convertible securities ... -/
def reg_8_explanation (issuer : Issuer) : Prop :=
  issuer.is_conversion_exchange_completed_before_filing = true

/-- Reg 8(proviso): Provided that in case the equity shares received on conversion or exchange of fully paid-up compulsorily convertible sec... -/
def reg_8_proviso (issuer : Issuer) : Prop :=
  issuer.convertible_security_and_resultant_share_holding_period_months ≥ 0  -- TODO: set correct threshold

/-- Combined Regulation 8 gate -/
def reg_8_eligible (issuer : Issuer) : Prop :=
  reg_8_2 issuer
  ∧ reg_8 issuer
  ∧ reg_8_1 issuer

/-! ## Composite Chapter II Part I Gate -/

def chapter2_part1_eligible (issuer : Issuer) : Prop :=
  reg_5_eligible issuer
  ∧ reg_6_eligible issuer
  ∧ reg_7_eligible issuer
  ∧ reg_8_eligible issuer

end Reglib.ICDR.Rules
