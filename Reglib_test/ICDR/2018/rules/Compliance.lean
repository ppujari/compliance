-- Auto-generated compliance gate file.

import Reglib.ICDR.rules.Chapter2_Part1
import Reglib.ICDR.rules.Chapter2_Part2
import Reglib.ICDR.rules.Chapter2_Part3
import Reglib.ICDR.rules.Chapter2_Part4
import Reglib.ICDR.rules.Chapter2_Part5
import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules
open Reglib.ICDR

/-! ## Full IPO Compliance Gate -/

def ipo_eligible (issuer : Issuer) : Prop :=
  chapter2_part1_eligible issuer
  ∧ chapter2_part2_eligible issuer
  ∧ chapter2_part3_eligible issuer
  ∧ chapter2_part4_eligible issuer
  ∧ chapter2_part5_eligible issuer

/-! ## Sample Compliant Issuer -/

def sample_compliant_issuer : Issuer := {
  alternative_contribution_max_pct := 20,
  assets_sufficient_principal_discharge := true,
  bonus_issue_holding_period_months := 12,
  convertible_debt_period_months := 12,
  convertible_debt_redemption_period_months := 12,
  convertible_debt_value_threshold := 1,
  convertible_security_and_resultant_share_holding_period_months := 12,
  employee_equity_lock_in_months := 12,
  firm_financial_arrangements_pct := 20,
  general_corporate_purpose_pct_limit := 20,
  has_appointed_debenture_trustee := true,
  has_credit_rating_from_one_agency := true,
  has_debarred_promoter_or_director := false,
  has_depository_agreement := true,
  has_depository_lock_in_record := true,
  has_disclosed_lead_manager_rights_obligations := true,
  has_followed_accounting_standards := true,
  has_fugitive_economic_offender_promoter_or_director := false,
  has_full_disclosures_for_employee_stock_schemes := true,
  has_identifiable_promoter_reg14 := true,
  has_lead_manager_appointed := true,
  has_lock_in_period_reg21 := true,
  has_lock_in_period_reg22 := true,
  has_made_full_disclosures_in_schedule_vi_part_a := true,
  has_non_associate_lead_manager := true,
  has_only_one_sr_equity_class := true,
  has_outstanding_convertible_securities_or_options := false,
  has_positive_consent_from_holders := true,
  has_price_comparison_requirement := true,
  has_promoter_contribution_disclosure := true,
  has_required_financial_disclosures := true,
  has_special_resolution_authorization := true,
  holding_period_months_reg17 := 12,
  holding_period_months_reg8 := 12,
  holding_period_years := 1,
  ipo_book_building_pct := 20,
  is_conditions_satisfied_filing_date := true,
  is_conversion_exchange_completed_before_filing := true,
  is_debarment_period_over := true,
  is_debarred := false,
  is_financial_statement_compliance_llp_or_pf := true,
  is_free_from_encumbrance := true,
  is_initial_public_offer_entirely_ofs := true,
  is_partly_paid_up_shares_forfeited_or_paid_up := true,
  is_promoter_securities_pledged := false,
  is_redeeming_convertible_debt_instruments := true,
  is_revalued_assets_or_intangibles_capitalised_in_transaction := true,
  is_statutory_auditor_certified := true,
  is_wilful_defaulter_or_fraudulent_borrower := false,
  lock_in_period_for_capital_expenditure_years := 1,
  net_tangible_assets_3yr := [10, 12, 15],
  net_tangible_assets_pct_monetary := 20,
  net_worth_3yr := [10, 12, 15],
  no_convertible_debt_for_promoter_group_financing := true,
  no_default_on_debt_payments_months := 12,
  no_default_payment_more_than_six_months := true,
  non_individual_public_shareholder_pct := 20,
  non_promoter_lock_in_period_months := 12,
  ofs_holding_period_months_reg16 := 12,
  ofs_holding_period_months_reg17 := 12,
  ofs_holding_period_remaining_months := 12,
  ofs_holding_period_years_reg19 := 1,
  ofs_holding_period_years_reg8 := 1,
  operating_profit_avg_crore := [10, 12, 15],
  operating_profit_each_year := [10, 12, 15],
  promoter_contribution_lock_in_months := 12,
  promoter_contribution_mechanism := "direct",
  promoter_contribution_min_crore := 10,
  promoter_contribution_pct := 20,
  promoter_contribution_pct_issue_size := 20,
  promoter_contribution_pct_project_cost := 20,
  promoter_contribution_pct_till_stage := 20,
  promoter_contribution_price_not_lower_than_weighted_avg := true,
  promoter_holding_period_years := 1,
  promoter_investment_period_years := 1,
  promoter_lock_in_period_months := 12,
  promoter_min_contribution_pct := 20,
  promoter_min_holding_pct := 20,
  promoter_payment_difference := true,
  promoter_requirements_compliance_date := 1,
  promoter_shares_dematerialised := true,
  revenue_from_new_activity_pct := 20,
  sr_equity_voting_ratio_max := 20,
  sr_equity_voting_ratio_min := 20,
  sr_equity_voting_rights_ratio := 20,
  sr_shareholder_net_worth_max_crore := 10,
  sr_shares_holding_period_months := 12,
  unidentified_objects_pct_limit := 20,
  unspecified_use_funds_pct_limit := 20,
  warrant_formula_consideration_pct := 20,
  promoters := [
    { is_debarred := false
      debarment_period_over := false
      is_director_of_debarred_company := false
      is_wilful_defaulter_or_fraudulent := false
      is_fugitive_economic_offender := false
      holding_pct := 25 }
  ]
}

/-! ## Smoke-Test Proofs -/

theorem sample_passes_reg5 :
    reg_5_eligible sample_compliant_issuer := by
  unfold reg_5_eligible reg_5_1_a reg_5_1_b reg_5_1_c reg_5_1_d reg_5_2
  simp [sample_compliant_issuer, List.all]

end Reglib.ICDR.Rules
