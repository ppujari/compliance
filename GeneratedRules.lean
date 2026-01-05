import Main
open Main
namespace GeneratedRules

def generatedRuleset : List ComplianceRule := [
{ id := "ICDR_5_2_a",
    title := "Exception: outstanding options granted to employees",
    reference := "Entities not eligible to make an initial public offer",
    check := fun i => !i.has_outstanding_convertibles || i.has_esop_exemption,
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.has_esop_exemption then
        "Outstanding options granted to employees must be in compliance with the Companies Act, 2013."
      else "Condition not met.",
    remedy? := some "Ensure outstanding options are compliant or exempt under the Companies Act." },

  { id := "ICDR_5_2_b",
    title := "Exception: outstanding stock appreciation rights (SAR)",
    reference := "Entities not eligible to make an initial public offer",
    check := fun i => !i.has_outstanding_convertibles || i.has_sar_exemption,
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.has_sar_exemption then
        "Outstanding SAR must be fully exercised for equity shares prior to filing."
      else "Condition not met.",
    remedy? := some "Ensure outstanding SAR are compliant or exempt under the Companies Act." },

  { id := "ICDR_5_2_c",
    title := "Exception: fully paid-up outstanding convertible securities",
    reference := "Entities not eligible to make an initial public offer",
    check := fun i => !i.has_outstanding_convertibles || i.has_mandatory_convertibles,
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.has_mandatory_convertibles then
        "Convertible securities must be fully paid-up and required to convert prior to filing."
      else "Condition not met.",
    remedy? := some "Ensure convertible securities are compliant or exempt under the Companies Act." },

  { id := "ICDR_6_1_a_Provided",
    title := "Monetary asset utilization requirement",
    reference := "Eligibility requirements for an initial public offer",
    check := fun i => !(i.monetary_asset_ratio > 50) || i.used_monetary_assets,
    failReason := fun i =>
      if i.monetary_asset_ratio > 50 && !i.used_monetary_assets then
        "Monetary assets exceed 50% of NTA without evidence of committed/actual use."
      else "Condition not met.",
    remedy? := some "Utilize or commit excess monetary assets in business/project." },

  { id := "ICDR_6_1_a_Provided_further",
    title := "Monetary asset limit exception for offer for sale",
    reference := "Eligibility requirements for an initial public offer",
    check := fun i => !i.is_offer_for_sale_only || (i.monetary_asset_ratio ≤ 50),
    failReason := fun i =>
      if i.is_offer_for_sale_only && i.monetary_asset_ratio > 50 then
        "Monetary asset limit of 50% not applicable for offer for sale."
      else "Condition not met.",
    remedy? := some "Ensure monetary assets are within limits or restructure to OSF-only." },

  { id := "ICDR_5_3_i",
    title := "Technology-intensive requirement for SR equity shares",
    reference := "(3)",
    check := fun i => i.is_tech_firm,
    failReason := fun i =>
      if !i.is_tech_firm then
        "Issuer must be intensive in the use of technology, information technology, intellectual property, data analytics, bio-technology or nano-technology."
      else "Condition not met.",
    remedy? := some "Demonstrate intensive use of specified technologies." },

  { id := "ICDR_5_3_ii",
    title := "Net worth requirement for SR shareholder",
    reference := "(3)",
    check := fun i => i.sr_net_worth ≤ 1000000000,
    failReason := fun i =>
      if i.sr_net_worth > 1000000000 then
        "Net worth of SR shareholder must not exceed ₹1,000 crore."
      else "Condition not met.",
    remedy? := some "Ensure net worth is within limits or re-evaluate valuation." },

  { id := "ICDR_5_3_iii",
    title := "SR shares issuance to promoters/founders",
    reference := "(3)",
    check := fun i => i.sr_holder_exec,
    failReason := fun i =>
      if !i.sr_holder_exec then
        "SR shares must be issued only to promoters/founders who hold an executive position."
      else "Condition not met.",
    remedy? := some "Ensure SR shares are issued only to eligible promoters/founders." },

  { id := "ICDR_5_3_iv_a",
    title := "Authorization of SR equity shares issuance",
    reference := "(3)",
    check := fun i => True, -- Placeholder for specific authorization details
    failReason := fun _ =>
      "Special resolution authorizing the issue must be provided.",
    remedy? := some "Ensure special resolution with required details is available." },

  { id := "ICDR_5_3_iv_b",
    title := "Sunset provisions for SR equity shares",
    reference := "(3)",
    check := fun i => True, -- Placeholder for specific sunset provisions
    failReason := fun _ =>
      "Sunset provisions must be provided.",
    remedy? := some "Ensure sunset provisions with required details are available." },

  { id := "ICDR_5_3_v",
    title := "Holding period requirement for SR equity shares",
    reference := "(3)",
    check := fun i => i.shares_held_duration_months ≥ 3,
    failReason := fun i =>
      if i.shares_held_duration_months < 3 then
        "SR shares must be held for at least three months prior to filing."
      else "Condition not met.",
    remedy? := some "Ensure SR shares are held for the required period." },

  { id := "ICDR_5_3_vi",
    title := "Voting rights ratio for SR equity shares",
    reference := "(3)",
    check := fun i => (i.sr_voting_ratio ≥ 2) && (i.sr_voting_ratio ≤ 10),
    failReason := fun i =>
      if !(i.sr_voting_ratio ≥ 2) || !(i.sr_voting_ratio ≤ 10) then
        "Voting rights ratio must be between 2:1 and 10:1."
      else "Condition not met.",
    remedy? := some "Ensure voting rights ratio is within the specified range." },

  { id := "ICDR_5_3_vii",
    title := "Face value requirement for SR equity shares",
    reference := "(3)",
    check := fun i => i.sr_same_face_value,
    failReason := fun i =>
      if !i.sr_same_face_value then
        "SR equity shares must have the same face value as ordinary shares."
      else "Condition not met.",
    remedy? := some "Ensure SR shares have the same face value as ordinary shares." },

  { id := "ICDR_5_3_viii",
    title := "Single class of SR equity shares requirement",
    reference := "(3)",
    check := fun i => i.sr_class_count == 1,
    failReason := fun i =>
      if i.sr_class_count != 1 then
        "Issuer must only have one class of SR equity shares."
      else "Condition not met.",
    remedy? := some "Ensure only one class of SR equity shares is issued." },

  { id := "ICDR_5_3_ix",
    title := "Equivalence to ordinary shares for SR equity shares",
    reference := "(3)",
    check := fun i => True, -- Placeholder for specific equivalence details
    failReason := fun _ =>
      "SR equity shares must be equivalent to ordinary shares except for voting rights.",
    remedy? := some "Ensure SR shares are equivalent to ordinary shares in all respects." },

  { id := "ICDR_7_1_a",
    title := "Application for in-principle approval to list specified securities",
    reference := "Regulation 7(1)(a)",
    check := fun i => i.applied_to_stock_exchange,
    failReason := fun i =>
      if !i.applied_to_stock_exchange then
        "Issuer must have applied to stock exchanges for listing."
      else "Condition not met.",
    remedy? := some "Ensure application is made and in-principle approval is sought." },

  { id := "ICDR_7_1_b",
    title := "Agreement with depository for dematerialisation",
    reference := "Regulation 7(1)(b)",
    check := fun i => i.has_demat_agreement,
    failReason := fun i =>
      if !i.has_demat_agreement then
        "Issuer must have an agreement with a depository."
      else "Condition not met.",
    remedy? := some "Ensure agreement is in place for dematerialisation." },

  { id := "ICDR_7_1_c",
    title := "Promoters' securities in dematerialised form",
    reference := "Regulation 7(1)(c)",
    check := fun i => i.promoter_securities_demat,
    failReason := fun i =>
      if !i.promoter_securities_demat then
        "Promoter securities must be in dematerialized form."
      else "Condition not met.",
    remedy? := some "Ensure promoter securities are dematerialized." },

  { id := "ICDR_7_1_d",
    title := "Partly paid-up equity shares fully paid-up or forfeited",
    reference := "Regulation 7(1)(d)",
    check := fun i => !i.no_partly_paid_shares,
    failReason := fun i =>
      if i.no_partly_paid_shares then
        "All partly paid-up equity shares must be fully paid-up or forfeited."
      else "Condition not met.",
    remedy? := some "Ensure all partly paid-up shares are either fully paid-up or forfeited." },

  { id := "ICDR_7_1_e",
    title := "Firm arrangements for project finance",
    reference := "Regulation 7(1)(e)",
    check := fun i => i.finance_75_percent_done,
    failReason := fun i =>
      if !i.finance_75_percent_done then
        "Issuer must have firm arrangements for at least 75% of project finance."
      else "Condition not met.",
    remedy? := some "Ensure firm financial arrangements are in place." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("has_outstanding_convertibles", "Are there any outstanding convertible securities?", "Bool"),
  ("has_esop_exemption", "Is the company exempt under employee stock option schemes?", "Bool"),
  ("has_sar_exemption", "Is the company exempt under stock appreciation rights schemes?", "Bool"),
  ("has_mandatory_convertibles", "Have all convertible securities been converted as required?", "Bool"),
  ("monetary_asset_ratio", "What percentage of net tangible assets are held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been utilized or committed for business/project?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("is_tech_firm", "Is the issuer intensive in technology, information technology, intellectual property, data analytics, bio-technology or nano-technology?", "Bool"),
  ("sr_net_worth", "What is the net worth of the SR shareholder as determined by a Registered Valuer (₹ paise)?", "Nat"),
  ("sr_holder_exec", "Are SR shares issued only to promoters/founders who hold an executive position?", "Bool"),
  ("sr_voting_ratio", "What is the voting rights ratio for SR equity shares compared to ordinary shares?", "Nat"),
  ("sr_same_face_value", "Do SR equity shares have the same face value as ordinary shares?", "Bool"),
  ("sr_class_count", "How many classes of SR equity shares does the issuer have?", "Nat"),
  ("shares_held_duration_months", "For how long have the SR shares been held (in months)?", "Nat"),
  ("applied_to_stock_exchange", "Has the issuer applied to stock exchanges for listing?", "Bool"),
  ("has_demat_agreement", "Does the issuer have an agreement with a depository for dematerialization?", "Bool"),
  ("promoter_securities_demat", "Are all promoter securities in dematerialized form?", "Bool"),
  ("no_partly_paid_shares", "Do any partly paid-up equity shares exist?", "Bool"),
  ("finance_75_percent_done", "Has the issuer made firm arrangements for at least 75% of project finance?", "Bool"),

{ id := "ICDR_7_2",
    title := "General corporate purposes limit ≤ 25%",
    reference := "Regulation 7(2)",
    check := fun i => i.general_corp_purpose_ratio ≤ 25,
    failReason := fun i =>
      if i.general_corp_purpose_ratio > 25 then
        s!"Amount for general corporate purposes exceeds 25%: {i.general_corp_purpose_ratio}%."
      else "Condition not met.",
    remedy? := some "Reduce the amount allocated to general corporate purposes to ≤ 25% of the total funds raised." },

  { id := "ICDR_6_2",
    title := "General corporate purposes limit (25%)",
    reference := "Regulation 6(2)",
    check := fun i => i.general_corp_purpose_ratio ≤ 25,
    failReason := fun i =>
      if i.general_corp_purpose_ratio > 25 then
        s!"Amount for general corporate purposes exceeds 25%: {i.general_corp_purpose_ratio}%."
      else "Condition not met.",
    remedy? := some "Reduce the amount allocated to general corporate purposes to ≤ 25% of the total funds raised." },

  { id := "ICDR_7_I",
    title := "\"project\" definition",
    reference := "Explanation (I)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Project definition not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_II_a",
    title := "Track record of operating profit (partnership)",
    reference := "Explanation (II)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Track record of operating profit for partnership not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_II_b_i",
    title := "Financial statements certification (i)",
    reference := "Explanation (II)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Certification of financial statements not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_II_b_ii",
    title := "Financial statements certification (ii)",
    reference := "Explanation (II)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Certification of financial statements not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_II_b_iii",
    title := "Financial statements certification (iii)",
    reference := "Explanation (II)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Certification of financial statements not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_III",
    title := "Track record of distributable profits (division)",
    reference := "Explanation (III)",
    check := fun _ => true,
    failReason := fun i =>
      s!"Track record of distributable profits for division not applicable: {i}",
    remedy? := none },

  { id := "ICDR_7_3_provided",
    title := "Limit for unidentified acquisition/investment (25%)",
    reference := "Regulation 7(3)",
    check := fun i => i.general_corp_purpose_ratio ≤ 25,
    failReason := fun i =>
      if i.general_corp_purpose_ratio > 25 then
        s!"Amount for unidentified acquisition/investment exceeds 25%: {i.general_corp_purpose_ratio}%."
      else "Condition not met.",
    remedy? := some "Reduce the amount allocated to unidentified acquisitions or investments to ≤ 25% of the total funds raised." },

  { id := "ICDR_8_core",
    title := "Holding period of equity shares (1 year)",
    reference := "Regulation 8",
    check := fun i => i.shares_held_duration_months ≥ 12,
    failReason := fun i =>
      if i.shares_held_duration_months < 12 then
        s!"Equity shares held for less than one year: {i.shares_held_duration_months} months."
      else "Condition not met.",
    remedy? := some "Ensure equity shares are held for at least one year prior to filing the draft offer document." },

  { id := "ICDR_8_provided",
    title := "Holding period for convertible securities (1 year)",
    reference := "Regulation 8",
    check := fun i => i.shares_held_duration_months ≥ 12,
    failReason := fun i =>
      if i.shares_held_duration_months < 12 then
        s!"Convertible securities held for less than one year: {i.shares_held_duration_months} months."
      else "Condition not met.",
    remedy? := some "Ensure convertible securities are held for at least one year prior to filing the draft offer document." },

  { id := "ICDR_8_provided_further_a",
    title := "Exemption for government companies/statutory authorities/corporation in infrastructure sector",
    reference := "Additional conditions for an offer for sale",
    check := fun i => i.is_govt_entity,
    failReason := fun i =>
      if !i.is_govt_entity then
        s!"Issuer is not a government company or statutory authority: {i}."
      else "Condition not met.",
    remedy? := some "Ensure the issuer is a government company, statutory authority, or corporation in the infrastructure sector." },

  { id := "ICDR_8_provided_further_b",
    title := "Exemption for equity shares acquired pursuant to High Court/tribunal/Central Government scheme",
    reference := "Additional conditions for an offer for sale",
    check := fun i => i.via_merger_scheme,
    failReason := fun i =>
      if !i.via_merger_scheme then
        s!"Equity shares not acquired pursuant to a High Court/tribunal/Central Government scheme: {i}."
      else "Condition not met.",
    remedy? := some "Ensure equity shares were acquired pursuant to a scheme approved by a High Court, tribunal, or Central Government." },

  { id := "ICDR_8_provided_further_c",
    title := "Exemption for bonus issue of equity shares",
    reference := "Additional conditions for an offer for sale",
    check := fun i => i.is_bonus_from_free_reserve && !i.bonus_not_from_revaluation,
    failReason := fun i =>
      if !(i.is_bonus_from_free_reserve && !i.bonus_not_from_revaluation) then
        s!"Bonus issue not from free reserves or includes revaluation reserves: {i}."
      else "Condition not met.",
    remedy? := some "Ensure bonus shares are issued out of free reserves and share premium, without using revaluation reserves." },

  { id := "ICDR_8A_a",
    title := "Limit on shares offered for sale by major shareholders under Regulation 6(2)",
    reference := "Additional conditions for an offer for sale for issues under sub-regulation (2) of regulation 6",
    check := fun i => true, -- Placeholder as specific fields are not available
    failReason := fun i =>
      s!"Major shareholder shares offered exceed 50%: {i}.",
    remedy? := some "Ensure major shareholders offer no more than 50% of their pre-issue shareholding." },

  { id := "ICDR_8A_b",
    title := "Limit on shares offered for sale by minor shareholders under Regulation 6(2)",
    reference := "Additional conditions for an offer for sale for issues under sub-regulation (2) of regulation 6",
    check := fun i => true, -- Placeholder as specific fields are not available
    failReason := fun i =>
      s!"Minor shareholder shares offered exceed 10%: {i}.",
    remedy? := some "Ensure minor shareholders offer no more than 10% of the issuer's pre-issue shareholding." },

  { id := "ICDR_8A_c",
    title := "Lock-in provisions for major shareholders under Regulation 6(2)",
    reference := "Additional conditions for an offer for sale for issues under sub-regulation (2) of regulation 6",
    check := fun i => true, -- Placeholder as specific fields are not available
    failReason := fun i =>
      s!"Lock-in provisions not applicable: {i}.",
    remedy? := some "Ensure major shareholders comply with lock-in provisions." },

  { id := "ICDR_6_2_a",
    title := "Offer for sale of government company/statutory authority infrastructure sector",
    reference := "Regulation 6(2)",
    check := fun i => i.is_govt_entity,
    failReason := fun i =>
      if !i.is_govt_entity then
        s!"Issuer is not a government entity or statutory authority: {i}."
      else "Condition not met.",
    remedy? := some "Ensure the issuer is a government company, statutory authority, or corporation in the infrastructure sector." },

  { id := "ICDR_6_2_b",
    title := "Equity shares acquired pursuant to High Court/tribunal/Central Government scheme",
    reference := "Regulation 6(2)",
    check := fun i => i.via_merger_scheme,
    failReason := fun i =>
      if !i.via_merger_scheme then
        s!"Shares not acquired via approved scheme: {i}."
      else "Condition not met.",
    remedy? := some "Ensure shares were acquired pursuant to a High Court, tribunal, or Central Government-approved scheme." },

  { id := "ICDR_6_2_c",
    title := "Equity shares issued under bonus issue on securities held for at least one year",
    reference := "Regulation 6(2)",
    check := fun i => i.is_bonus_from_free_reserve && !i.bonus_not_from_revaluation,
    failReason := fun i =>
      if !(i.is_bonus_from_free_reserve && !i.bonus_not_from_revaluation) then
        s!"Bonus issue not from free reserves or includes revaluation reserves: {i}."
      else "Condition not met.",
    remedy? := some "Ensure bonus shares are issued out of free reserves and share premium, without using revaluation reserves." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("general_corp_purpose_ratio", "What % of funds raised is allocated to general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How long have the shares been held by the seller(s)? (in months)", "Nat"),
  ("is_govt_entity", "Is the issuer a government company or statutory authority?", "Bool"),
  ("via_merger_scheme", "Were the equity shares acquired pursuant to a High Court/tribunal/Central Government scheme?", "Bool"),
  ("is_bonus_from_free_reserve", "Are bonus shares issued from free reserves and share premium?", "Bool"),
  ("bonus_not_from_revaluation", "Are bonus shares not issued by utilizing revaluation reserves or unrealized profits?", "Bool"),

{ id := "ICDR_36_Explanation",
    title := "Limits for shares offered for sale calculated with reference to shareholding on filing date",
    reference := "Explanation under Regulation 8A",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure the limits are calculated with reference to shareholding on filing date and apply cumulatively." },

  { id := "ICDR_9",
    title := "Eligibility for issue of convertible debt instruments",
    reference := "Regulation 9",
    check := fun i => !i.is_debarred && !i.has_debarred_directors && !i.is_fraudulent && !i.is_fugitive,
    failReason := fun i =>
      if i.is_debarred then "Issuer is debarred."
      else if i.has_debarred_directors then "Issuer has debarred directors."
      else if i.is_fraudulent then "Issuer is fraudulent."
      else if i.is_fugitive then "Issuer is a fugitive."
      else "",
    remedy? := some "Ensure the issuer is not debarred, does not have debarred directors, and is not fraudulent or a fugitive." },

  { id := "ICDR_10_a",
    title := "Credit rating requirement for convertible debt instruments",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Obtain credit rating from at least one credit rating agency." },

  { id := "ICDR_10_b",
    title := "Debenture trustee requirement for convertible debt instruments",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Appoint at least one debenture trustee in accordance with the provisions of the Companies Act, 2013 and the Securities and Exchange Board of India (Debenture Trustees) Regulations, 1993." },

  { id := "ICDR_10_c",
    title := "Debenture redemption reserve requirement for convertible debt instruments",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Create a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules made thereunder." },

  { id := "ICDR_10_d_i",
    title := "Sufficient assets for principal amount discharge",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the assets are sufficient to discharge the principal amount at all times." },

  { id := "ICDR_10_d_ii",
    title := "Assets free from encumbrance for convertible debt instruments",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the assets are free from any encumbrance." },

  { id := "ICDR_10_d_iii",
    title := "Consent for existing security or leasehold land",
    reference := "Regulation 10(1)",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Obtain consent of the lender or security trustee or lessor for creating a charge on leasehold land." },

  { id := "ICDR_10_1_a",
    title := "Credit rating requirement for convertible debt issue",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Obtain credit rating from at least one credit rating agency." },

  { id := "ICDR_10_1_b",
    title := "Debenture trustee requirement for convertible debt issue",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Appoint at least one debenture trustee in accordance with the provisions of the Companies Act, 2013 and the Securities and Exchange Board of India (Debenture Trustees) Regulations, 1993." },

  { id := "ICDR_10_1_c",
    title := "Debenture redemption reserve requirement for convertible debt issue",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Create a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules made thereunder." },

  { id := "ICDR_10_1_d_i",
    title := "Sufficient assets for principal discharge (secured convertible debt)",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the assets are sufficient to discharge the principal amount at all times." },

  { id := "ICDR_10_1_d_ii",
    title := "Free from encumbrance (secured convertible debt)",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the assets are free from any encumbrance." },

  { id := "ICDR_10_1_d_iii",
    title := "Consent for second or pari passu charge (secured convertible debt)",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Obtain consent from the lender or security trustee for a second or pari passu charge." },

  { id := "ICDR_10_1_d_iv",
    title := "Security or asset cover for second charge (secured convertible debt)",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the security or asset cover is arrived at after reduction of liabilities having a first or prior charge." },

  { id := "ICDR_10_2",
    title := "Redemption of convertible debt instruments",
    reference := "Additional requirements for issue of convertible debt instruments",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure the issuer redeems the convertible debt instruments in terms of the offer document." },

  { id := "ICDR_11_1",
    title := "Positive consent required for conversion of optionally convertible debt instruments",
    reference := "Conversion of optionally convertible debt instruments into equity shares",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the holders of such convertible debt instruments have sent their positive consent for conversion." },

  { id := "ICDR_11_2",
    title := "Option to holders for conversion of listed convertible debt instruments",
    reference := "Conversion of optionally convertible debt instruments into equity shares",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the holders are given an option not to convert the convertible portion into equity shares." },

  { id := "ICDR_11_3",
    title := "Redemption within one month for non-exercised conversion option",
    reference := "Conversion of optionally convertible debt instruments into equity shares",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the issuer redeems the non-exercised portion within one month at a price not less than its face value." },

  { id := "ICDR_11_4",
    title := "Redemption as per disclosures in offer document",
    reference := "Conversion of optionally convertible debt instruments into equity shares",
    check := fun _ => True, -- Placeholder as no specific Issuer field is provided
    failReason := fun _ => "Insufficient data to determine compliance.",
    remedy? := some "Ensure that the redemption is as per the disclosures made in the offer document." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("is_debarred", "Is the issuer debarred?", "Bool"),
  ("has_debarred_directors", "Does the issuer have debarred directors?", "Bool"),
  ("is_fraudulent", "Is the issuer fraudulent?", "Bool"),
  ("is_fugitive", "Is the issuer a fugitive?", "Bool"),

{ id := "ICDR_12",
    title := "Restriction on issuing convertible debt for financing promoter group or group companies",
    reference := "Issue of convertible debt instruments for financing",
    check := fun i => !(i.has_outstanding_convertibles && i.is_debarred),
    failReason := fun i =>
      if i.has_outstanding_convertibles && i.is_debarred then
        "Issuer cannot issue convertible debt for financing promoter group or group companies."
      else "",
    remedy? := some "Ensure no outstanding convertibles and issuer is not debarred." },

  { id := "ICDR_11_2_provided",
    title := "Exception to option for conversion with upper limit on price",
    reference := "Conversion of optionally convertible debt instruments into equity shares",
    check := fun i => !(i.has_outstanding_convertibles && !i.conversion_price_disclosure_required),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.conversion_price_disclosure_required then
        "Issuer must disclose the upper limit on price of convertible debt instruments."
      else "",
    remedy? := some "Disclose the upper limit on price of convertible debt instruments." },

  { id := "ICDR_12_provided",
    title := "Exception to restriction on issuing fully convertible debt instruments for financing or loans",
    reference := "Issue of convertible debt instruments for financing",
    check := fun i => !(i.has_outstanding_convertibles && !i.full_conversion_within_eighteen_months),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.full_conversion_within_eighteen_months then
        "Issuer must ensure full conversion within eighteen months."
      else "",
    remedy? := some "Ensure full conversion of debt instruments within eighteen months." },

  { id := "ICDR_13_a",
    title := "Tenure of warrants in initial public offer",
    reference := "Issue of warrants",
    check := fun i => !(i.has_outstanding_convertibles && !i.warrant_tenure_not_exceed_eighteen_months),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.warrant_tenure_not_exceed_eighteen_months then
        "Warrants tenure exceeds eighteen months."
      else "",
    remedy? := some "Ensure warrants tenure does not exceed eighteen months." },

  { id := "ICDR_13_b",
    title := "Attachment of one or more warrants to specified security",
    reference := "Issue of warrants",
    check := fun i => !(i.has_outstanding_convertibles && !i.multiple_warrants_per_security),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.multiple_warrants_per_security then
        "Issuer must attach one or more warrants to specified security."
      else "",
    remedy? := some "Attach one or more warrants to the specified security." },

  { id := "ICDR_13_c",
    title := "Determination and disclosure of exercise price for warrants",
    reference := "Issue of warrants",
    check := fun i => !(i.has_outstanding_convertibles && !i.upfront_disclosure_of_exercise_price),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.upfront_disclosure_of_exercise_price then
        "Issuer must disclose the exercise price upfront."
      else "",
    remedy? := some "Disclose the exercise price of warrants upfront." },

  { id := "ICDR_13_c_provided",
    title := "Consideration based on cap price in case of formula-based exercise price",
    reference := "Issue of warrants",
    check := fun i => !(i.has_outstanding_convertibles && !i.cap_price_disclosure_required),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.cap_price_disclosure_required then
        "Issuer must disclose the cap price based on formula."
      else "",
    remedy? := some "Disclose the cap price of warrants based on formula." },

  { id := "ICDR_13_d",
    title := "Forfeiture of consideration for unexercised warrants",
    reference := "Issue of warrants",
    check := fun i => !(i.has_outstanding_convertibles && !i.forfeiture_of_unexercised_warrants),
    failReason := fun i =>
      if i.has_outstanding_convertibles && !i.forfeiture_of_unexercised_warrants then
        "Issuer must forfeit consideration for unexercised warrants."
      else "",
    remedy? := some "Forfeit the consideration made in respect of unexercised warrants." },

  { id := "ICDR_14_1",
    title := "Minimum promoters’ contribution requirement",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.promoters_shareholding < 20),
    failReason := fun i =>
      if i.promoters_shareholding < 20 then
        "Promoters must hold at least twenty per cent. of the post-issue capital."
      else "",
    remedy? := some "Ensure promoters hold at least twenty per cent. of the post-issue capital." },

  { id := "ICDR_14_1_provided",
    title := "Alternative contributors to meet shortfall in minimum contribution",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.promoters_shareholding < 20 && !i.alternative_contributors_to_meet_shortfall),
    failReason := fun i =>
      if i.promoters_shareholding < 20 && !i.alternative_contributors_to_meet_shortfall then
        "Alternative contributors must meet the shortfall in minimum contribution."
      else "",
    remedy? := some "Ensure alternative contributors meet the shortfall in minimum contribution." },

  { id := "ICDR_14_1_provided_further",
    title := "Exception to minimum promoters’ contribution requirement",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.promoters_shareholding < 20 && !i.no_identifiable_promoter_exception),
    failReason := fun i =>
      if i.promoters_shareholding < 20 && !i.no_identifiable_promoter_exception then
        "Issuer must not have any identifiable promoter."
      else "",
    remedy? := some "Ensure issuer does not have an identifiable promoter." },

  { id := "ICDR_14_1_core",
    title := "Minimum Promoters' Contribution",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.promoters_shareholding < 20 && !i.alternative_contributions),
    failReason := fun i =>
      if i.promoters_shareholding < 20 && !i.alternative_contributions then
        "Promoters must hold at least twenty per cent. of the post-issue capital or alternative contributions."
      else "",
    remedy? := some "Ensure promoters hold at least twenty per cent. of the post-issue capital or alternative contributions." },

  { id := "ICDR_14_2_a",
    title := "Promoters' Contribution by Equity or Convertible Securities",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.promoter_contribution_method != "equity" && i.promoter_contribution_method != "convertibles"),
    failReason := fun i =>
      if i.promoter_contribution_method != "equity" && i.promoter_contribution_method != "convertibles" then
        "Promoters must contribute by equity or convertibles."
      else "",
    remedy? := some "Ensure promoters contribute either by equity shares or convertible securities." },

  { id := "ICDR_14_2_b",
    title := "Price of Convertible Securities",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.convertible_securities_price < i.weighted_average_price),
    failReason := fun i =>
      if i.convertible_securities_price < i.weighted_average_price then
        "Convertible securities price must be at least the weighted average price."
      else "",
    remedy? := some "Ensure convertible securities price is not lower than the weighted average price." },

  { id := "ICDR_14_2_c",
    title := "Initial Public Offer Contribution for Convertible Debt Instruments",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.convertible_debt_instruments_contribution < 20),
    failReason := fun i =>
      if i.convertible_debt_instruments_contribution < 20 then
        "Promoters must contribute at least twenty per cent. of the project cost and issue size."
      else "",
    remedy? := some "Ensure promoters contribute at least twenty per cent. of the project cost and issue size." },

  { id := "ICDR_14_3",
    title := "Satisfying Contribution Requirements Prior to Issue Opening",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.contribution_requirements_satisfied_before_issue_opening),
    failReason := fun i =>
      if !i.contribution_requirements_satisfied_before_issue_opening then
        "Promoters must satisfy the requirements at least one day prior to issue opening."
      else "",
    remedy? := some "Ensure contribution requirements are satisfied before the issue opens." },

  { id := "ICDR_14_4_core",
    title := "Escrow Account for Promoters' Contribution",
    reference := "Minimum promoters’ contribution",
    check := fun i => !(i.escrow_account_for_promoters_contribution && !i.cash_flow_disclosure),
    failReason := fun i =>
      if i.escrow_account_for_promoters_contribution && !i.cash_flow_disclosure then
        "Issuer must disclose the use of funds in the offer document."
      else "",
    remedy? := some "Ensure escrow account for promoters' contribution and cash flow disclosure." },

  { id := "ICDR_5_a",
    title := "Promoters' Contribution: Equity or Convertible Securities",
    reference := "ICDR_5_a",
    check := fun i => !(i.promoter_contribution != "equity" && i.promoter_contribution != "convertibles"),
    failReason := fun i =>
      if i.promoter_contribution != "equity" && i.promoter_contribution != "convertibles" then
        "Promoters must contribute by equity or convertibles."
      else "",
    remedy? := some "Ensure promoters contribute either by equity shares or convertible securities." },

  { id := "ICDR_5_a_provided",
    title := "Promoters' Contribution: Convertible Securities Only",
    reference := "ICDR_5_a_provided",
    check := fun i => !(i.promoter_contribution_type != "convertibles" && !i.contribution_method),
    failReason := fun i =>
      if i.promoter_contribution_type != "convertibles" && !i.contribution_method then
        "Promoters must contribute by subscription to convertible securities."
      else "",
    remedy? := some "Ensure promoters contribute only by way of subscription to the convertible securities." },

  { id := "ICDR_5_b",
    title := "Promoters' Contribution: Weighted Average Price",
    reference := "ICDR_5_b",
    check := fun i => !(i.promoter_contribution_price < i.weighted_average_price),
    failReason := fun i =>
      if i.promoter_contribution_price < i.weighted_average_price then
        "Promoters' contribution price must be at least the weighted average price."
      else "",
    remedy? := some "Ensure promoters' contribution price is not lower than the weighted average price." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("has_outstanding_convertibles", "Does the issuer have any outstanding convertible debt instruments?", "Bool"),
  ("is_debarred", "Is the issuer debarred?", "Bool"),
  ("conversion_price_disclosure_required", "Has the upper limit on price of convertible debt instruments been disclosed to investors?", "Bool"),
  ("full_conversion_within_eighteen_months", "Will the fully convertible debt instruments be converted within eighteen months from issuance?", "Bool"),
  ("warrant_tenure_not_exceed_eighteen_months", "Does the tenure of warrants not exceed eighteen months from allotment in IPO?", "Bool"),
  ("multiple_warrants_per_security", "Can one or more warrants be attached to a specified security?", "Bool"),
  ("upfront_disclosure_of_exercise_price", "Has the exercise price for warrants been disclosed upfront?", "Bool"),
  ("cap_price_disclosure_required", "Is the cap price based on formula disclosed upfront?", "Bool"),
  ("forfeiture_of_unexercised_warrants", "Will unexercised warrant consideration be forfeited by issuer within three months?", "Bool"),
  ("promoters_shareholding", "What percentage of post-issue capital is held by promoters?", "Nat"),
  ("alternative_contributors_to_meet_shortfall", "Are alternative contributors meeting the shortfall in minimum contribution?", "Bool"),
  ("no_identifiable_promoter_exception", "Does the issuer not have any identifiable promoter?", "Bool"),
  ("promoter_contribution_method", "How are promoters contributing (equity or convertibles)?", "String"),
  ("convertible_securities_price", "What is the price of convertible securities?", "Nat"),
  ("weighted_average_price", "What is the weighted average price of equity shares arising from conversion?", "Nat"),
  ("convertible_debt_instruments_contribution", "What percentage of project cost and issue size are promoters contributing through convertible debt instruments?", "Nat"),
  ("contribution_requirements_satisfied_before_issue_opening", "Are contribution requirements satisfied at least one day prior to the date of opening of the issue?", "Bool"),
  ("escrow_account_for_promoters_contribution", "Is the amount of promoters' contribution kept in an escrow account with a scheduled commercial bank?", "Bool"),
  ("cash_flow_disclosure", "Has the issuer disclosed the use of funds in the offer document?", "Bool"),

{ id := "ICDR_5_c",
    title := "Promoters' Contribution: Initial Public Offer of Convertible Debt Instruments",
    reference := "ICDR_5_c",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with promoters' contribution requirements.",
    remedy? := some "Ensure promoters bring in at least 20% of the project cost and 20% of the issue size from their own funds." },

  { id := "ICDR_5_c_provided",
    title := "Promoters' Contribution: Staged Project Implementation",
    reference := "ICDR_5_c_provided",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with staged project implementation requirements.",
    remedy? := some "Ensure promoters' contribution is in line with total equity participation till the respective stage." },

  { id := "ICDR_5_3",
    title := "Promoters' Contribution: Satisfaction Prior to Issue Opening",
    reference := "ICDR_5_3",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with satisfaction prior to issue opening.",
    remedy? := some "Ensure promoters satisfy the requirements at least one day prior to the date of opening of the issue." },

  { id := "ICDR_5_4",
    title := "Promoters' Contribution: Escrow Account Requirement",
    reference := "ICDR_5_4",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with escrow account requirement.",
    remedy? := some "Ensure the amount of promoters' contribution is kept in an escrow account and released along with issue proceeds." },

  { id := "ICDR_5_4_provided",
    title := "Promoters' Contribution: Cash Flow Statement Disclosure",
    reference := "ICDR_5_4_provided",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with cash flow statement disclosure.",
    remedy? := some "Ensure the issuer gives a cash flow statement disclosing the use of funds in the offer document." },

  { id := "ICDR_5_4_provided_further",
    title := "Promoters' Contribution: Partially Paid Shares Requirement",
    reference := "ICDR_5_4_provided_further",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with partially paid shares requirement.",
    remedy? := some "Ensure promoters bring in at least ₹100 crore before the date of opening of the issue and remaining amount on a pro-rata basis." },

  { id := "ICDR_15_1_a",
    title := "Specified securities ineligible for minimum promoters’ contribution (I)",
    reference := "Securities ineligible for minimum promoters’ contribution",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with specified securities eligibility.",
    remedy? := some "Ensure specified securities acquired during the preceding three years meet the criteria." },

  { id := "ICDR_15_1_b",
    title := "Specified securities ineligible for minimum promoters’ contribution (II)",
    reference := "Securities ineligible for minimum promoters’ contribution",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with specified securities eligibility.",
    remedy? := some "Ensure specified securities acquired by the promoters and other entities meet the criteria." },

  { id := "ICDR_15_1_b_i",
    title := "Exception to ineligible specified securities (I)",
    reference := "Securities ineligible for minimum promoters’ contribution",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with exception to ineligible specified securities.",
    remedy? := some "Ensure the difference between the price at which specified securities are offered and acquired is paid." },

  { id := "ICDR_15_1_b_ii",
    title := "Exception to ineligible specified securities (II)",
    reference := "Securities ineligible for minimum promoters’ contribution",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with exception to ineligible specified securities.",
    remedy? := some "Ensure specified securities are acquired under the scheme approved by a High Court or tribunal." },

  { id := "ICDR_5_1_i",
    title := "Difference Payment for Specified Securities",
    reference := "(i)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with difference payment for specified securities.",
    remedy? := some "Ensure the promoters and other entities pay the difference between the price at which specified securities are offered and acquired." },

  { id := "ICDR_5_1_ii",
    title := "Acquisition of Specified Securities under Scheme",
    reference := "(ii)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with acquisition of specified securities under scheme.",
    remedy? := some "Ensure specified securities are acquired in terms of the approved scheme." },

  { id := "ICDR_5_1_iii",
    title := "Initial Public Offer by Government Company or Infrastructure Sector SPV",
    reference := "(iii)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with initial public offer by government company or infrastructure sector SPV.",
    remedy? := some "Ensure the issuer is a government company, statutory authority, corporation, or special purpose vehicle engaged in the infrastructure sector." },

  { id := "ICDR_5_1_iv",
    title := "Conversion or Exchange of Compulsorily Convertible Securities",
    reference := "(iv)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with conversion or exchange of compulsorily convertible securities.",
    remedy? := some "Ensure equity shares arise from the conversion or exchange of fully paid-up compulsorily convertible securities." },

  { id := "ICDR_14_1_c",
    title := "Specified securities ineligible for minimum promoters’ contribution",
    reference := "Regulation 14(1)(c)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with specified securities eligibility.",
    remedy? := some "Ensure specified securities allotted to promoters and other entities meet the criteria." },

  { id := "ICDR_14_2",
    title := "Eligibility of specified securities for promoters’ contribution under certain schemes",
    reference := "Regulation 14(2)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with eligibility of specified securities.",
    remedy? := some "Ensure specified securities are acquired pursuant to an approved scheme." },

  { id := "ICDR_16_1_a",
    title := "Lock-in period for minimum promoters’ contribution",
    reference := "Regulation 16(1)(a)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with lock-in period requirements.",
    remedy? := some "Ensure the minimum promoters' contribution is locked in for eighteen months." },

  { id := "ICDR_16_1_a_Provided",
    title := "Lock-in period for minimum promoters’ contribution (capital expenditure)",
    reference := "Regulation 16(1)(a)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with lock-in period requirements.",
    remedy? := some "Ensure the minimum promoters' contribution is locked in for three years if majority of issue proceeds are used for capital expenditure." },

  { id := "ICDR_16_1_b",
    title := "Lock-in period for promoters’ holding in excess of minimum contribution",
    reference := "Regulation 16(1)(b)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with lock-in period requirements.",
    remedy? := some "Ensure promoters' holding in excess of minimum contribution is locked in for six months." },

  { id := "ICDR_16_1_b_Provided",
    title := "Lock-in period for promoters’ holding (capital expenditure)",
    reference := "Regulation 16(1)(b)",
    check := fun i => True, -- Placeholder as no specific fields are available
    failReason := fun i => "Insufficient data to determine compliance with lock-in period requirements.",
    remedy? := some "Ensure promoters' holding is locked in for one year if majority of issue proceeds are used for capital expenditure." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("promoter_securities_demat", "Are promoter securities dematerialized?", "Bool"),
  ("no_partly_paid_shares", "Does the company have any partly paid shares?", "Bool"),

{ id := "ICDR_16_1_a_provided",
    title := "Lock-in extension for capital expenditure (majority)",
    reference := "Regulation 16(1)",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure majority of issue proceeds excluding offer for sale is used for capital expenditure." },

  { id := "ICDR_16_1_b_provided",
    title := "Lock-in extension for capital expenditure (excess)",
    reference := "Regulation 16(1)",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure majority of issue proceeds excluding offer for sale is used for capital expenditure." },

  { id := "ICDR_16_2",
    title := "Lock-in for SR equity shares",
    reference := "Regulation 16(2)",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure SR equity shares are locked in until conversion or specified period." },

  { id := "ICDR_17_core",
    title := "Lock-in for pre-issue capital held by non-promoters",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure pre-issue capital held by non-promoters is locked in for six months." },

  { id := "ICDR_17_provided_a",
    title := "Exemption for employee stock options/schemes",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure full disclosures with respect to ESOPs or schemes." },

  { id := "ICDR_17_provided_b",
    title := "Exemption for employee stock option trusts",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure compliance with lock-in provisions under SEBI regulations." },

  { id := "ICDR_17_provided_c",
    title := "Exemption for venture capital funds/alternative investment funds",
    reference := "Regulation 17",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in period of at least six months from date of purchase." },

  { id := "ICDR_17_a",
    title := "Exclusion for employee stock options/schemes",
    reference := "Lock-in of specified securities held by persons other than the promoters",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure full disclosures with respect to ESOPs or schemes." },

  { id := "ICDR_17_b",
    title := "Exclusion for employee stock option trusts",
    reference := "Lock-in of specified securities held by persons other than the promoters",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure compliance with lock-in provisions under SEBI regulations." },

  { id := "ICDR_17_c",
    title := "Exclusion for venture capital funds/alternative investment funds",
    reference := "Lock-in of specified securities held by persons other than the promoters",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in period of at least six months from date of purchase." },

  { id := "ICDR_18_core",
    title := "Lock-in provisions for stabilising agent under green shoe option",
    reference := "Lock-in of specified securities lent to stabilising agent under the green shoe option",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in provisions do not apply during the period starting from allotment." },

  { id := "ICDR_64_i",
    title := "Holding period for converted securities and resultant equity shares",
    reference := "ICDR_64_i",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure holding periods of convertible securities and resultant equity shares together meet the six-month period." },

  { id := "ICDR_66_ii_a",
    title := "Bonus shares from free reserves and share premium",
    reference := "ICDR_66_ii_a",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure bonus shares issued out of free reserves and share premium meet the six-month holding period." },

  { id := "ICDR_66_ii_b",
    title := "Bonus shares not from revaluation reserves or unrealized profits",
    reference := "ICDR_66_ii_b",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure bonus shares not issued from revaluation reserves or unrealized profits meet the six-month holding period." },

  { id := "ICDR_67_iii",
    title := "Equity shares include those from employee schemes",
    reference := "ICDR_67_iii",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure equity shares include those from ESOPs, ESPS, and SAR schemes." },

  { id := "ICDR_18",
    title := "Lock-in provisions for specified securities lent to stabilizing agent",
    reference := "ICDR_18",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in provisions do not apply during the period starting from lending and ending on return." },

  { id := "ICDR_19",
    title := "Lock-in for partly paid-up specified securities",
    reference := "ICDR_19",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure lock-in ends only after three years from becoming pari passu with public-issued specified securities." },

  { id := "ICDR_20",
    title := "Inscription or recording of non-transferability",
    reference := "ICDR_20",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure certificates contain 'non-transferable' inscription and lock-in period is recorded." },

  { id := "ICDR_21_a",
    title := "Pledge conditions for lock-in under clause (a) of regulation 16",
    reference := "ICDR_21_a",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure loan is granted to issuer or subsidiary for financing issue objects and pledge is a term of sanction." },

  { id := "ICDR_21_b",
    title := "Pledge conditions for lock-in under clause (b) of regulation 16",
    reference := "ICDR_21_b",
    check := fun i => True, -- Placeholder as no specific fields are provided
    failReason := fun _ => "Condition not met.",
    remedy? := some "Ensure pledge is a term of sanction for the loan." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  ("is_debarred", "Is the issuer debarred?", "Bool"),
  ("has_debarred_directors", "Does the issuer have any debarred directors?", "Bool"),
  ("is_fraudulent", "Is the issuer fraudulent?", "Bool"),
  ("is_fugitive", "Is the issuer a fugitive?", "Bool"),
  ("has_outstanding_convertibles", "Does the issuer have outstanding convertibles?", "Bool"),
  ("has_esop_exemption", "Does the issuer have ESOP exemption?", "Bool"),
  ("has_sar_exemption", "Does the issuer have SAR exemption?", "Bool"),
  ("has_mandatory_convertibles", "Does the issuer have mandatory convertibles?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (₹ paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (₹ paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (₹ paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new-name activity?", "Nat"),

{ id := "ICDR_22",
    title := "Transferability of locked-in specified securities",
    reference := "ICDR_22",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with transferability rules.",
    remedy? := some "Ensure that the specified securities held by promoters and locked-in can be transferred only under the conditions stipulated." },

  { id := "ICDR_23_1",
    title := "Appointment of lead managers",
    reference := "ICDR_23_1",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with lead manager appointment rules.",
    remedy? := some "Ensure that the issuer appoints one or more registered merchant bankers as lead managers." },

  { id := "ICDR_23_2",
    title := "Rights, obligations and responsibilities of lead managers",
    reference := "ICDR_23_2",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with lead manager rights and responsibilities rules.",
    remedy? := some "Ensure that the issuer specifies the rights, obligations, and responsibilities of each lead manager in the draft offer document." },

  { id := "ICDR_23_3",
    title := "Non-associate lead manager requirement",
    reference := "ICDR_23_3",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with non-associate lead manager rules.",
    remedy? := some "Ensure that at least one lead manager is not an associate of the issuer and disclose any associates' roles." },

  { id := "ICDR_23_4",
    title := "Appointment of other intermediaries",
    reference := "ICDR_23_4",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with intermediary appointment rules.",
    remedy? := some "Ensure that the issuer appoints other registered intermediaries after assessing their capabilities." },

  { id := "ICDR_23_5",
    title := "Agreements with lead managers and intermediaries",
    reference := "ICDR_23_5",
    check := fun i => True, -- Placeholder as no specific Issuer fields are provided
    failReason := fun _ => "Insufficient data to determine compliance with agreement formats rules.",
    remedy? := some "Ensure that the issuer enters into agreements with lead managers and intermediaries in the specified format." }
]

def issuerQuestionsChunk : List (String × String × String) := [
  -- Placeholder as no specific Issuer fields are provided
]

def issuerQuestions : List (String × String × String) := [
("has_outstanding_convertibles", "Are there any outstanding convertible securities?", "Bool"),
  ("has_esop_exemption", "Is the company exempt under employee stock option schemes?", "Bool"),
  ("has_sar_exemption", "Is the company exempt under stock appreciation rights schemes?", "Bool"),
  ("has_mandatory_convertibles", "Have all convertible securities been converted as required?", "Bool"),
  ("monetary_asset_ratio", "What percentage of net tangible assets are held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been utilized or committed for business/project?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("is_tech_firm", "Is the issuer intensive in technology, information technology, intellectual property, data analytics, bio-technology or nano-technology?", "Bool"),
  ("sr_net_worth", "What is the net worth of the SR shareholder as determined by a Registered Valuer (₹ paise)?", "Nat"),
  ("sr_holder_exec", "Are SR shares issued only to promoters/founders who hold an executive position?", "Bool"),
  ("sr_voting_ratio", "What is the voting rights ratio for SR equity shares compared to ordinary shares?", "Nat"),
  ("sr_same_face_value", "Do SR equity shares have the same face value as ordinary shares?", "Bool"),
  ("sr_class_count", "How many classes of SR equity shares does the issuer have?", "Nat"),
  ("shares_held_duration_months", "For how long have the SR shares been held (in months)?", "Nat"),
  ("applied_to_stock_exchange", "Has the issuer applied to stock exchanges for listing?", "Bool"),
  ("has_demat_agreement", "Does the issuer have an agreement with a depository for dematerialization?", "Bool"),
  ("promoter_securities_demat", "Are all promoter securities in dematerialized form?", "Bool"),
  ("no_partly_paid_shares", "Do any partly paid-up equity shares exist?", "Bool"),
  ("finance_75_percent_done", "Has the issuer made firm arrangements for at least 75% of project finance?", "Bool"),
("general_corp_purpose_ratio", "What % of funds raised is allocated to general corporate purposes?", "Nat"),
  ("shares_held_duration_months", "How long have the shares been held by the seller(s)? (in months)", "Nat"),
  ("is_govt_entity", "Is the issuer a government company or statutory authority?", "Bool"),
  ("via_merger_scheme", "Were the equity shares acquired pursuant to a High Court/tribunal/Central Government scheme?", "Bool"),
  ("is_bonus_from_free_reserve", "Are bonus shares issued from free reserves and share premium?", "Bool"),
  ("bonus_not_from_revaluation", "Are bonus shares not issued by utilizing revaluation reserves or unrealized profits?", "Bool"),
("is_debarred", "Is the issuer debarred?", "Bool"),
  ("has_debarred_directors", "Does the issuer have debarred directors?", "Bool"),
  ("is_fraudulent", "Is the issuer fraudulent?", "Bool"),
  ("is_fugitive", "Is the issuer a fugitive?", "Bool"),
("has_outstanding_convertibles", "Does the issuer have any outstanding convertible debt instruments?", "Bool"),
  ("is_debarred", "Is the issuer debarred?", "Bool"),
  ("conversion_price_disclosure_required", "Has the upper limit on price of convertible debt instruments been disclosed to investors?", "Bool"),
  ("full_conversion_within_eighteen_months", "Will the fully convertible debt instruments be converted within eighteen months from issuance?", "Bool"),
  ("warrant_tenure_not_exceed_eighteen_months", "Does the tenure of warrants not exceed eighteen months from allotment in IPO?", "Bool"),
  ("multiple_warrants_per_security", "Can one or more warrants be attached to a specified security?", "Bool"),
  ("upfront_disclosure_of_exercise_price", "Has the exercise price for warrants been disclosed upfront?", "Bool"),
  ("cap_price_disclosure_required", "Is the cap price based on formula disclosed upfront?", "Bool"),
  ("forfeiture_of_unexercised_warrants", "Will unexercised warrant consideration be forfeited by issuer within three months?", "Bool"),
  ("promoters_shareholding", "What percentage of post-issue capital is held by promoters?", "Nat"),
  ("alternative_contributors_to_meet_shortfall", "Are alternative contributors meeting the shortfall in minimum contribution?", "Bool"),
  ("no_identifiable_promoter_exception", "Does the issuer not have any identifiable promoter?", "Bool"),
  ("promoter_contribution_method", "How are promoters contributing (equity or convertibles)?", "String"),
  ("convertible_securities_price", "What is the price of convertible securities?", "Nat"),
  ("weighted_average_price", "What is the weighted average price of equity shares arising from conversion?", "Nat"),
  ("convertible_debt_instruments_contribution", "What percentage of project cost and issue size are promoters contributing through convertible debt instruments?", "Nat"),
  ("contribution_requirements_satisfied_before_issue_opening", "Are contribution requirements satisfied at least one day prior to the date of opening of the issue?", "Bool"),
  ("escrow_account_for_promoters_contribution", "Is the amount of promoters' contribution kept in an escrow account with a scheduled commercial bank?", "Bool"),
  ("cash_flow_disclosure", "Has the issuer disclosed the use of funds in the offer document?", "Bool"),
("promoter_securities_demat", "Are promoter securities dematerialized?", "Bool"),
  ("no_partly_paid_shares", "Does the company have any partly paid shares?", "Bool"),
("is_debarred", "Is the issuer debarred?", "Bool"),
  ("has_debarred_directors", "Does the issuer have any debarred directors?", "Bool"),
  ("is_fraudulent", "Is the issuer fraudulent?", "Bool"),
  ("is_fugitive", "Is the issuer a fugitive?", "Bool"),
  ("has_outstanding_convertibles", "Does the issuer have outstanding convertibles?", "Bool"),
  ("has_esop_exemption", "Does the issuer have ESOP exemption?", "Bool"),
  ("has_sar_exemption", "Does the issuer have SAR exemption?", "Bool"),
  ("has_mandatory_convertibles", "Does the issuer have mandatory convertibles?", "Bool"),
  ("net_tangible_assets", "Provide NTA for each of the last 3 full years (₹ paise).", "List Nat"),
  ("monetary_asset_ratio", "What % of NTA is held in monetary assets?", "Nat"),
  ("used_monetary_assets", "Have excess monetary assets been used or firmly committed?", "Bool"),
  ("is_offer_for_sale_only", "Is the IPO entirely an offer for sale (no fresh issue)?", "Bool"),
  ("operating_profits", "Provide operating profit for each of the last 3 full years (₹ paise).", "List Nat"),
  ("net_worths", "Provide net worth for each of the last 3 full years (₹ paise).", "List Nat"),
  ("changed_name_recently", "Has the company changed its name within the last 1 year?", "Bool"),
  ("percent_revenue_from_new_name", "What % of last year’s revenue came from the new-name activity?", "Nat"),
-- Placeholder as no specific Issuer fields are provided
]

end GeneratedRules
