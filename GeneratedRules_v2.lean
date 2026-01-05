import Src.Core
open Core

namespace GeneratedRules_v2

def generatedRuleset : List ComplianceRule := [
{ id := "ICDR_4_core",
    title := "Conditions on reference date",
    reference := "Regulation 4",
    check := fun _ => True,
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure all conditions are satisfied as of the filing dates." },

  { id := "ICDR_5_1_a",
    title := "Disqualification: issuer/promoters/directors/sellers debarred",
    reference := "Regulation 5(1)(a)",
    check := fun i => !i.is_debarred,
    failReason := fun _ => "Issuer, promoters, directors or selling shareholders are debarred.",
    remedy? := some "Ensure no party is debarred." },

  { id := "ICDR_5_1_b",
    title := "Disqualification: promoter/director of another debarred company",
    reference := "Regulation 5(1)(b)",
    check := fun i => !i.has_debarred_directors,
    failReason := fun _ => "Promoters or directors are associated with a debarred company.",
    remedy? := some "Ensure no association with debarred companies." },

  { id := "ICDR_5_1_c",
    title := "Disqualification: wilful defaulter or fraudulent borrower",
    reference := "Regulation 5(1)(c)",
    check := fun i => !i.is_fraudulent,
    failReason := fun _ => "Issuer, promoters or directors are fraudulent borrowers.",
    remedy? := some "Ensure no fraudulence." },

  { id := "ICDR_5_1_d",
    title := "Disqualification: fugitive economic offender",
    reference := "Regulation 5(1)(d)",
    check := fun i => !i.is_fugitive,
    failReason := fun _ => "Promoters or directors are fugitive economic offenders.",
    remedy? := some "Ensure no association with fugitives." },

  { id := "ICDR_5_2_a",
    title := "Outstanding options for employees (ESOP)",
    reference := "Regulation 5(2)(a)",
    check := fun i => !i.has_esop_exemption,
    failReason := fun _ => "Issuer has outstanding ESOPs.",
    remedy? := some "Ensure no outstanding ESOPs." },

  { id := "ICDR_5_2_b",
    title := "Outstanding stock appreciation rights (SAR)",
    reference := "Regulation 5(2)(b)",
    check := fun i => !i.has_sar_exemption,
    failReason := fun _ => "Issuer has outstanding SARs.",
    remedy? := some "Ensure no outstanding SARs." },

  { id := "ICDR_5_2_c",
    title := "Fully paid-up convertible securities",
    reference := "Regulation 5(2)(c)",
    check := fun i => !i.has_mandatory_convertibles,
    failReason := fun _ => "Issuer has outstanding mandatory convertibles.",
    remedy? := some "Ensure no outstanding mandatory convertibles." },

  { id := "ICDR_5_2_core",
    title := "No outstanding convertibles/rights (pre-IPO)",
    reference := "Regulation 5(2)",
    check := fun i => !i.has_outstanding_convertibles,
    failReason := fun _ => "Issuer has outstanding convertible securities or rights.",
    remedy? := some "Ensure no outstanding convertibles or rights." },

  { id := "ICDR_6_1_a",
    title := "Net tangible assets ≥ ₹3 cr in each of last 3 years",
    reference := "Regulation 6(1)(a)",
    check := fun i =>
      let ntaOK := (lengthIs i.net_tangible_assets 3) && allGeNat i.net_tangible_assets 30000000
      let moneyOK := (i.monetary_asset_ratio ≤ 50) || i.used_monetary_assets || i.is_offer_for_sale_only
      ntaOK && moneyOK,
    failReason := fun i =>
      let ntaMsg :=
        if !(lengthIs i.net_tangible_assets 3) then "Need 3 full-year NTA figures."
        else if !(allGeNat i.net_tangible_assets 30000000) then "Each year’s net tangible assets must be ≥ ₹3.0 crore."
        else ""
      let moneyMsg :=
        if i.is_offer_for_sale_only then ""
        else if i.monetary_asset_ratio > 50 && !i.used_monetary_assets then "Monetary assets exceed 50% of NTA without evidence of committed/actual use."
        else ""
      String.intercalate " " ([ntaMsg, moneyMsg].filter (· ≠ "")),
    remedy? := some "Demonstrate firm commitments/use of monetary assets, or restructure to OSF-only; ensure each NTA year ≥ ₹3 cr." },

  { id := "ICDR_6_1_b",
    title := "Operating profit ≥ ₹15 cr in each of last 3 years",
    reference := "Regulation 6(1)(b)",
    check := fun i => (lengthIs i.operating_profits 3) && allGeNat i.operating_profits 150000000,
    failReason := fun i =>
      if !(lengthIs i.operating_profits 3) then "Need 3 full-year operating profit figures."
      else
        let fails := i.operating_profits.zipIdx |>.filter (fun (x, idx) => x < 150000000)
        let years := fails.map (fun (_, idx) => s!"Year {idx + 1}")
        "Operating profit below ₹15 cr in: " ++ String.intercalate ", " years,
    remedy? := some "Demonstrate ≥ ₹15 cr operating profit in each of the last 3 full financial years (restated, consolidated)." },

  { id := "ICDR_6_1_c",
    title := "Net worth ≥ ₹1 cr in each of last 3 years",
    reference := "Regulation 6(1)(c)",
    check := fun i => (lengthIs i.net_worths 3) && allGeNat i.net_worths 10000000,
    failReason := fun i =>
      if !(lengthIs i.net_worths 3) then "Need 3 full-year net worth figures."
      else
        let fails := i.net_worths.zipIdx |>.filter (fun (x, idx) => x < 10000000)
        let years := fails.map (fun (_, idx) => s!"Year {idx + 1}")
        "Net worth below ₹1 cr in: " ++ String.intercalate ", " years,
    remedy? := some "Increase equity/retained earnings to meet ≥ ₹1 cr in each of the last 3 full years." },

  { id := "ICDR_6_1_d",
    title := "Revenue from new name activity ≥ 50% in last year",
    reference := "Regulation 6(1)(d)",
    check := fun i => (!i.changed_name_recently) || (i.percent_revenue_from_new_name ≥ 50),
    failReason := fun i =>
      if i.changed_name_recently && i.percent_revenue_from_new_name < 50 then
        "Changed name within 1 year but <50% revenue from new-name activity in the preceding full year."
      else "Condition not met.",
    remedy? := some "Demonstrate ≥50% revenue from the activity indicated by the new name or defer filing." },

  { id := "ICDR_6_2_core",
    title := "Eligibility for IPO through book-building process",
    reference := "Regulation 6(2)",
    check := fun i => i.uses_book_building && (i.general_corp_purpose_ratio ≤ 75) && i.qib_allocation_done,
    failReason := fun _ => "Issuer does not meet the eligibility criteria for IPO through book-building process.",
    remedy? := some "Ensure at least 75% allocation to QIBs and complete QIB allocations." },

  { id := "ICDR_6_3_i",
    title := "General corporate purposes limit ≤ 35%",
    reference := "Regulation 6(3)",
    check := fun i => (i.general_corp_purpose_ratio ≤ 35),
    failReason := fun _ => "Amount for general corporate purposes exceeds 35%.",
    remedy? := some "Ensure the amount for general corporate purposes does not exceed 35%." },

  { id := "ICDR_6_3_ii",
    title := "Unidentified acquisition/investment limit ≤ 25%",
    reference := "Regulation 6(3)",
    check := fun i => (i.general_corp_purpose_ratio ≤ 25),
    failReason := fun _ => "Amount for unidentified acquisitions or investments exceeds 25%.",
    remedy? := some "Ensure the amount for unidentified acquisitions or investments does not exceed 25%." },

  { id := "ICDR_6_3_iii",
    title := "SR shares issued to promoters/founders with executive positions",
    reference := "Regulation 6(3)(iii)",
    check := fun i => !i.sr_holder_exec,
    failReason := fun _ => "SR shares were not issued only to promoters/founders who hold an executive position.",
    remedy? := some "Ensure SR shares are issued only to promoters/founders with executive positions." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("is_debarred", "Is the issuer debarred from accessing the capital market?", "Bool"),
  ("has_debarred_directors", "Are any of the directors associated with a debarred company?", "Bool"),
  ("is_fraudulent", "Is the issuer or its promoters/directors fraudulent borrowers?", "Bool"),
  ("is_fugitive", "Are any of the promoters or directors fugitive economic offenders?", "Bool"),
  ("has_esop_exemption", "Does the issuer have outstanding ESOPs?", "Bool"),
  ("has_sar_exemption", "Does the issuer have outstanding SARs?", "Bool"),
  ("has_mandatory_convertibles", "Does the issuer have outstanding mandatory convertibles?", "Bool"),
  ("has_outstanding_convertibles", "Are there any outstanding convertible securities or rights?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (₹ paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (₹ paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (₹ paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new-name activity?", "Nat"),
  ("uses_book_building", "Does the issuer use book-building process for IPO?", "Bool"),
  ("qib_allocation_done", "Has at least 75% allocation to QIBs been completed?", "Bool"),
  ("general_corp_purpose_ratio", "What % of funds are allocated for general corporate purposes?", "Nat"),
  ("sr_holder_exec", "Are SR shares issued only to promoters/founders with executive positions?", "Bool"),

{ id := "ICDR_6_3_iv",
    title := "Authorization of SR equity shares by special resolution",
    reference := "Regulation 6(3)(iv)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure compliance with the authorization requirements.",
    remedy? := some "Ensure that a special resolution was passed at a general meeting of shareholders, and the notice for such meeting specifically provided details on SR equity shares." },

  { id := "ICDR_6_3_ix",
    title := "SR equity shares equivalent to ordinary shares except for voting rights",
    reference := "Regulation 6(3)(ix)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure SR equity shares are equivalent to ordinary shares in all respects, except for superior voting rights.",
    remedy? := some "Ensure that SR equity shares have the same rights as ordinary shares except for superior voting rights." },

  { id := "ICDR_6_3_v",
    title := "SR equity shares issued prior to filing draft red herring prospectus",
    reference := "Regulation 6(3)(v)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure SR equity shares were issued and held for at least three months before the filing of the red herring prospectus.",
    remedy? := some "Ensure that SR equity shares are issued prior to the draft red herring prospectus and held for a minimum period of three months." },

  { id := "ICDR_6_3_vi",
    title := "Voting rights ratio for SR equity shares",
    reference := "Regulation 6(3)(vi)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure the voting rights ratio of SR equity shares is between 2:1 and 10:1 compared to ordinary shares.",
    remedy? := some "Ensure that the voting rights ratio for SR equity shares is within the specified range." },

  { id := "ICDR_7_1_a",
    title := "Application for in-principle approval to stock exchanges",
    reference := "Regulation 7(1)(a)",
    check := fun i => i.applied_to_stock_exchange,
    failReason := fun _ => "Issuer has not applied for an in-principle approval from a stock exchange.",
    remedy? := some "Apply for an in-principle approval to at least one stock exchange." },

  { id := "ICDR_7_1_b",
    title := "Agreement with depository for dematerialisation",
    reference := "Regulation 7(1)(b)",
    check := fun i => i.has_demat_agreement,
    failReason := fun _ => "Issuer has not entered into an agreement with a depository.",
    remedy? := some "Enter into an agreement with a depository for dematerialisation of specified securities." },

  { id := "ICDR_7_1_c",
    title := "Promoters' securities in dematerialised form",
    reference := "Regulation 7(1)(c)",
    check := fun i => i.promoter_securities_demat,
    failReason := fun _ => "Issuer's promoters' securities are not in dematerialised form.",
    remedy? := some "Ensure that all specified securities held by the promoters are in dematerialised form." },

  { id := "ICDR_7_1_d",
    title := "Partly paid-up equity shares fully paid-up or forfeited",
    reference := "Regulation 7(1)(d)",
    check := fun i => i.no_partly_paid_shares,
    failReason := fun _ => "Issuer has partly paid-up equity shares that are not fully paid-up or forfeited.",
    remedy? := some "Ensure all existing partly paid-up equity shares have been fully paid-up or forfeited." },

  { id := "ICDR_7_1_e",
    title := "Firm arrangements for finance towards project funding",
    reference := "Regulation 7(1)(e)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure firm financial arrangements are in place.",
    remedy? := some "Ensure that firm arrangements of finance through verifiable means cover at least seventy-five percent of the stated means for project funding." },

  { id := "ICDR_7_2_core",
    title := "Amount for general corporate purposes ≤ 25%",
    reference := "Regulation 7(2)",
    check := fun i => i.general_corp_purpose_ratio ≤ 25,
    failReason := fun _ => "The amount allocated to general corporate purposes exceeds twenty-five percent.",
    remedy? := some "Ensure that the amount for general corporate purposes does not exceed twenty-five percent of the total issue proceeds." },

  { id := "ICDR_8_core",
    title := "Holding period for equity shares offered for sale",
    reference := "Regulation 8",
    check := fun i => i.shares_held_duration_months ≥ 12,
    failReason := fun _ => "Equity shares held by sellers are not at least one year old.",
    remedy? := some "Ensure that the equity shares being offered for sale have been held for a minimum of one year." },

  { id := "ICDR_8_provided",
    title := "Holding period for converted securities",
    reference := "Regulation 8",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure the combined holding period is at least one year.",
    remedy? := some "Ensure that the combined holding period of convertible securities and resultant equity shares is at least one year." },

  { id := "ICDR_10_1_b",
    title := "Debenture trustee requirement for convertible debt instruments",
    reference := "Regulation 10(1)(b)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure at least one debenture trustee is appointed.",
    remedy? := some "Appoint at least one debenture trustee in accordance with the Companies Act, 2013 and SEBI regulations." },

  { id := "ICDR_10_1_c",
    title := "Debenture redemption reserve requirement for convertible debt instruments",
    reference := "Regulation 10(1)(c)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure a debenture redemption reserve is created.",
    remedy? := some "Create a debenture redemption reserve in accordance with the Companies Act, 2013 and rules made thereunder." },

  { id := "ICDR_10_1_d",
    title := "Security on assets for convertible debt instruments",
    reference := "Regulation 10(1)(d)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure security on assets is in place.",
    remedy? := some "Ensure that any charge or security on assets in respect of secured convertible debt instruments complies with the regulations." },

  { id := "ICDR_11_1",
    title := "Positive consent for conversion of optionally convertible debt instruments",
    reference := "Regulation 11(1)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure positive consent from holders.",
    remedy? := some "Ensure that the issuer does not convert optionally convertible debt instruments without positive consent from the holders." },

  { id := "ICDR_11_2",
    title := "Option to holders for conversion of listed convertible debt instruments",
    reference := "Regulation 11(2)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure options are given to holders.",
    remedy? := some "Ensure that holders of listed convertible debt instruments exceeding ten crore rupees in value have the option not to convert into equity shares." },

  { id := "ICDR_11_3",
    title := "Redemption within one month for non-exercised conversion option",
    reference := "Regulation 11(3)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure redemption is within one month.",
    remedy? := some "Ensure that the issuer redeems convertible debt instruments not exercised by holders within one month at a price not less than face value." },

  { id := "ICDR_11_4",
    title := "Redemption as per disclosures in offer document",
    reference := "Regulation 11(4)",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure redemption is as disclosed.",
    remedy? := some "Ensure that any redemption complies with the disclosures made in the offer document." },

  { id := "ICDR_12_core",
    title := "Restriction on issuing convertible debt instruments for financing or loans to promoter group",
    reference := "Regulation 12",
    check := fun i => True,
    failReason := fun _ => "Manual review required to ensure no issuance for financing or loans to the promoter group.",
    remedy? := some "Ensure that convertible debt instruments are not issued for financing or providing loans to any person in the promoter group unless conversion is within eighteen months." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("applied_to_stock_exchange", "Has an application been made to a stock exchange for in-principle approval?", "Bool"),
  ("has_demat_agreement", "Is there an agreement with a depository for dematerialisation of specified securities?", "Bool"),
  ("promoter_securities_demat", "Are all promoter securities held in dematerialised form?", "Bool"),
  ("no_partly_paid_shares", "Have all partly paid-up equity shares been fully paid-up or forfeited?", "Bool"),
  ("general_corp_purpose_ratio", "What percentage of the issue proceeds is allocated to general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How long have the equity shares being offered for sale been held by sellers (in months)?", "Nat"),

{ id := "ICDR_13_a",
    title := "Warrant tenure ≤ 18 months",
    reference := "Regulation 13",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate warrant tenure.",
    remedy? := some "Ensure the warrant tenure does not exceed eighteen months from the date of their allotment." },

  { id := "ICDR_13_c",
    title := "Exercise price upfront and 25% consideration received",
    reference := "Regulation 13",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate exercise price or upfront consideration.",
    remedy? := some "Ensure the exercise price of warrants is determined upfront and disclosed in the offer document with at least 25% of the consideration received upfront." },

  { id := "ICDR_13_core",
    title := "Issue of warrants in initial public offer",
    reference := "Regulation 13",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate the core conditions for issuing warrants.",
    remedy? := some "Ensure all conditions specified under Regulation 13 are met." },

  { id := "ICDR_13_d",
    title := "Forfeiture of consideration if not exercised within 3 months",
    reference := "Regulation 13",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate forfeiture conditions.",
    remedy? := some "Ensure the warrant holder forfeits consideration if not exercised within three months from payment." },

  { id := "ICDR_13_1_core",
    title := "Promoters' contribution ≥ 20% post-issue capital",
    reference := "Regulation 14(1)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate promoters' contribution.",
    remedy? := some "Ensure the promoters hold at least twenty per cent. of the post-issue capital." },

  { id := "ICDR_14_1_c",
    title := "Specified securities ineligible for minimum promoters’ contribution",
    reference := "Regulation 14(1)(c)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate specified securities eligibility.",
    remedy? := some "Ensure the specified securities are eligible for minimum promoters' contribution." },

  { id := "ICDR_14_2_a",
    title := "Promoters' contribution by equity shares or convertible securities",
    reference := "Regulation 14(2)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate promoters' contribution method.",
    remedy? := some "Ensure the promoters contribute twenty per cent. either by equity shares or convertible securities." },

  { id := "ICDR_14_2_b",
    title := "Price of equity shares not lower than weighted average price",
    reference := "Regulation 14(2)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate equity share pricing.",
    remedy? := some "Ensure the price of equity shares is not lower than the weighted average price." },

  { id := "ICDR_14_2_c",
    title := "Promoters' contribution for convertible debt instruments",
    reference := "Regulation 14(2)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate promoters' contribution for convertible debt.",
    remedy? := some "Ensure the promoters contribute at least twenty per cent. of the project cost in equity shares." },

  { id := "ICDR_14_2_core",
    title := "Eligibility of specified securities for promoters’ contribution under clauses (a) and (c)",
    reference := "Regulation 14(2)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate eligibility of specified securities.",
    remedy? := some "Ensure the specified securities are eligible for promoters' contribution." },

  { id := "ICDR_14_3_core",
    title := "Promoters' contribution requirements satisfied one day prior to issue opening",
    reference := "Regulation 14(3)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate promoters' contribution timing.",
    remedy? := some "Ensure the promoters satisfy the requirements at least one day prior to issue opening." },

  { id := "ICDR_14_4_core",
    title := "Promoters' contribution escrow account and release conditions",
    reference := "Regulation 14(4)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate promoters' contribution escrow.",
    remedy? := some "Ensure the promoters' contribution is kept in an escrow account and released as per conditions." },

  { id := "ICDR_15_1_a",
    title := "Specified securities ineligible for minimum promoters’ contribution (a)",
    reference := "Regulation 15(1)(a)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate specified securities eligibility.",
    remedy? := some "Ensure the specified securities are eligible for minimum promoters' contribution." },

  { id := "ICDR_15_1_b",
    title := "Specified securities ineligible for minimum promoters’ contribution (b)",
    reference := "Regulation 15(1)(b)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate specified securities eligibility.",
    remedy? := some "Ensure the specified securities are eligible for minimum promoters' contribution." },

  { id := "ICDR_16_1_a",
    title := "Lock-in period for minimum promoters’ contribution",
    reference := "Regulation 16(1)(a)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate lock-in period.",
    remedy? := some "Ensure the minimum promoters' contribution is locked-in for eighteen months or three years as per conditions." },

  { id := "ICDR_16_1_b",
    title := "Lock-in period for excess promoters’ holding",
    reference := "Regulation 16(1)(b)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate lock-in period.",
    remedy? := some "Ensure the excess promoters' holdings are locked-in for six months or one year as per conditions." },

  { id := "ICDR_16_2_core",
    title := "Lock-in for SR equity shares",
    reference := "Regulation 16(2)",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate lock-in period.",
    remedy? := some "Ensure the SR equity shares are locked-in until conversion or for eighteen months/three years." },

  { id := "ICDR_17_a",
    title := "Exemption for employee stock options/schemes",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate exemption conditions.",
    remedy? := some "Ensure the equity shares allotted under employee schemes are exempted as per regulations." },

  { id := "ICDR_17_b",
    title := "Exemption for employee stock option trust",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate exemption conditions.",
    remedy? := some "Ensure the equity shares held by an employee stock option trust are exempted as per regulations." },

  { id := "ICDR_17_c",
    title := "Exemption for venture capital funds/alternative investment funds",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder since no relevant field is available
    failReason := fun _ => "No specific issuer field to validate exemption conditions.",
    remedy? := some "Ensure the equity shares held by venture capital funds or alternative investment funds are exempted as per regulations." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  -- Placeholder since no relevant fields are available,

{ id := "ICDR_17_core",
    title := "Pre-issue capital lock-in for non-promoters",
    reference := "Regulation 17",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure pre-issue capital held by persons other than promoters is locked in for six months from the date of allotment." },

  { id := "ICDR_18_core",
    title := "Lock-in provisions for specified securities lent to stabilising agent under green shoe option",
    reference := "Regulation 18",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in provisions do not apply during the period specified securities are lent for green shoe option." },

  { id := "ICDR_19_core",
    title := "Lock-in for partly paid-up specified securities",
    reference := "Regulation 19",
    check := fun i => !i.no_partly_paid_shares || i.shares_fully_paid,
    failReason := fun i =>
      if !i.no_partly_paid_shares && !i.shares_fully_paid then
        "Partly paid-up specified securities are not fully paid."
      else "Condition not met.",
    remedy? := some "Ensure partly paid-up specified securities become pari passu with the specified securities issued to the public." },

  { id := "ICDR_20_core",
    title := "Inscription or recording of non-transferability for locked-in specified securities",
    reference := "Regulation 20",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure certificates contain 'non-transferable' inscription and lock-in period is recorded." },

  { id := "ICDR_21_a",
    title := "Pledge conditions for clause (a) of regulation 16",
    reference := "Regulation 21(a)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure loan is granted for financing objects of the issue and pledge is a term of sanction." },

  { id := "ICDR_21_b",
    title := "Pledge conditions for clause (b) of regulation 16",
    reference := "Regulation 21(b)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure pledge is a term of sanction." },

  { id := "ICDR_21_core",
    title := "Pledge of locked-in specified securities by promoters",
    reference := "Regulation 21",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure pledge conditions are met and lock-in continues post-invocation." },

  { id := "ICDR_22_core",
    title := "Transferability of locked-in specified securities",
    reference := "Regulation 22",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure transfer conditions are met and lock-in continues for transferee." },

  { id := "ICDR_23_1",
    title := "Appointment of lead managers",
    reference := "Regulation 23(1)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure one or more registered merchant bankers are appointed as lead manager(s)." },

  { id := "ICDR_23_2",
    title := "Rights, obligations and responsibilities of lead managers",
    reference := "Regulation 23(2)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure rights, obligations, and responsibilities are predetermined and disclosed." },

  { id := "ICDR_23_3",
    title := "Non-associate lead manager requirement",
    reference := "Regulation 23(3)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure at least one non-associated lead manager is appointed." },

  { id := "ICDR_23_4",
    title := "Appointment of other intermediaries",
    reference := "Regulation 23(4)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure other intermediaries are appointed after capability assessment." },

  { id := "ICDR_23_5",
    title := "Agreements with Intermediaries",
    reference := "Regulation 23(5)",
    check := fun i => True, -- No specific field to map directly
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure agreements are in specified format and do not diminish liabilities/obligations." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("no_partly_paid_shares", "Are there any partly paid-up shares?", "Bool"),
  ("shares_fully_paid", "Are the specified securities fully paid up?", "Bool")
]

def issuerQuestions : List (String × String × String) := [
("is_debarred", "Is the issuer debarred from accessing the capital market?", "Bool"),
  ("has_debarred_directors", "Are any of the directors associated with a debarred company?", "Bool"),
  ("is_fraudulent", "Is the issuer or its promoters/directors fraudulent borrowers?", "Bool"),
  ("is_fugitive", "Are any of the promoters or directors fugitive economic offenders?", "Bool"),
  ("has_esop_exemption", "Does the issuer have outstanding ESOPs?", "Bool"),
  ("has_sar_exemption", "Does the issuer have outstanding SARs?", "Bool"),
  ("has_mandatory_convertibles", "Does the issuer have outstanding mandatory convertibles?", "Bool"),
  ("has_outstanding_convertibles", "Are there any outstanding convertible securities or rights?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (₹ paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (₹ paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (₹ paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new-name activity?", "Nat"),
  ("uses_book_building", "Does the issuer use book-building process for IPO?", "Bool"),
  ("qib_allocation_done", "Has at least 75% allocation to QIBs been completed?", "Bool"),
  ("general_corp_purpose_ratio", "What % of funds are allocated for general corporate purposes?", "Nat"),
  ("sr_holder_exec", "Are SR shares issued only to promoters/founders with executive positions?", "Bool"),
("applied_to_stock_exchange", "Has an application been made to a stock exchange for in-principle approval?", "Bool"),
  ("has_demat_agreement", "Is there an agreement with a depository for dematerialisation of specified securities?", "Bool"),
  ("promoter_securities_demat", "Are all promoter securities held in dematerialised form?", "Bool"),
  ("no_partly_paid_shares", "Have all partly paid-up equity shares been fully paid-up or forfeited?", "Bool"),
  ("general_corp_purpose_ratio", "What percentage of the issue proceeds is allocated to general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How long have the equity shares being offered for sale been held by sellers (in months)?", "Nat"),
-- Placeholder since no relevant fields are available,
("no_partly_paid_shares", "Are there any partly paid-up shares?", "Bool"),
  ("shares_fully_paid", "Are the specified securities fully paid up?", "Bool")
]

end GeneratedRules_v2
