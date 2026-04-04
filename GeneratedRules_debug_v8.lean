import Main
open Main
namespace GeneratedRules

def generatedRuleset : List ComplianceRule := [
{ id := "ICDR_6_1_a", title := "Net tangible assets ≥ ₹3 cr, with limit on monetary assets", reference := "6(1)(a)", check := net_tangible_assets_check, failReason := net_tangible_assets_failReason },
  { id := "ICDR_6_1_b", title := "Operating profit ≥ ₹15 cr in each of last 3 years", reference := "6(1)(b)", check := operating_profits_check, failReason := operating_profits_failReason },
  { id := "ICDR_6_1_c", title := "Net worth ≥ ₹1 cr in each of last 3 years", reference := "Regulation 6(1)(c)", check := net_worth_check, failReason := net_worth_failReason },
  { id := "ICDR_7_1_a", title := "Application for in-principle approval", reference := "Regulation 7(1)(a)", check := in_principle_approval_application },
  { id := "ICDR_7_1_b", title := "Agreement with depository for dematerialisation", reference := "Regulation 7(1)(b)", check := agreement_with_depository },

{ id := "ICDR_7_1_c", title := "Dematerialised form of promoter's securities", reference := "Regulation 7(1)(c)", maps_to := [ { field := "promoter_securities_dematerialised" } ], check := fun i => i.promoter_securities_dematerialised, failReason := fun i => "Promoters' securities not in dematerialised form." },
  { id := "ICDR_7_1_d", title := "Fully paid-up equity shares or forfeiture", reference := "Regulation 7(1)(d)", maps_to := [ { field := "fully_paid_up_equity_shares" } ], check := fun i => i.fully_paid_up_equity_shares, failReason := fun i => "Existing partly paid-up equity shares not fully paid-up or forfeited." },
  { id := "ICDR_7_1_e", title := "Firm arrangements of finance", reference := "General conditions", maps_to := [ { field := "finance_arrangements", type_hint := "OptionListNat" } ], check := fun i => i.finance_arrangements.sum > (75 * i.offer_size), failReason := fun i => "Firm arrangements of finance for less than 75% of the project's funding." },
  { id := "ICDR_8", title := "Minimum holding period for equity shares offered for sale", reference := "Regulation 8", maps_to := [ { field := "min_holding_period", type_hint := "Nat" } ], check := fun i => i.equity_shares_held_for_sale.all (fun x => x >= 1), failReason := fun i => "Equity shares offered for sale not held for at least one year." },
  { id := "ICDR_8_1", title := "Holding period for convertible securities and resulting equity shares", reference := "ICDR_8_1", maps_to := [ { field := "convertible_securities", type_hint := "List Nat" } ], check := fun i => i.convertible_securities.all (fun x => i.equity_shares_resulting_from_conversion.getOrElse(x, 0) >= 1), failReason := fun i => "Convertible securities and resulting equity shares not held for at least one year." },

{ id := "ICDR_6_8_provided", title := "Max sale of equity shares for unidentified targets", reference := "Regulation 6(8)",
    check := fun i => i.max_sale_unidentified_targets <= 25,
    failReason := fun i => "Maximum sale exceeded 25%.", remedy? := none },
  { id := "ICDR_6_8_provided_further", title := "Exceptions to max sale for general corporate purposes", reference := "Regulation 6(8)", check := fun _ => True,
    failReason := fun _ => "No specific disclosures about acquisitions or investments were made." },
  { id := "ICDR_8_provided_further", title := "Additional conditions for conversion of compulsorily convertible securities", reference := "Regulation 8", check := fun i => i.convertible_securities_conditions,
    failReason := fun _ => "Convertible securities issued from revaluation reserves or unrealized profits." },
  { id := "ICDR_9", title := "Issuer may issue convertible debt instruments without prior equity IPO", reference := "Regulation 9",
    check := fun i => i.eligible_for_cdi_without_prior_ipo, failReason := fun _ => "Issuer is in default of payment or repayment for more than six months." },
  { id := "ICDR_10_1a", title := "Credit rating required for CDI offer", reference := "Regulation 10(1)(a)",
    check := fun i => i.credit_rating_required, failReason := fun _ => "No credit rating obtained from any agency." },

{ id := "ICDR_9_6", title := "Default payment of interest or repayment of principal", reference := "Regulation 9",
    check := fun i => i.default_payment_status == some true,
    failReason := fun i => "Issuer is in default of payment of interest or repayment of principal amount for a period of more than six months.", remedy? := none },
  { id := "ICDR_10_a", title := "Credit rating and debenture trustee requirements", reference := "Regulation 10(1)(a)",
    check := fun i => (i.credit_rating.isSome) && (i.debenture_trustee.length > 0),
    failReason := fun i =>
      if not i.credit_rating.isSome then "Issuer has not obtained credit rating from at least one credit rating agency."
                                        else if i.debenture_trustee.isEmpty then "Issuer has not appointed at least one debenture trustee.", remedy? := none },
  { id := "ICDR_10_c", title := "Debenture redemption reserve", reference := "Regulation 10(1)(c)",
    check := fun i => i.debenture_redemption_reserve == some true,
    failReason := fun i => "Issuer has not created a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules made thereunder.", remedy? := none },
  { id := "ICDR_11_1", title := "Consent for conversion of convertible debt instruments", reference := "Regulation 11(1)",
    check := fun i => i.consent_for_conversion,
    failReason := fun i => "Issuer has not obtained positive consent from holders for the conversion of optionally convertible debt instruments into equity shares.", remedy? := none },
  { id := "ICDR_11_2", title := "Option to not convert convertible portion into equity shares", reference := "Regulation 11(2)",
    check := fun i => (i.convertible_debt_value > 10000000) && (i.option_not_convert.isSome),
    failReason := fun i =>
      if (i.convertible_debt_value <= 10000000) then "The value of the convertible portion of any listed convertible debt instruments issued by an issuer is less than ten crore rupees."
                                                   else if not i.option_not_convert.isSome then "Holders of such convertible debt instruments have not been given the option of not converting the convertible portion into equity shares.", remedy? := none },

{ id := "ICDR_13_a", title := "Warrant tenure ≤ 18 months", reference := "Regulation 13(a)",
    check := fun i => i.warrant_tenure <= 18 * 12,
    failReason := fun i => s!"Warrant tenure exceeds 18 months. Tenure: {i.warrant_tenure}",
    remedy? := none },
  { id := "ICDR_13_c", title := "Warrant exercise price formula and upfront payment", reference := "Regulation 13(c)",
    check := fun i => i.warrant_exercise_price.isSome && i.upfront_payment > (25 / 100) * i.warrant_exercise_price.get,
    failReason := fun i =>
      if not i.warrant_exercise_price.isSome then s!"Warrant exercise price is missing."
      else if not (i.upfront_payment > (25 / 100) * i.warrant_exercise_price.get) then s!"Upfront payment should be at least 25% of the consideration amount based on the exercise price.",
    remedy? := none },
  { id := "ICDR_13_d", title := "Forfeiture of consideration for un-exercised warrants", reference := "Regulation 13(d)",
    check := fun i => i.warrant_tenure <= 3 * 12 && (i.warrant_exercise_price.isNone || i.upfront_payment > 0),
    failReason := fun i =>
      if i.warrant_tenure > 3 * 12 then s!"Warrant tenure exceeds 3 months."
      else if i.warrant_exercise_price.isSome && i.upfront_payment == 0 then s!"Upfront payment should be received for un-exercised warrants.",
    remedy? := none },
  { id := "ICDR_14_1", title := "Minimum promoters’ contribution ≥ 20%", reference := "Regulation 14(1)",
    check := fun i => i.promoter_contribution >= 20 * 100,
    failReason := fun i => s!"Promoters' contribution is less than 20%. Contribution: {i.promoter_contribution}",
    remedy? := none },
  { id := "ICDR_14_1_a", title := "Promoter contribution by equity shares or convertible securities", reference := "Regulation 14(1)",
    check := fun i => i.contribution_method.isSome,
    failReason := fun i => s!"Contribution method is missing.",
    remedy? := none },

{ id := "ICDR_14_1_b", title := "Undisclosed conversion price", reference := "Regulation 14(1)", check := fun i => i.promoter_contribution_undisclosed, failReason := fun i => "Promoter contribution not specified in the offer document." },
  { id := "ICDR_6_3", title := "Promoters' contribution computation", reference := "ICDR_6_3", check := fun i => (i.promoter_contribution_computation_method.length == 2) && i.promoter_contribution_computation_method.all (fun x => x.1 == "post-issue expanded capital" && (x.2 == "full proposed conversion of convertible securities into equity shares" || x.2 == "exercise of all vested options, where any employee stock options or stock appreciation rights are outstanding at the time of initial public offer in terms of proviso (a) to sub-regulation (2) of regulation 5")), failReason := fun i => "Incorrect promoters' contribution computation method." },
  { id := "ICDR_6_4", title := "Securities ineligible for minimum promoters’ contribution", reference := "ICDR_6_4", check := fun i => (i.securities_ineligible.length > 0) && i.securities_ineligible.all (fun x => x >= 1 && x <= 3), failReason := fun i => "Incorrect number of ineligible securities." },
  { id := "ICDR_12_a", title := "Promoters’ contribution computation", reference := "ICDR_12_a", check := fun i => i.promoter_contribution_computation_method.all (fun x => x.1 == "post-issue expanded capital"), failReason := fun i => "Incorrect promoters' contribution computation method." },
  { id := "ICDR_12_a_ii", title := "Exercise of employee stock options or SARs", reference := "ICDR_12_a_ii", check := fun i => i.employee_stock_options_or_SARs_exercise, failReason := fun i => "No assumption made for exercising employee stock options or SARs." },

{ id := "ICDR_4_13_a", title := "Payment for specified securities acquired by promoters", reference := "Regulation 4(1)(a)", check := fun i => i.specified_securities.all (fun x => i.promoter_payments.exists (λ p, p.securities == x && p.price < i.issue_price)), failReason := fun i => "Promoters paid more than issue price for some specified securities.", remedy? := some "Ensure promoters pay the issue price for all specified securities." },
  { id := "ICDR_4_13_b", title := "Payment for specified securities acquired under Companies Act", reference := "Regulation 4(1)(b)", check := fun i => i.specified_securities.all (fun x => i.companies_act_approvals.exists (λ a, a.securities == x && a.price < i.issue_price) && i.promoter_investments.exists (λ p, p.time > 1 && p.year <= a.year)), failReason := fun i => "Promoters did not invest for more than one year prior to approval or specified securities were not acquired under Companies Act.", remedy? := some "Ensure promoters invested business and capital that had been in existence for a period of more than one year prior to such approval." },
  { id := "ICDR_4_13_c", title := "Payment for specified securities in government company IPO", reference := "Regulation 4(1)(c)", check := fun i => i.specified_securities.all (fun x => i.government_ipos.exists (λ g, g.securities == x)), failReason := fun i => "Initial public offer was not by a government company, statutory authority or corporation or any special purpose vehicle set up by any of them, engaged in the infrastructure sector.", remedy? := some "Ensure initial public offer is made by a government company, statutory authority or corporation." },
  { id := "ICDR_4_13_d", title := "Specified securities allotted to promoters at a price less than issue price", reference := "Regulation 4(1)(d)", check := fun i => i.specified_securities.all (fun x => i.promoter_transactions.exists (λ t, t.securities == x && t.price < i.issue_price) && t.time <= 1), failReason := fun i => "Specified securities were not allotted to promoters at a price less than the issue price within the preceding one year.", remedy? := some "Ensure specified securities are allotted to promoters at a price less than the issue price during the preceding one year." },
  { id := "ICDR_16_1", title := "Lock-in of specified securities held by the promoters", reference := "ICDR_16_1", check := fun i => i.securities_held_by_promoters.all (fun x => i.lock_in_periods.exists (λ p, p.securities == x && p.time <= p.end)), failReason := fun i => "Specified securities held by promoters are transferable outside the lock-in period.", remedy? := some "Ensure specified securities held by promoters are not transferable during the lock-in period." },

{ id := "ICDR_16_49a", title := "Promoter lock-in period (18 months)", reference := "Regulation 16(49)",
    check := fun i => match i.lock_in_period with
                        some 18 => True
                      | _ => False,
    failReason := fun i => if i.lock_in_period.isSome then "Lock-in period should be 18 for promoter contribution." else "Missing lock-in period for promoter contribution.",
    remedy? := some "Specify the lock-in period of 18 months for promoter contribution." },

  { id := "ICDR_16_49b", title := "Promoter excess holding lock-in (6 months)", reference := "Regulation 16(49)",
    check := fun i => match i.lock_in_period with
                        some 6 => True
                      | _ => False,
    failReason := fun i => if i.lock_in_period.isSome then "Lock-in period should be 6 for promoter excess holding." else "Missing lock-in period for promoter excess holding.",
    remedy? := some "Specify the lock-in period of 6 months for promoter excess holding." },

  { id := "ICDR_17", title := "Other persons' lock-in (6 months)", reference := "ICDR_17",
    check := fun i => match i.lock_in_period with
                        some x => x == 6
                      | _ => False,
    failReason := fun i => if i.lock_in_period.isSome then "Lock-in period should be 6 for equity shares held by persons other than promoters." else "Missing lock-in period for equity shares held by persons other than promoters.",
    remedy? := some "Specify the lock-in period of 6 months for equity shares held by persons other than promoters." },

  { id := "ICDR_17_c", title := "Venture capital funds' lock-in (6 months)", reference := "ICDR_17_c",
    check := fun i => match i.lock_in_period with
                        some x => x == 6
                      | _ => False,
    failReason := fun i => if i.lock_in_period.isSome then "Lock-in period should be 6 for equity shares held by venture capital funds or alternative investment funds." else "Missing lock-in period for equity shares held by venture capital funds or alternative investment funds.",
    remedy? := some "Specify the lock-in period of 6 months for equity shares held by venture capital funds or alternative investment funds." },

{ id := "ICDR_21_a", title := "Pledge of locked-in specified securities (a)", reference := "Regulation 21(a)", check := fun i => i.locked_in_securities.length > 0 && i.locked_in_securities.all (fun x => x != 0) && i.issuer_or_subsidiary && i.loan_for_issue_financing, failReason := fun i => if !i.locked_in_securities.length > 0 then "Need locked-in specified securities." else if !i.locked_in_securities.all (fun x => x != 0) then "All locked-in specified securities must be non-zero." else if !i.issuer_or_subsidiary then "Loan granted to issuer company or its subsidiary(ies) is required." else if !i.loan_for_issue_financing then "Loan was not granted for the purpose of financing one or more of the objects of the issue." },
  { id := "ICDR_21_b", title := "Pledge of locked-in specified securities (b)", reference := "Regulation 21(b)", check := fun i => i.locked_in_securities.length > 0 && i.locked_in_securities.all (fun x => x != 0) && i.loan_terms, failReason := fun i => if !i.locked_in_securities.length > 0 then "Need locked-in specified securities." else if !i.locked_in_securities.all (fun x => x != 0) then "All locked-in specified securities must be non-zero." else if !i.loan_terms then "Pledge of specified securities is not one of the terms of sanction of the loan." },
  { id := "ICDR_21", title := "Pledge of locked-in specified securities", reference := "Regulation 21", check := fun i => i.locked_in_securities.length > 0 && i.locked_in_securities.all (fun x => x != 0) && !i.sr_equity_shares, failReason := fun i => if !i.locked_in_securities.length > 0 then "Need locked-in specified securities." else if !i.locked_in_securities.all (fun x => x != 0) then "All locked-in specified securities must be non-zero." else if i.sr_equity_shares then "SR equity shares are excluded from pledging." },
  { id := "ICDR_22", title := "Transfer of locked-in specified securities", reference := "ICDR_22", failReason := fun i => "Provisions for transfer of locked-in specified securities are subject to other SEBI regulations. No check provided." },
  { id := "ICDR_23", title := "Rights, obligations and responsibilities of lead managers", reference := "ICDR_23", check := fun i => i.lead_manager_roles.isDefined, failReason := fun i => if !i.lead_manager_roles.isDefined then "Lead manager roles are not predetermined and disclosed." }
]

def issuerQuestions : List (String × String × String) := [
("net_tangible_assets", "What is the net tangible assets of the company?", "List Nat"),
  ("monetary_assets", "What percentage of net tangible assets are held in monetary assets?", "Nat"),
  ("operating_profits", "Provide the operating profits for the last three years.", "List Nat"),
  ("net_worth", "What is the net worth of the company for the last three years?", "List Nat"),
  ("in_principle_approval_application", "Has an application been made to one or more stock exchanges for in-principle approval?"),
  ("agreement_with_depository", "Is there an agreement with a depository for dematerialisation of the specified securities?"),
{ fieldName := "promoter_securities_dematerialised", question := "Is the dematerialisation status of promoters' securities available?", type := "Bool" },
  { fieldName := "fully_paid_up_equity_shares", question := "What is the number of fully paid-up equity shares held by the issuer?", type := "Nat" },
  { fieldName := "finance_arrangements", question := "What are the firm arrangements of finance towards seventy five per cent. of the stated means of finance for a specific project proposed to be funded from the issue proceeds, excluding the amount to be raised through the proposed public issue or through existing identifiable internal accruals?", type := "OptionListNat" },
  { fieldName := "equity_shares_held_for_sale", question := "What is the number of equity shares held by the issuer for sale to the public?", type := "List Nat" },
  { fieldName := "convertible_securities", question := "What are the convertible securities held by the issuer?", type := "List Nat" },
{ "max_sale_unidentified_targets", "What percentage of funds can be used for unidentified acquisition or investment targets?", "Nat" },
  { "convertible_securities_conditions", "Do the conditions for conversion or exchange of compulsorily convertible securities apply?", "Bool" },
  { "eligible_for_cdi_without_prior_ipo", "Is the issuer eligible to make an initial public offer of convertible debt instruments without a prior public issue of its equity shares and listing thereof?", "Bool" },
  { "credit_rating_required", "Has the issuer obtained credit rating from at least one credit rating agency for the CDI offer?" , "Bool" },
("default_payment_status", "Has the issuer defaulted on payment of interest or principal for more than six months?", "OptionBool"),
  ("credit_rating", "Has the issuer obtained credit rating from at least one credit rating agency?", "OptionBool"),
  ("debenture_trustee", "Who are the debenture trustees appointed by the issuer in accordance with the Companies Act, 2013 and the Securities and Exchange Board of India (Debenture Trustees) Regulations, 1993?", "List Nat"),
  ("debenture_redemption_reserve", "Has the issuer created a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules made thereunder?", "OptionBool"),
  ("consent_for_conversion", "Has the issuer obtained positive consent from holders for the conversion of optionally convertible debt instruments into equity shares?", "Bool"),
  ("convertible_debt_value", "What is the total value (in rupees) of the convertible portion of any listed convertible debt instruments issued by an issuer?", "Nat"),
{ "promoter_contribution", "What percentage of the post-issue capital do promoters hold?", "Nat" },
  { "contribution_method", "How does the promoter contribute (equity shares or convertible securities)?", "OptionString" },
("promoter_contribution_undisclosed", "Have you disclosed the promoter contribution in the offer document?", "Bool"),
  ("promoter_contribution_computation_method", "How is the promoters' contribution computed?", "List (String × String)"),
  ("securities_ineligible", "Which securities are not eligible for minimum promoters’ contribution?", "List Nat"),
  ("employee_stock_options_or_SARs_exercise", "Have you made an assumption for exercising employee stock options or SARs?", "Bool"),
("specified_securities", "What are the specified securities?", "List Nat"),
  ("promoter_payments", "Were payments made for specified securities by promoters?", "Option List (Nat × Nat)"),
  ("companies_act_approvals", "Were specified securities acquired under Companies Act?", "Option List (Nat × Nat)"),
  ("government_ipos", "Was the initial public offer a government company IPO?", "Option List Nat"),
  ("promoter_transactions", "Did promoters acquire specified securities at a price less than issue price?", "Option List (Nat × Nat)"),
  ("securities_held_by_promoters", "What are the specified securities held by promoters?", "OptionList Nat"),
("lock_in_period", "What is the lock-in period in months?", "OptionNat"),
("locked_in_securities", "Enter the number of locked-in specified securities.", "List Nat"),
  ("sr_equity_shares", "Is this issue related to SR equity shares?", "Bool")
]

end GeneratedRules
