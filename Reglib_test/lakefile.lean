-- Reglib/lakefile.lean
import Lake
open Lake DSL

package Reglib where
  name        := "Reglib"
  version     := "0.1.0"
  description := "Formal regulatory library for SEBI ICDR compliance verification"

lean_lib Reglib where
  roots := #[`Reglib]
