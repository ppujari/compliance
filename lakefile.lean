import Lake
open Lake DSL

package compliance

lean_lib Src where
  srcDir := "."

@[default_target]
lean_exe compliance where
  root := `Src.Main_v2
