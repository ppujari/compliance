import Src.Core_auto
open Src.Core_auto
namespace Src.GeneratedRules_judged_v2

def generatedRuleset : List ComplianceRule := [
{ id := "ICDR_6_1_a"
  , title := "Net tangible assets ≥ ₹3 cr, not > 50% monetary assets"
  , reference := "Regulation 6(1)(a)"
  , check := fun _ => True
  , failReason := fun _ => "(rule ICDR_6_1_a: check stub — schema mismatch)"
  , remedy? := some "Adjust net tangible assets or monetary assets to meet the requirements." },
{ id := "ICDR_6_1_b"
  , title := "Operating profit ≥ ₹15 cr in each of last 3 years"
  , reference := "Regulation 6(1)(b)"
  , check := fun i => (i.operating_profits.length == 3) && i.operating_profits.all (fun x => x >= 150000000)
  , failReason := fun i => if (i.operating_profits.length != 3) then "Need 3 full-year operating profit figures." else let fails := (List.zip (List.range i.operating_profits.length) i.operating_profits).filter (fun p => p.snd < 150000000); let years := fails.map (fun p => s!"Year {p.fst + 1}"); "Operating profit below ₹15 cr in: " ++ String.intercalate ", " years
  , remedy? := some "Demonstrate ≥ ₹15 cr operating profit in each of the last 3 full financial years (restated, consolidated)." },
{ id := "ICDR_6_1_c"
  , title := "Net worth ≥ ₹1 cr in each of last 3 years"
  , reference := "Regulation 6(1)(c)"
  , check := fun i => (i.net_worth.length == 3) && i.net_worth.all (fun x => x >= 1000000)
  , failReason := fun i => if (i.net_worth.length != 3) then "Need 3 full-year net worth figures." else let fails := (List.zip (List.range i.net_worth.length) i.net_worth).filter (fun p => p.snd < 1000000); let years := fails.map (fun p => s!"Year {p.fst + 1}"); "Net worth below ₹1 cr in: " ++ String.intercalate ", " years
  , remedy? := some "Demonstrate ≥ ₹1 cr net worth in each of the last 3 full financial years (restated, consolidated)." },
{ id := "ICDR_7_1_b"
  , title := "Agreement with depository for dematerialisation"
  , reference := "Regulation 7(1)(b)"
  , check := fun i => i.agreement_with_depository
  , failReason := fun _ => "No agreement with a depository for dematerialisation found."
  , remedy? := none },
{ id := "rule_7_1_c"
  , title := "Promoter's specified securities in dematerialised form"
  , reference := "Regulation 7(1)(c)"
  , check := fun i => i.promoter_specified_securities_dematerialised
  , failReason := fun _ => "Specified securities held by promoters are not in dematerialised form."
  , remedy? := none },
{ id := "rule_7_1_d"
  , title := "Fully paid-up equity shares or forfeited"
  , reference := "Regulation 7(1)(d)"
  , check := fun _ => True
  , failReason := fun _ => "Existing partly paid-up equity shares are not fully paid-up or forfeited."
  , remedy? := none },
{ id := "rule_6_2"
  , title := "Amount for general corporate purposes limit"
  , reference := "Regulation 6(2)"
  , check := fun i => i.general_corporate_purposes <= (i.net_worth.sum * 25) / 100
  , failReason := fun _ => "The amount for general corporate purposes exceeds 25% of the total net worth."
  , remedy? := none },
{ id := "rule_6_3"
  , title := "Amount for other unidentified objects limit (without exceeding 25%)"
  , reference := "Regulation 6(3)"
  , check := fun _ => True
  , failReason := fun _ => "The amount for other unidentified objects exceeds 25% of the total net worth."
  , remedy? := none },
{ id := "rule_6_8"
  , title := "Maximum holding period for equity shares offered for sale"
  , reference := "ICDR_6_8"
  , check := fun i => i.holding_period >= 1
  , failReason := fun _ => "Equity shares offered for sale have been held for less than one year."
  , remedy? := none },
{ id := "ICDR_6_8_provided"
  , title := "Holding period exception for equity shares"
  , reference := "ICDR_6_8_provided"
  , check := fun _ => True
  , failReason := fun _ => "Equity shares received on conversion or exchange of compulsorily convertible securities not found."
  , remedy? := none },
{ id := "ICDR_6_8_provided_further"
  , title := "Holding period compliance at draft offer"
  , reference := "ICDR_6_8_provided_further"
  , check := fun i => i.holding_period_at_draft
  , failReason := fun _ => "Holding period of one year not complied with at the time of filing the draft offer document."
  , remedy? := none },
{ id := "ICDR_10_1a"
  , title := "Credit rating for CDI issuance"
  , reference := "Regulation 10(1)(a)"
  , check := fun i => i.credit_rating
  , failReason := fun _ => "No credit rating obtained from at least one credit rating agency."
  , remedy? := none },
{ id := "ICDR_9"
  , title := "Issuer may issue CDI without equity IPO"
  , reference := "Regulation 9"
  , check := fun i => i.eligible_for_cdi_without_equity_ipo
  , failReason := fun _ => "Issuer is in default of payment or repayment for more than six months."
  , remedy? := none },
{ id := "ICDR_10_4_debenture_trustee"
  , title := "Debenture trustee requirement for CDI"
  , reference := "Regulation 10(b)"
  , check := fun i => i.appointed_debenture_trustee
  , failReason := fun _ => "No debenture trustee appointed in accordance with the provisions of the Companies Act and SEBI regulations."
  , remedy? := none },
{ id := "ICDR_9_6"
  , title := "Default payment or repayment period"
  , reference := "Regulation 9"
  , check := fun _ => True
  , failReason := fun _ => "Has defaulted on payment or repayment of debt instruments for more than six months."
  , remedy? := none },
{ id := "ICDR_11_2"
  , title := "Option to not convert if conversion price is not determined"
  , reference := "Regulation 11(2)"
  , check := fun _ => True
  , failReason := fun _ => "Has convertible debt instruments with conversion price not determined."
  , remedy? := none },
{ id := "ICDR_13_a"
  , title := "Warrant tenure ≤ 18 months"
  , reference := "Regulation 13(a)"
  , check := fun _ => True
  , failReason := fun _ => "Has warrants with tenure exceeding 18 months."
  , remedy? := none },
{ id := "ICDR_13_c"
  , title := "Warrant exercise price formula and upfront payment"
  , reference := "Regulation 13(c)"
  , check := fun _ => True
  , failReason := fun _ => "Does not have warrant exercise price formula determined upfront or at least 25% of the consideration amount based on the exercise price not received upfront."
  , remedy? := none },
{ id := "ICDR_13_d"
  , title := "Warrant non-exercise forfeiture"
  , reference := "Regulation 13(d)"
  , check := fun _ => True
  , failReason := fun _ => "Has warrants with consideration not forfeited within three months of non-exercise."
  , remedy? := none },
{ id := "ICDR_6_4"
  , title := "Securities ineligible for minimum promoters’ contribution"
  , reference := "ICDR_6_4"
  , check := fun _ => True
  , failReason := fun _ => "Missing specified securities ineligible."
  , remedy? := none },
{ id := "ICDR_15_1_a"
  , title := "Specified securities ineligible for minimum promoters’ contribution"
  , reference := "ICDR_15_1_a"
  , check := fun _ => True
  , failReason := fun _ => "Incorrect specified securities ineligible."
  , remedy? := none },
{ id := "ICDR_15_1_a_i_i"
  , title := "Specified securities ineligible for minimum promoters’ contribution (I)(a)(i)"
  , reference := "ICDR_15_1_a_i_i"
  , check := fun _ => True
  , failReason := fun _ => "Missing specified securities acquired for consideration other than cash."
  , remedy? := none },
{ id := "ICDR_15_1_a_i_ii"
  , title := "Specified securities ineligible for minimum promoters’ contribution (I)(a)(ii)"
  , reference := "ICDR_15_1_a_i_ii"
  , check := fun i => i.conditions.any (fun c => c == 2)
  , failReason := fun _ => "Missing specified securities resulting from a bonus issue."
  , remedy? := none },
{ id := "ICDR_16_1"
  , title := "Lock-in of specified securities held by the promoters"
  , reference := "ICDR_16_1"
  , check := fun _ => True
  , failReason := fun _ => "Missing lock-in period for specified securities."
  , remedy? := none },
{ id := "rule_16_49a"
  , title := "Lock-in period for promoter contribution"
  , reference := "ICDR_16_49a"
  , check := fun i => i.securities_held_by_promoters.all (fun s => s >= 18 * 30)
  , failReason := fun _ => "Promoter contribution not locked in for at least 18 months."
  , remedy? := some "Lock-in promoter contribution for a period of 18 months from the date of allotment." },
{ id := "rule_16_49b"
  , title := "Lock-in period for promoter excess holding"
  , reference := "ICDR_16_49b"
  , check := fun _ => True
  , failReason := fun _ => "Promoter excess holding not locked in for at least 6 months."
  , remedy? := some "Lock-in promoter excess holding for a period of 6 months from the date of allotment." },
{ id := "rule_17"
  , title := "Lock-in of pre-issue capital held by non-promoters"
  , reference := "ICDR_17"
  , check := fun i => i.lock_in_period == 6 * 30
  , failReason := fun _ => "Pre-issue capital held by non-promoters not locked in for 6 months."
  , remedy? := some "Lock-in pre-issue capital held by non-promoters for a period of 6 months from the date of allotment." },
{ id := "rule_17_a"
  , title := "Exceptions to lock-in for non-promoters"
  , reference := "ICDR_17_a"
  , check := fun _ => True
  , failReason := fun _ => "No exceptions specified for equity shares allotted to employees or held by employee stock option trusts."
  , remedy? := some "Specify exceptions for equity shares allotted to employees or held by employee stock option trusts." },
{ id := "rule_17_c"
  , title := "Lock-in for equity shares held by venture capital funds or alternative investment funds"
  , reference := "ICDR_17_c"
  , check := fun _ => True
  , failReason := fun _ => "No lock-in period specified for equity shares held by venture capital funds or alternative investment funds."
  , remedy? := some "Specify a lock-in period of at least 6 months from the date of purchase for equity shares held by venture capital funds or alternative investment funds." },
{ id := "ICDR_21_1a"
  , title := "Lock-in for specified securities (a)"
  , reference := "Regulation 21"
  , check := fun i => i.conditions.any (fun c => c == 1) && i.securities.any (fun s => s == 68) && i.lead_manager_appointment
  , failReason := fun _ => "Specified securities not locked-in according to clause (a) of regulation 16 or not held by promoters."
  , remedy? := none },
{ id := "ICDR_21_1b"
  , title := "Lock-in for specified securities (b)"
  , reference := "Regulation 21"
  , check := fun i => i.conditions.any (fun c => c == 2) && i.securities.any (fun s => s == 68)
  , failReason := fun _ => "Specified securities not locked-in according to clause (b) of regulation 16 or not held by promoters."
  , remedy? := none },
{ id := "ICDR_21"
  , title := "Pledge of locked-in specified securities"
  , reference := "ICDR_21"
  , check := fun i => i.securities.any (fun s => s == 68) && !(i.specified_securities_ineligible)
  , failReason := fun _ => "Specified securities not held by promoters or ineligible."
  , remedy? := none },
{ id := "ICDR_21_a"
  , title := "Pledge conditions (a)"
  , reference := "ICDR_21_a"
  , check := fun i => i.conditions.any (fun c => c == 1) && i.lead_manager_appointment
  , failReason := fun _ => "Loan not granted to the issuer company or its subsidiary(ies) for financing one or more of the objects of the issue."
  , remedy? := none },
{ id := "ICDR_21_b"
  , title := "Pledge conditions (b)"
  , reference := "ICDR_21_b"
  , check := fun i => i.conditions.any (fun c => c == 2)
  , failReason := fun _ => "Loan not granted with pledge of specified securities as a term."
  , remedy? := none },
{ id := "ICDR_23"
  , title := "Appointment of lead manager(s)"
  , reference := "ICDR_23"
  , check := fun i => i.lead_manager_appointment
  , failReason := fun _ => "Lead Manager(s) not appointed."
  , remedy? := none }
]

end Src.GeneratedRules_judged_v2
