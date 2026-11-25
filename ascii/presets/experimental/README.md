# M8.1 experimental glyph-library preset

`ASCII_M8_1_GlyphLibrary.blend` is a copy of the approved v2 preset with the glyph
geometry replaced by an independent, bbox-centred Bfont library. The approved preset
is untouched.

What changed:

- nine independent mesh objects (`glyph_0` … `glyph_8`) in the hidden `M8_Glyphs`
  collection; space is an empty mesh;
- `Collection Info` with separate/reset children and one `Instance on Points`;
- `Glyph Size` scales the library uniformly at any density;
- `Vertices X/Y = Grid X/Y + 1` so Blender creates the same number of **faces** as
  the index-map cells (the approved preset creates one fewer row/column);
- index 0 has no geometry;
- the original UV/colour path remains connected to the cell position.

Validation:

- `_discovery/milestone8_1/gate_report.json` — all six grids pass index 0, centre,
  corners, checkerboard, ramp, reordered ramp, uniform index mapping and colour bands.
- `_discovery/milestone8_1/ab/` — A/B/C/D comparison stills and metrics.
- `_discovery/milestone8_1/editorial/round_01/round_01.mp4` — 9 s vertical editorial
  prototype.

Usage constraints:

- Not approved for production and not selected by `preset.py`.
- Use a lossless **index movie** (`video_index_job` style) rather than an image
  sequence: the image-sequence + Scene Time link crashes with this graph in Blender
  5.3. `gcf/ascii/blender_job.py` has an optional `link_index_time` job field
  (default true) for that experimental path.
- The corrected path still needs a formal GUI/production integration before it can be
  selected automatically.
