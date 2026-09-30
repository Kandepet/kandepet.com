---
title: "Katana STL slicer"
date: "2017-06-01T22:46:25Z"
lastmod: "2017-06-01T22:46:25Z"
slug: "katana"
---

Katana is an experimental stl slicer and gcode generator for reprap 3D printers. Written in C++, Katana is based on schlizzer, written by Paul Geisler.

Usage: ./katana inputfile.stl outputfile.gcode

Important features missing w.r.t Slic3r:

- No discrimination of 'solid' and 'fill' areas. They are handled equally with fill\_density=1.
- Only 'rectilinear' fill pattern supported.
- No contour correction of perimeter and infill, so the object exceeds the specified .stl
- Bad route planning leading to bad movement order with useless many and long travels
- Even worse planning for 'non manifold' objects (most of thingyverse i guess..)
- No brim, skirt, cooling etc.
- No automatic placement and z leveling
- Generated Gcode need to be extended before printing

Github: <https://github.com/Kandepet/katana>
