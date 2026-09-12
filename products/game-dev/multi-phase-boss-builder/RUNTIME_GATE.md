# GameMaker Runtime Certification Gate

The JakeAI Boss Builder is not considered GameMaker-runtime certified until a generated encounter compiles with the current GameMaker runtime and passes a minimal playtest.

## Gate order

1. Run `python validate_scaffold.py cosmic_vending_machine.gml`.
2. Import/integrate the generated scaffold into a minimal GameMaker project.
3. Compile with GameMaker Igor using `igor_compile_gate.ps1`.
4. Reject certification on any compiler error or warning that changes encounter behavior.
5. Run the encounter and verify:
   - telegraph always precedes damaging attack;
   - damage only lands during intended recovery windows;
   - phase transitions fire once and in order;
   - Phase 3 cannot be defeated by HP damage;
   - three valid product returns reach defeated state;
   - encounter completion fires once;
   - reset/restart restores all state.

## Current status

Static deterministic validation: READY.
Browser behavioral harness: READY.
GameMaker Igor compile: PENDING an environment with GameMaker installed and an authenticated IDE/runtime.
GameMaker playtest: PENDING compile gate.

The official GameMaker command-line workflow requires GameMaker and the required runtime to be installed; Igor is supplied inside the runtime directory. GameMaker documentation also notes that the IDE account must have been logged in before command-line building.
