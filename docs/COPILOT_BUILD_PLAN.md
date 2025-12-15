# COPILOT_BUILD_PLAN.md

**Milestone 1 — Packaging**

* Implement `.stella` as ZIP with `manifest.json`
* Implement read/write helpers
* Add checksum generation

**Milestone 2 — Collision**

* Implement `collision.rlevox` read/write
* Unit tests: round-trip equality + row run validation

**Milestone 3 — Floorplan → World**

* Implement floorplan pipeline producing:
  * `levels/0/render.glb`
  * `levels/0/collision.rlevox`
  * correct manifest/level json
* Generate `examples/sample.stella`

**Milestone 4 — VS Code viewer**

* Create custom editor that:
  * opens `.stella`
  * displays GLB
  * supports WASD + mouse look
  * enforces collision from `collision.rlevox`

**Milestone 5 — Video**

* Add CLI wrapper that runs MASt3R-SLAM and packages result
* Keep rendering simple first (points ok)

**Milestone 6 — Polish**

* Multi-level
* Semantics overlays (room labels)
* Navmesh generation (optional)