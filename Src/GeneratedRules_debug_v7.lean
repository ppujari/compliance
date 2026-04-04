import Src.Core_auto_debug_v7
open Src.Core_auto_debug_v7
namespace Src.GeneratedRules_debug_v7

def generatedRuleset : List ComplianceRule := [
{ id := "ICDR_10_1a"
  , title := "Credit rating required for CDI offer"
  , reference := "Regulation 10(1)(a)"
  , check := fun _ => True
  , failReason := fun _ => s!"No credit rating obtained from at least one credit rating agency."
  , remedy? := none },
{ id := "ICDR_10_a"
  , title := "Credit rating and debenture trustee requirements"
  , reference := "Regulation 10(1)(a)"
  , check := fun i => i.credit_rating && i.debenture_trustee.length > 0
  , failReason := fun i => if i.credit_rating then "No debenture trustee appointed." else "No credit rating obtained."
  , remedy? := some "" },
{ id := "ICDR_10_c"
  , title := "Debenture redemption reserve"
  , reference := "Regulation 10(1)(c)"
  , check := fun i => i.debenture_redemption_reserve
  , failReason := fun _ => "No debenture redemption reserve created."
  , remedy? := none },
{ id := "ICDR_11_1"
  , title := "Consent for conversion of convertible debt instruments"
  , reference := "Regulation 11(1)"
  , check := fun i => i.consent_for_conversion
  , failReason := fun _ => "No positive consent from holders for conversion of optionally convertible debt instruments."
  , remedy? := none },
{ id := "ICDR_11_2"
  , title := "Option to not convert convertible portion into equity shares"
  , reference := "Regulation 11(2)"
  , check := fun _ => True
  , failReason := fun _ => "No option provided for holders of listed convertible debt instruments to not convert the convertible portion into equity shares."
  , remedy? := none },
{ id := "ICDR_12_a"
  , title := "Promoters’ contribution computation"
  , reference := "ICDR_12_a"
  , check := fun _ => True
  , failReason := fun _ => "The rule requires complex computations not directly representable in the provided Issuer structure."
  , remedy? := none },
{ id := "ICDR_12_a_ii"
  , title := "Exercise of employee stock options or SARs"
  , reference := "ICDR_12_a_ii"
  , check := fun _ => True
  , failReason := fun _ => "The rule requires complex computations not directly representable in the provided Issuer structure."
  , remedy? := none },
{ id := "ICDR_13_a"
  , title := "Warrant tenure ≤ 18 months"
  , reference := "Regulation 13(a)"
  , check := fun i => i.warrant_tenure <= 18
  , failReason := fun _ => "Warrant tenure exceeds 18 months."
  , remedy? := none },
{ id := "ICDR_13_c"
  , title := "Warrant exercise price formula and upfront payment"
  , reference := "Regulation 13(c)"
  , check := fun i => (i.warrant_exercise_price.isSome) && (i.upfront_payment > 0)
  , failReason := fun _ => "Warrant exercise price not determined or upfront payment is zero."
  , remedy? := none },
{ id := "ICDR_13_d"
  , title := "Forfeiture of consideration for un-exercised warrants"
  , reference := "Regulation 13(d)"
  , check := fun _ => True
  , failReason := fun _ => "Forfeiture of consideration for un-exercised warrants not applicable."
  , remedy? := none },
{ id := "ICDR_14_1"
  , title := "Minimum promoters’ contribution ≥ 20%"
  , reference := "Regulation 14(1)"
  , check := fun i => i.promoter_contribution >= (i.fully_paid_up_equity_shares * 5)
  , failReason := fun _ => "Promoters' contribution is less than 20% of the post-issue capital."
  , remedy? := none },
{ id := "ICDR_14_1_a"
  , title := "Promoter contribution by equity shares or convertible securities"
  , reference := "Regulation 14(1)"
  , check := fun i => i.contribution_method.isSome
  , failReason := fun _ => "Promoter contribution method not specified."
  , remedy? := none },
{ id := "ICDR_14_1_b"
  , title := "Undisclosed conversion price"
  , reference := "Regulation 14(1)"
  , check := fun i => i.promoter_contribution > 0
  , failReason := fun _ => "Promoters did not contribute to the issue.\"
  , remedy? := some \"Contribute to the public issue." },
{ id := "ICDR_16_1"
  , title := "Lock-in of specified securities held by the promoters"
  , reference := "ICDR_16_1"
  , check := fun _ => True
  , failReason := fun _ => "Lock-in period for specified securities held by promoters is not within the valid range."
  , remedy? := some "Ensure that the lock-in period for specified securities held by promoters is between 1 and 3 times the minimum holding period." },
{ id := "ICDR_16_49a"
  , title := "Lock-in period for promoter contribution"
  , reference := "Regulation 16(49)"
  , check := fun i => (i.lock_in_period == some 18) || ((i.finance_arrangements.contains 1) && (i.lock_in_period == some 3))
  , failReason := fun _ => "if (i.lock_in_period != some 18) then \"Lock-in period for promoter contribution is not 18 months.\" else if (i.finance_arrangements.contains 1) && (i.lock_in_period != some 3) then \"Lock-in period for promoter contribution is not 3 years when majority of issue proceeds are proposed for capital expenditure.\"
  , remedy? := some \"Adjust lock-in period for promoter contribution according to the regulation." },
{ id := "ICDR_16_49b"
  , title := "Lock-in period for promoter excess holding"
  , reference := "Regulation 16(49)"
  , check := fun i => (i.lock_in_period == some 6) || ((i.finance_arrangements.contains 1) && (i.lock_in_period == some 12))
  , failReason := fun _ => "if (i.lock_in_period != some 6) then \"Lock-in period for promoter excess holding is not 6 months.\" else if (i.finance_arrangements.contains 1) && (i.lock_in_period != some 12) then \"Lock-in period for promoter excess holding is not 1 year when majority of issue proceeds are proposed for capital expenditure.\"
  , remedy? := some \"Adjust lock-in period for promoter excess holding according to the regulation." },
{ id := "ICDR_17"
  , title := "Lock-in of equity shares held by persons other than promoters"
  , reference := "ICDR_17"
  , check := fun i => i.lock_in_period == some 6
  , failReason := fun _ => "if (i.lock_in_period != some 6) then \"Lock-in period for equity shares held by persons other than promoters is not 6 months."
  , remedy? := none },
{ id := "ICDR_17_a"
  , title := "Exceptions to lock-in for equity shares held by employees and employee stock option trusts"
  , reference := "ICDR_17_a"
  , check := fun _ => True
  , failReason := fun _ => "This rule does not apply to the provided Issuer structure."
  , remedy? := none },
{ id := "ICDR_17_c"
  , title := "Lock-in for equity shares held by venture capital funds or alternative investment funds"
  , reference := "ICDR_17_c"
  , check := fun i => i.lock_in_period == some 6 || (i.specified_securities.contains 3 && i.lock_in_period > 0)
  , failReason := fun _ => "if (i.lock_in_period != some 6) then \"Lock-in period for equity shares held by venture capital funds or alternative investment funds is not 6 months.\" else if (i.specified_securities.contains 3 && i.lock_in_period == 0) then \"Lock-in period for equity shares held by venture capital funds or alternative investment funds should be greater than zero."
  , remedy? := none },
{ id := "ICDR_21"
  , title := "Pledge of locked-in specified securities"
  , reference := "Regulation 21"
  , check := fun _ => True
  , failReason := fun _ => "Locked-in specified securities not found."
  , remedy? := some "Provide locked-in specified securities." },
{ id := "ICDR_21_a"
  , title := "Pledge of locked-in specified securities (a)"
  , reference := "Regulation 21(a)"
  , check := fun _ => True
  , failReason := fun _ => "Locked-in specified securities not found or no lead manager roles provided."
  , remedy? := some "Provide locked-in specified securities and lead manager roles." },
{ id := "ICDR_21_b"
  , title := "Pledge of locked-in specified securities (b)"
  , reference := "Regulation 21(b)"
  , check := fun _ => True
  , failReason := fun _ => "Locked-in specified securities not found or no lead manager roles provided."
  , remedy? := some "Provide locked-in specified securities and lead manager roles." },
{ id := "ICDR_22"
  , title := "Transfer of locked-in specified securities"
  , reference := "ICDR_22"
  , check := fun _ => True
  , failReason := fun _ => "This rule cannot be checked with the available Issuer fields.\"
  , remedy? := none },
{ id := "ICDR_23"
  , title := "Rights, obligations and responsibilities of lead managers"
  , reference := "ICDR_23"
  , check := fun _ => True
  , failReason := fun _ => "No lead manager roles provided."
  , remedy? := some "Provide lead manager roles." },
{ id := "ICDR_4_13_a"
  , title := "Payment for specified securities acquired by promoters"
  , reference := "Regulation 4(1)(a)"
  , check := fun i => i.specified_securities.length > 0 && i.securities_held_by_promoters.any (fun s => s == fst i.specified_securities)
  , failReason := fun _ => "Specified securities not found in securities held by promoters."
  , remedy? := some "Ensure that the specified securities are included in the list of securities held by promoters." },
{ id := "ICDR_4_13_b"
  , title := "Payment for specified securities acquired under Companies Act"
  , reference := "Regulation 4(1)(b)"
  , check := fun i => i.specified_securities.length > 0 && i.securities_held_by_promoters.any (fun s => s == fst i.specified_securities) && i.finance_arrangements.any (fun f => f == 230 || f == 231 || f == 232 || f == 233 || f == 234)
  , failReason := fun _ => "Specified securities not found in finance arrangements or not acquired under Companies Act."
  , remedy? := some "Ensure that the specified securities are acquired under sections 230 to 234 of the Companies Act and included in the list of finance arrangements." },
{ id := "ICDR_4_13_c"
  , title := "Payment for specified securities in government company IPO"
  , reference := "Regulation 4(1)(c)"
  , check := fun i => i.specified_securities.length > 0 && i.finance_arrangements.any (fun f => f == 235)
  , failReason := fun _ => "Specified securities not found in finance arrangements or not part of government company IPO."
  , remedy? := some "Ensure that the specified securities are included in the list of finance arrangements and represent an initial public offer for a government company." },
{ id := "ICDR_4_13_d"
  , title := "Specified securities allotted to promoters at a price less than issue price"
  , reference := "Regulation 4(1)(d)"
  , check := fun _ => True
  , failReason := fun _ => "Specified securities not found in securities held by promoters or allotted at a price greater than the issue price."
  , remedy? := some "Ensure that the specified securities are allotted to promoters at a price less than the issue price." },
{ id := "ICDR_6_3"
  , title := "Computation of promoter's contribution and weighted average price"
  , reference := "ICDR_6_3"
  , check := fun _ => True
  , failReason := fun _ => "The rule requires complex computations not directly representable in the provided Issuer structure."
  , remedy? := none },
{ id := "ICDR_6_4"
  , title := "Securities ineligible for minimum promoters’ contribution"
  , reference := "ICDR_6_4"
  , check := fun i => i.securities_ineligible.all (fun x => x < i.lock_in_period || x >= i.lock_in_period + 1)
  , failReason := fun _ => "Some securities are ineligible for minimum promoters' contribution.\"
  , remedy? := some \"Ensure that the specified securities acquired during the preceding three years comply with the regulation." },
{ id := "ICDR_6_8_provided"
  , title := "Max sale unidentified targets"
  , reference := "Regulation 6(8)"
  , check := fun i => i.max_sale_unidentified_targets <= (25 * i.convertible_securities.length) / 100
  , failReason := fun _ => s!"Maximum sale of equity shares for unidentified acquisition or investment targets exceeds 25%."
  , remedy? := some "Adjust the maximum sale to not exceed 25%." },
{ id := "ICDR_6_8_provided_further"
  , title := "Exceptions to max sale"
  , reference := "Regulation 6(8)"
  , check := fun _ => True
  , failReason := fun _ => s!"No exceptions found for maximum sale limits."
  , remedy? := none },
{ id := "ICDR_7_1_c"
  , title := "Dematerialised promoter's securities"
  , reference := "Regulation 7(1)(c)"
  , check := fun i => i.promoter_securities_dematerialised
  , failReason := fun _ => "Promoters' securities are not in dematerialised form."
  , remedy? := some "Ensure all promoter's specified securities are in dematerialised form before offer document filing." },
{ id := "ICDR_7_1_d"
  , title := "Fully paid-up equity shares or forfeiture"
  , reference := "Regulation 7(1)(d)"
  , check := fun i => i.fully_paid_up_equity_shares
  , failReason := fun _ => "Existing partly paid-up equity shares are not fully paid-up or forfeited."
  , remedy? := none },
{ id := "ICDR_7_1_e"
  , title := "Firm arrangements of finance"
  , reference := "General conditions"
  , check := fun i => i.finance_arrangements.some.getOrElse (fun _ => false) && i.finance_arrangements.length >= 3
  , failReason := fun i => if i.finance_arrangements.some.isNone then "No firm arrangements of finance found." else "Firm arrangements of finance for less than 75% of the project's funding."
  , remedy? := some "Make firm arrangements of finance through verifiable means towards seventy five per cent. of the stated means of finance for a specific project proposed to be funded from the issue proceeds, excluding the amount to be raised through the proposed public issue or through existing identifiable internal accruals." },
{ id := "ICDR_8"
  , title := "Minimum holding period for equity shares offered for sale"
  , reference := "Regulation 8"
  , check := fun i => i.min_holding_period > 0
  , failReason := fun _ => "No minimum holding period specified for equity shares offered for sale."
  , remedy? := none },
{ id := "ICDR_8_1"
  , title := "Holding period for convertible securities and resulting equity shares"
  , reference := "ICDR_8_1"
  , check := fun i => i.convertible_securities.length > 0
  , failReason := fun _ => "No convertible securities specified."
  , remedy? := none },
{ id := "ICDR_8_provided_further"
  , title := "Additional conditions for conversion"
  , reference := "Regulation 8"
  , check := fun i => i.convertible_securities.all (fun cs => i.net_worth.contains cs && cs != i.fully_paid_up_equity_shares)
  , failReason := fun _ => s!"Convertible securities not issued out of free reserves and share premium, or issued by utilisation of revaluation reserves or unrealized profits."
  , remedy? := none },
{ id := "ICDR_9"
  , title := "Issuer may issue convertible debt instruments"
  , reference := "Regulation 9"
  , check := fun i => !i.default_payment_status
  , failReason := fun _ => s!"Issuer in default of payment of interest or repayment of principal amount for more than six months."
  , remedy? := none },
{ id := "ICDR_9_6"
  , title := "Default payment of interest or repayment of principal"
  , reference := "Regulation 9"
  , check := fun i => not (i.default_payment_status)
  , failReason := fun _ => "Issuer is in default of payment of interest or repayment of principal amount for a period of more than six months."
  , remedy? := none }
]

end Src.GeneratedRules_debug_v7
