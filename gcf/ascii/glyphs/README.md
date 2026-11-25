# Glyph atlas

`branch_atlas.png` is a 64 px-per-cell raster of the complete Bfont glyphs used by
the ASCII renderer, in ramp order `" .,:;+HW@"`. It is built from the same bbox-centred
text meshes as the M8.1 independent glyph library, so `@`, `W` and the other glyphs are
not clipped at the cell edge. It is used only by the diagnostic raster renderer
(`gcf/ascii/reference.py`); it does not replace the production Blender renderer.

Regenerate with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --factory-startup `
  --python tools/make_text_glyph_atlas.py
```

The atlas is intentionally small and tracked so the diagnostic renderer is
reproducible after a clone.
