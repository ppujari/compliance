import Main
open Main
namespace GeneratedRules

def generatedRuleset : List ComplianceRule := [
-- Add your generated ComplianceRule definitions here,

-- Add your ComplianceRule definitions here, one per item
  rule "ICDR_4_13_a" do
    description "Initial public offer; payment for specified securities acquired by promoters."
    predicate fun p (issuer : Issuer) =>
      issuer.specifiedSecuritiesAcquiredByPromoters.map (_.priceInIPO) <> [] &&
      issuer.specifiedSecuritiesAcquiredByPromoters.map (_.acquisitionPrice) <> [] &&
      issuer.specifiedSecuritiesAcquiredByPromoters.map (_.priceInIPO) - issuer.specifiedSecuritiesAcquiredByPromoters.map (_.acquisitionPrice) == issuer.paymentForSpecifiedSecurities
    failReason "The difference between the price at which specified securities are offered in the initial public offer and the price at which they were acquired is not paid to the issuer."
  -- Add more rules here...,

{ id := "ICDR_21_a",
    title := "Pledge of locked-in specified securities (a)",
    reference := "Regulation 21(a)",
    check := fun i => i.loan_granted_to_issuer && i.purpose_of_issue,
    failReason := fun i => "Loan not granted to issuer company or subsidiary for the purpose of financing one or more of the objects of the issue.",
    remedy? := some "Ensure loan is granted to issuer company or subsidiary for the purpose of financing one or more of the objects of the issue." },
  { id := "ICDR_21_b",
    title := "Pledge of locked-in specified securities (b)",
    reference := "Regulation 21(b)",
    check := fun i => i.loan_terms && i.pledge_of_specified_securities,
    failReason := fun i => "Pledge of specified securities not one of the loan terms.",
    remedy? := some "Ensure pledge of specified securities is one of the loan terms." },
  { id := "ICDR_21",
    title := "Pledge of locked-in specified securities",
    reference := "Regulation 21",
    check := fun i => !(i.sr_equity_shares) && i.promoters_locked_in,
    failReason := fun i => "Specified securities held by promoters not locked-in or SR equity shares included.",
    remedy? := some "Ensure specified securities held by promoters are locked-in and exclude SR equity shares." },
  { id := "ICDR_22",
    title := "Transfer of locked-in specified securities",
    reference := "ICDR_22",
    check := fun i => (i.promoters_locked_in && (i.transfer_to_promoter || i.transfer_to_promoter_group || i.new_promoter)) || (i.others_locked_in && i.transfer_to_any_person),
    failReason := fun i =>
      if i.promoters_locked_in then
        if !(i.transfer_to_promoter || i.transfer_to_promoter_group || i.new_promoter) then "Transfer to another promoter or any person of the promoter group or a new promoter not allowed."
        else if i.lockin_period_remaining > 0 && i.transferee_eligible_to_transfer then "Transferee is eligible to transfer locked-in specified securities before lock-in period expires."
      else "Specified securities held by persons other than the promoters not locked-in as per regulation  17.",
    remedy? := some "Ensure transfer complies with SEBI regulations and lock-in period is respected." },
  { id := "ICDR_23",
    title := "Rights, obligations and responsibilities of lead managers",
    reference := "ICDR_23",
    check := fun i => i.predetermined_and_disclosed,
    failReason := fun i => "Rights, obligations and responsibilities not predetermined and disclosed.",
    remedy? := some "Predetermine and disclose rights, obligations and responsibilities of lead managers." }
]

def issuerQuestions : List (String × String × String) := [
("min_holding_period", "How long have the equity shares been held before offering for sale?", Bool),
  ("convertible_securities_holding_period", "What is the holding period of convertible securities and resulting equity shares?", Nat),
  ("max_sale_unidentified_targets", "What percentage of funds can be used for unidentified acquisition or investment targets?", Nat),
  ("credit_rating", "Has the issuer obtained credit rating from at least one credit rating agency?", Bool),
  ("debenture_trustee", "Has the issuer appointed a debenture trustee in accordance with the provisions of the Companies Act, 2013 and the Securities and Exchange Board of India (Debenture Trustees) Regulations, 1993?", Bool),
  ("debenture_redemption_reserve", "Has the issuer created a debenture redemption reserve in accordance with the provisions of the Companies Act, 2013 and rules made thereunder?", Bool),
  ("consent_for_conversion", "Did holders of convertible debt instruments send positive consent to the issuer for conversion into equity shares?", Bool),
  ("option_not_convert", "Do holders of listed convertible debt instruments have the option of not converting the convertible portion into equity shares if the conversion price is undetermined?", Bool),
-- Add your Issuer questions here, one per field used in your generated checks
  ("specifiedSecuritiesAcquiredByPromoters", "What are the specified securities acquired by promoters?", "List Nat"),
  ("paymentForSpecifiedSecurities", "How much was paid for the specified securities acquired by promoters?", "Nat")
  -- Add more questions here...,
{ "loan_granted_to_issuer", "Has the loan been granted to the issuer company or its subsidiary(ies)?", "Bool" },
  { "purpose_of_issue", "For what purpose was the loan granted?", "String" },
  { "loan_terms", "What are the terms of the loan?", "String" },
  { "pledge_of_specified_securities", "Is pledging specified securities one of the loan terms?", "Bool" },
  { "sr_equity_shares", "Are SR equity shares included in the specified securities?", "Bool" },
  { "promoters_locked_in", "Are the specified securities held by the promoters locked-in?", "Bool" },
  { "lockin_period_remaining", "How much time remains for the lock-in period on the specified securities?", "Nat" },
  { "transferee_eligible_to_transfer", "Is the transferee eligible to transfer locked-in specified securities?", "Bool" },
  { "transfer_to_promoter", "Will the specified securities be transferred to another promoter?", "Bool" },
  { "transfer_to_promoter_group", "Will the specified securities be transferred to any person of the promoter group?", "Bool" },
  { "new_promoter", "Will the specified securities be transferred to a new promoter?", "Bool" },
  { "transfer_to_any_person", "Will the specified securities held by persons other than the promoters be transferred to any other person holding the specified securities which are locked-in along with the securities proposed to be transferred?", "Bool" },
  { "predetermined_and_disclosed", "Are the rights, obligations and responsibilities of lead managers predetermined and disclosed?", "Bool" }
]

end GeneratedRules
