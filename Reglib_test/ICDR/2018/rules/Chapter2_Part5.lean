-- Auto-generated rules file: Chapter2_Part5.lean
-- Chapter II, Part V: APPOINTMENT OF LEAD MANAGERS, OTHER INTERMEDIARIES AND

import Reglib.ICDR.definitions.Core

namespace Reglib.ICDR.Rules

open Reglib.ICDR

/-! ## Regulation 23 -/
/-- Reg 23(1): The issuer shall appoint one or more merchant bankers, which are registered with the Board, as lead manager(s) to the is... -/
def reg_23_1 (issuer : Issuer) : Prop :=
  issuer.has_lead_manager_appointed = true

/-- Reg 23(2): Where the issue is managed by more than one lead manager, the rights, obligations and responsibilities, relating inter a... -/
def reg_23_2 (issuer : Issuer) : Prop :=
  issuer.has_disclosed_lead_manager_rights_obligations = true

/-- Reg 23(3): At least one lead manager to the issue shall not be an associate (as defined under the Securities and Exchange Board of ... -/
def reg_23_3 (issuer : Issuer) : Prop :=
  issuer.has_non_associate_lead_manager = false

/-- Reg 23(4): The issuer shall, in consultation with the lead manager(s), appoint other intermediaries which are registered with the B... -/
def reg_23_4 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 23(5): The issuer shall enter into an agreement with the lead manager(s) in the format specified in Schedule II and enter into ... -/
def reg_23_5 (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Reg 23(5)(proviso): such agreements may include such other clauses as the issuer and the intermediaries may deem fit without diminishing or ... -/
def reg_23_5_proviso (issuer : Issuer) : Prop :=
  sorry  -- TODO: no fields extracted

/-- Combined Regulation 23 gate -/
def reg_23_eligible (issuer : Issuer) : Prop :=
  reg_23_1 issuer
  ∧ reg_23_2 issuer
  ∧ reg_23_3 issuer

/-! ## Composite Chapter II Part V Gate -/

def chapter2_part5_eligible (issuer : Issuer) : Prop :=
  reg_23_eligible issuer

end Reglib.ICDR.Rules
