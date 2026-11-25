# Glyph atlas

`branch_atlas.png` is a 64 px-per-cell raster of the exact Bfont glyphs used by the
ASCII preset, in ramp order `" .,:;+HW@"`.  It is generated with Blender's
String-to-Curves/Fill path and is used only by the diagnostic raster renderer
(`gcf/ascii/reference.py`); it does not replace the production Blender renderer.

Regenerate with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" -b --factory-startup `
  --python tools/make_glyph_atlas.py
```

The atlas is intentionally small and tracked so the diagnostic renderer is
reproducible after a clone.
