from pathlib import Path
p=Path('deep-shift-visual/scripts/VisualArt.gd')
s=p.read_text()
old='draw_arc(Vector2.ZERO,18+t%1.0*8,0,TAU,40,Color(1,0.25,0.08,0.35*(1.0-(t%1.0))),2)'
new='var cycle := fmod(t, 1.0)\n    draw_arc(Vector2.ZERO,18+cycle*8,0,TAU,40,Color(1,0.25,0.08,0.35*(1.0-cycle)),2)'
if old not in s:
    raise SystemExit('PASS12 HOTFIX MISS')
p.write_text(s.replace(old,new,1))
print('DEEP_SHIFT_PASS12_HOTFIX: PASS')
