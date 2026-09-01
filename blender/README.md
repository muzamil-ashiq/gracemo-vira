# GraceEMO Blender project

Starter scene for modeling the **LPU campus** and **GRACEEMO-01** at real scale (meters).

## Regenerate all artifacts

```bash
./tools/regenerate_artifacts.sh
```

This writes:

| Artifact | Path |
|----------|------|
| Engineering prototype | `GRACEEMO-01_Engineering_Prototype.blend` |
| Engineering preview | `GRACEEMO_preview.png` |
| Professional hero | `GRACEEMO-01_PROFESSIONAL_v3.blend` |
| Professional preview | `GRACEEMO-01_v3_preview.png` |
| Campus scene | `GraceEMO_LPU.blend` |
| Campus GLB | `GraceEMO_LPU_preview.glb` |
| Campus render | `GraceEMO_LPU_preview.png` |
| Robot GLB (engineering) | `graceemo_ws/.../meshes/GRACEEMO-01_robot.glb` |
| Robot GLB (campus URDF) | `.../meshes/GRACEEMO-01_campus_robot.glb` |
| Manifest | `ARTIFACTS.json` |

## Generate / refresh `GraceEMO_LPU.blend` only

After installing Blender 5.2 from the DMG:

```bash
# GUI install: open blender-5.2.1-macos-arm64.dmg, drag Blender into /Applications

"/Applications/Blender.app/Contents/MacOS/Blender" --background --python \
  blender/scripts/build_graceemo_lpu.py
```

Then open `blender/GraceEMO_LPU.blend`.

Inside Blender: **Scripting** workspace → Open `blender/scripts/build_graceemo_lpu.py` → Run Script (rebuilds the file).

## What you should model

| Collection | Purpose |
|------------|---------|
| `01_Campus` / Buildings | Replace box LOD with real facades. Keep object names (`block_37`, `uni_mall`, …). |
| `02_GRACEEMO_01` / `ROS_Frames` | **Do not delete** empties (`base_link`, `lidar_link`, `camera_link`, `head_link`, hands). |
| `Robot_Visual` | Sculpt / replace `*_visual` meshes parented to those frames. |
| `Robot_HeroSculpt_Optional` | Larger humanoid **guide only** (wire). Not URDF collision. |

Export finished meshes to `graceemo_ws/src/gracemo_description/meshes/` (glTF or DAE) and point the xacro `<mesh>` tags at them.

Campus footprints stay **approximate** until you replace them with surveyed geometry (`DATA_SOURCES.md`).
