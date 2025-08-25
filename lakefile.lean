import Lake
open Lake DSL

package «compliance» where
  -- optional: version := v!"0.1"

@[default_target]
lean_exe «compliance» where
  root := `Main
