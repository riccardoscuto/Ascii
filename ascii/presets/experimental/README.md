# Experimental glyph-library presets

`ASCII_M8_1_GlyphLibrary.blend` is the first experimental copy of v2 with independent,
bbox-centred Bfont glyphs. `ASCII_M8_2_GlyphLibrary.blend` and
`ASCII_M8_2_Decoupled.blend` are the same graph with an orthographic camera and the
backend movie-index path.

The approved v2 preset and BlueFox are untouched.

What changed:

- nine independent mesh objects (`glyph_0` … `glyph_8`) in the hidden `M8_Glyphs`
  collection; space is an empty mesh;
- `Collection Info` with separate/reset children and one `Instance on Points`;
- `Glyph Size` scales the library uniformly at any density;
- `Vertices X/Y = Grid X/Y + 1` so Blender creates the same number of **faces** as the
  index-map cells;
- index 0 has no geometry;
- the original UV/colour path remains connected to the cell position;
- `ASCII_M8_2_Decoupled.blend` adds `Color Map` and `Intensity Map` textures and
  multiplies them into `clr`; the backend supplies lossless FFV1 movies for both.

Selectable renderers:

- `v2` — approved preset;
- `glyph-library` — corrected geometry, adaptive/highlight maps;
- `glyph-library-decoupled` — corrected geometry + separate index/colour/intensity
  maps.

The CLI exposes `--renderer`. The backend creates and validates the exact FFV1 index
movie; the image-sequence + Scene Time path crashes with this graph in Blender 5.3 and
is not used.

Validation:

- `_discovery/milestone8_1/gate_report.json`;
- `_discovery/milestone8_2/backend_checks.json`;
- `_discovery/milestone8_2/compare/`;
- `_discovery/milestone8_2/rounds/three_rounds.mp4`.

These presets are still experimental: they are not the default and are not integrated
into the GUI.
