-- Auto-generated from SEBI_ICDR_2018; DO NOT EDIT MANUALLY.

namespace Reglib.ICDR

abbrev INR_Crore := Nat
abbrev Pct       := Nat
abbrev Months    := Nat
abbrev Years     := Nat

inductive IssueType where
  | IPO | FPO | RightsIssue | QIP | Preferential | SME_IPO
  deriving DecidableEq, Repr

inductive SecurityType where
  | EquityShares | ConvertibleDebt | ConvertiblePreference | Warrants
  deriving DecidableEq, Repr

structure Promoter where
  is_debarred                       : Bool
  debarment_period_over             : Bool
  is_director_of_debarred_company   : Bool
  is_wilful_defaulter_or_fraudulent : Bool
  is_fugitive_economic_offender     : Bool
  holding_pct                       : Pct
  deriving Repr

structure Issuer where
  -- -- Regulation 4 --
  /-- Unless otherwise provided in this Chapter, an issuer making an initial public offer of specified securities shall satisf -/
  is_conditions_satisfied_filing_date : Bool
  -- -- Regulation 5(1)(a) --
  /-- if the issuer, any of its promoters, promoter group or directors or selling shareholders are debarred from accessing the -/
  is_debarred                        : Bool
  -- -- Regulation 5(1)(b) --
  /-- if any of the promoters or directors of the issuer is a promoter or director of any other company which is debarred from -/
  has_debarred_promoter_or_director  : Bool
  -- -- Regulation 5(1)(c) --
  /-- if the issuer or any of its promoters or directors is a [wilful defaulter or a fraudulent borrower.] -/
  is_wilful_defaulter_or_fraudulent_borrower : Bool
  -- -- Regulation 5(1)(d) --
  /-- if any of its promoters or directors is a fugitive economic offender. -/
  has_fugitive_economic_offender_promoter_or_director : Bool
  -- -- Regulation 5(2) --
  /-- An issuer shall not be eligible to make an initial public offer if there are any outstanding convertible securities or a -/
  has_outstanding_convertible_securities_or_options : Bool
  -- -- Regulation 5(explanation) --
  /-- The restrictions under (a) and (b) above shall not apply to the persons or entities mentioned therein, who were debarred -/
  is_debarment_period_over           : Bool
  -- -- Regulation 6(1)(a) --
  /-- at least three crore rupees, not more than fifty per cent. are held in monetary assets -/
  net_tangible_assets_3yr            : List INR_Crore
  -- -- Regulation 6(1)(b) --
  /-- length=3 -/
  operating_profit_avg_crore         : List INR_Crore
  /-- it has an average operating profit of at least fifteen crore rupees, calculated on a restated and consolidated basis, du -/
  operating_profit_each_year         : List INR_Crore
  -- -- Regulation 6(1)(c) --
  /-- at least one crore rupees -/
  net_worth_3yr                      : List INR_Crore
  -- -- Regulation 6(1)(d) --
  /-- at least fifty per cent -/
  revenue_from_new_activity_pct      : Nat
  -- -- Regulation 6(1)(proviso) --
  /-- if more than fifty per cent. of the net tangible assets are held in monetary assets, the issuer has utilised or made fir -/
  net_tangible_assets_pct_monetary   : Nat
  -- -- Regulation 6(1)(proviso)(2) --
  /-- the limit of fifty per cent. on monetary assets shall not be applicable in case the initial public offer is made entirel -/
  is_initial_public_offer_entirely_ofs : Bool
  -- -- Regulation 6(2) --
  /-- at least seventy five per cent -/
  ipo_book_building_pct              : Nat
  -- -- Regulation 6(3) --
  /-- shall not exceed thirty five per cent -/
  unidentified_objects_pct_limit     : Nat
  -- -- Regulation 6(3)(ii) --
  /-- rupees one thousand crore -/
  sr_shareholder_net_worth_max_crore : Nat
  -- -- Regulation 6(3)(iv) --
  /-- the issue of SR equity shares had been authorized by a special resolution passed at a general meeting of the shareholder -/
  has_special_resolution_authorization : Bool
  -- -- Regulation 6(3)(iv)(b) --
  /-- ratio of voting rights of SR equity shares vis-à-vis the ordinary shares, -/
  sr_equity_voting_rights_ratio      : Nat
  -- -- Regulation 6(3)(proviso) --
  /-- 25% -/
  unspecified_use_funds_pct_limit    : Nat
  -- -- Regulation 6(3)(v) --
  /-- at least three months -/
  sr_shares_holding_period_months    : Months
  -- -- Regulation 6(3)(vi) --
  /-- minimum of 2:1 -/
  sr_equity_voting_ratio_min         : Nat
  /-- upto a maximum of 10:1 -/
  sr_equity_voting_ratio_max         : Nat
  -- -- Regulation 6(3)(viii) --
  /-- The issuer shall only have one class of SR equity shares; -/
  has_only_one_sr_equity_class       : Bool
  -- -- Regulation 7(1)(b) --
  /-- it has entered into an agreement with a depository for dematerialisation of the specified securities already issued and -/
  has_depository_agreement           : Bool
  -- -- Regulation 7(1)(c) --
  /-- all its specified securities held by the promoters are in dematerialised form prior to filing of the offer document; -/
  promoter_shares_dematerialised     : Bool
  -- -- Regulation 7(1)(d) --
  /-- all its existing partly paid-up equity shares have either been fully paid-up or have been forfeited; -/
  is_partly_paid_up_shares_forfeited_or_paid_up : Bool
  -- -- Regulation 7(1)(e) --
  /-- seventy five per cent. -/
  firm_financial_arrangements_pct    : Nat
  -- -- Regulation 7(2) --
  /-- twenty five per cent -/
  general_corporate_purpose_pct_limit : Nat
  -- -- Regulation 7(explanation) --
  /-- In case of an issuer formed out of a division of an existing company, the track record of distributable profits of the d -/
  is_financial_statement_compliance_llp_or_pf : Bool
  -- -- Regulation 7(explanation)(a) --
  /-- adequate disclosures are made in the financial statements as required to be made by the issuer as per schedule III of th -/
  has_required_financial_disclosures : Bool
  -- -- Regulation 7(explanation)(b) --
  /-- the financial statements are duly certified by the statutory auditor stating that: (i) the accounts and the disclosures -/
  is_statutory_auditor_certified     : Bool
  -- -- Regulation 7(explanation)(b)(ii) --
  /-- the applicable accounting standards have been followed; -/
  has_followed_accounting_standards  : Bool
  -- -- Regulation 8 --
  /-- at least one year -/
  ofs_holding_period_years_reg8      : Years
  -- -- Regulation 8(1) --
  /-- in case the equity shares received on conversion or exchange of fully paid-up compulsorily convertible securities includ -/
  holding_period_years               : Years
  -- -- Regulation 8(2) --
  /-- one year -/
  holding_period_months_reg8         : Months
  -- -- Regulation 8(explanation) --
  /-- If the equity shares arising out of the conversion or exchange of the fully paid-up compulsorily convertible securities -/
  is_conversion_exchange_completed_before_filing : Bool
  -- -- Regulation 8(proviso) --
  /-- Provided that in case the equity shares received on conversion or exchange of fully paid-up compulsorily convertible sec -/
  convertible_security_and_resultant_share_holding_period_months : Months
  -- -- Regulation 9 --
  /-- for a period of more than six months -/
  no_default_payment_more_than_six_months : Bool
  -- -- Regulation 9(proviso) --
  /-- for a period of more than six months -/
  no_default_on_debt_payments_months : Months
  -- -- Regulation 10(1)(a) --
  /-- it has obtained credit rating from at least one credit rating agency; -/
  has_credit_rating_from_one_agency  : Bool
  -- -- Regulation 10(1)(b) --
  /-- it has appointed at least one debenture trustee in accordance with the provisions of the Companies Act, 2013 and the Sec -/
  has_appointed_debenture_trustee    : Bool
  -- -- Regulation 10(1)(d)(i) --
  /-- such assets are sufficient to discharge the principal amount at all times; -/
  assets_sufficient_principal_discharge : Bool
  -- -- Regulation 10(1)(d)(ii) --
  /-- such assets are free from any encumbrance; -/
  is_free_from_encumbrance           : Bool
  -- -- Regulation 10(2) --
  /-- The issuer shall redeem the convertible debt instruments in terms of the offer document. -/
  is_redeeming_convertible_debt_instruments : Bool
  -- -- Regulation 11(1) --
  /-- The issuer shall not convert its optionally convertible debt instruments into equity shares unless the holders of such c -/
  has_positive_consent_from_holders  : Bool
  -- -- Regulation 11(2) --
  /-- ten crore rupees -/
  convertible_debt_value_threshold   : INR_Crore
  -- -- Regulation 11(3) --
  /-- Where an option is to be given to the holders of the convertible debt instruments in terms of sub-regulation (2) and if -/
  convertible_debt_redemption_period_months : Months
  -- -- Regulation 12 --
  /-- An issuer shall not issue convertible debt instruments for financing or for providing loans to or for acquiring shares o -/
  no_convertible_debt_for_promoter_group_financing : Bool
  -- -- Regulation 12(proviso) --
  /-- < 18 -/
  convertible_debt_period_months     : Months
  -- -- Regulation 13(proviso) --
  /-- twenty-five per cent -/
  warrant_formula_consideration_pct  : Nat
  -- -- Regulation 14(1) --
  /-- The promoters of the issuer shall hold at least twenty per cent. of the post-issue capital: -/
  promoter_min_holding_pct           : Nat
  -- -- Regulation 14(1)(proviso) --
  /-- ten per cent. of the post-issue capital -/
  alternative_contribution_max_pct   : Nat
  -- -- Regulation 14(1)(proviso)(2)(that) --
  /-- Provided further that the requirement of minimum promoters’ contribution shall not apply in case an issuer does not have -/
  has_identifiable_promoter_reg14    : Bool
  -- -- Regulation 14(2) --
  /-- The minimum promoters’ contribution shall be as follows: -/
  promoter_min_contribution_pct      : Nat
  -- -- Regulation 14(3) --
  /-- at least one day -/
  promoter_requirements_compliance_date : Nat
  -- -- Regulation 14(4)(proviso) --
  /-- where the promoters’ contribution has already been brought in and utilised, the issuer shall give the cash flow statemen -/
  has_promoter_contribution_disclosure : Bool
  -- -- Regulation 14(4)(proviso)(2) --
  /-- at least one hundred crore rupees -/
  promoter_contribution_min_crore    : Nat
  -- -- Regulation 14(a) --
  /-- twenty per cent -/
  promoter_contribution_pct          : Nat
  -- -- Regulation 14(a)(proviso) --
  /-- only by way of subscription to the convertible securities -/
  promoter_contribution_mechanism    : String
  -- -- Regulation 14(b) --
  /-- in case of any issue of convertible securities which are convertible or exchangeable on different dates and if the promo -/
  promoter_contribution_price_not_lower_than_weighted_avg : Bool
  -- -- Regulation 14(c) --
  /-- at least twenty per cent. of the project cost -/
  promoter_contribution_pct_project_cost : Nat
  /-- contributing at least twenty per cent. of the issue size from their own funds in the form of equity shares -/
  promoter_contribution_pct_issue_size : Nat
  -- -- Regulation 14(c)(proviso) --
  /-- if the project is to be implemented in stages, the promoters’ contribution shall be with respect to total equity partici -/
  promoter_contribution_pct_till_stage : Nat
  -- -- Regulation 15(1)(a) --
  /-- specified securities acquired during the preceding three years, if these are: acquired for consideration other than cash -/
  is_revalued_assets_or_intangibles_capitalised_in_transaction : Bool
  -- -- Regulation 15(1)(b) --
  /-- specified securities acquired by the promoters and alternative investment funds or foreign venture capital investors or -/
  has_price_comparison_requirement   : Bool
  -- -- Regulation 15(proviso) --
  /-- at least five per cent. -/
  non_individual_public_shareholder_pct : Nat
  -- -- Regulation 15(proviso)(i) --
  /-- if the promoters and alternative investment funds or foreign venture capital investors or scheduled commercial banks or -/
  promoter_payment_difference        : Bool
  -- -- Regulation 15(proviso)(ii) --
  /-- more than one year -/
  promoter_investment_period_years   : Years
  -- -- Regulation 15(proviso)(iv) --
  /-- at least one year -/
  promoter_holding_period_years      : Years
  -- -- Regulation 16 --
  /-- The specified securities held by the promoters shall not be transferable (hereinafter referred to as “lock-in”) for the -/
  promoter_lock_in_period_months     : Months
  -- -- Regulation 16(1) --
  /-- eighteen months -/
  promoter_contribution_lock_in_months : Months
  -- -- Regulation 16(1)(proviso) --
  /-- three years -/
  lock_in_period_for_capital_expenditure_years : Years
  -- -- Regulation 16(b) --
  /-- promoters’ holding in excess of minimum promoters’ contribution shall be locked-in for a period of [six months] from the -/
  ofs_holding_period_months_reg16    : Months
  -- -- Regulation 17 --
  /-- six months -/
  non_promoter_lock_in_period_months : Months
  -- -- Regulation 17(a) --
  /-- equity shares allotted to employees, whether currently an employee or not, under an employee stock option or employee st -/
  has_made_full_disclosures_in_schedule_vi_part_a : Bool
  -- -- Regulation 17(explanation)(i) --
  /-- For the purpose of clause (c), in case such equity shares have resulted pursuant to conversion of fully paid-up compulso -/
  holding_period_months_reg17        : Months
  -- -- Regulation 17(explanation)(ii) --
  /-- For the purpose of clause (c), in case such equity shares have resulted pursuant to a bonus issue, then the holding peri -/
  bonus_issue_holding_period_months  : Months
  -- -- Regulation 17(proviso) --
  /-- nothing contained in this regulation shall apply to: a) equity shares allotted to employees, whether currently an employ -/
  has_full_disclosures_for_employee_stock_schemes : Bool
  /-- such equity shares shall be locked in for a period of at least six months from the date of purchase by the venture capit -/
  ofs_holding_period_months_reg17    : Months
  -- -- Regulation 17(proviso)(2) --
  /-- the equity shares allotted to the employees shall be subject to the provisions of lock-in as specified under the [Securi -/
  employee_equity_lock_in_months     : Months
  -- -- Regulation 18(proviso) --
  /-- Provided that the specified securities shall be locked-in for the remaining period from the date on which they are retur -/
  ofs_holding_period_remaining_months : Months
  -- -- Regulation 19 --
  /-- three years -/
  ofs_holding_period_years_reg19     : Years
  -- -- Regulation 20 --
  /-- The certificates of specified securities which are subject to lock-in shall contain the inscription “non-transferable” a -/
  has_depository_lock_in_record      : Bool
  -- -- Regulation 21 --
  /-- Specified securities[, except SR equity shares,] held by the promoters and locked-in may be pledged as a collateral secu -/
  is_promoter_securities_pledged     : Bool
  -- -- Regulation 21(proviso) --
  /-- Provided that such lock-in shall continue pursuant to the invocation of the pledge and such transferee shall not be elig -/
  has_lock_in_period_reg21           : Bool
  -- -- Regulation 22(proviso) --
  /-- Provided that the lock-in on such specified securities shall continue for the remaining period with the transferee and s -/
  has_lock_in_period_reg22           : Bool
  -- -- Regulation 23(1) --
  /-- The issuer shall appoint one or more merchant bankers, which are registered with the Board, as lead manager(s) to the is -/
  has_lead_manager_appointed         : Bool
  -- -- Regulation 23(2) --
  /-- Where the issue is managed by more than one lead manager, the rights, obligations and responsibilities, relating inter a -/
  has_disclosed_lead_manager_rights_obligations : Bool
  -- -- Regulation 23(3) --
  /-- At least one lead manager to the issue shall not be an associate (as defined under the Securities and Exchange Board of -/
  has_non_associate_lead_manager     : Bool
  /-- All promoters (for list-level Reg 5 checks) -/
  promoters                          : List Promoter
  deriving Repr

end Reglib.ICDR
