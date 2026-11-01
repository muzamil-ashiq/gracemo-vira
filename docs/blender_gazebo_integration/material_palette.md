# Material & Color Palette Pipeline

This document details the configurable material architecture and color palette implemented for the GRaCEmo ViRa Blender-to-Gazebo asset pipeline.

---

## 1. Centralized Palette Configuration

All material definitions are managed through a single configuration file:  
📁 [staging_blender_integration/config/palette_config.json](file:///home/sabarishchandrasekaran/projects/VIRA-agent-bridge-migration/staging_blender_integration/config/palette_config.json)

```json
{
  "palette": {
    "GRACE_WHITE": {
      "hex": "#F5F5F5",
      "rgb": [0.9608, 0.9608, 0.9608],
      "roughness": 0.28,
      "metallic": 0.05,
      "description": "Main body shell, head casing, and outer arm pods"
    },
    "GRACE_BLACK": {
      "hex": "#111111",
      "rgb": [0.0667, 0.0667, 0.0667],
      "roughness": 0.35,
      "metallic": 0.30,
      "description": "Internal chassis structure, camera bar, antenna, bezels"
    },
    "GRACE_ACCENT": {
      "hex": "#FF7900",
      "rgb": [1.0000, 0.4745, 0.0000],
      "roughness": 0.35,
      "metallic": 0.10,
      "description": "Safety orange trim, wheel accent rings, neck ring, chest button"
    },
    "GRACE_TIRE": {
      "hex": "#222222",
      "rgb": [0.1333, 0.1333, 0.1333],
      "roughness": 0.80,
      "metallic": 0.00,
      "description": "High-grip dark rubber tire treads"
    },
    "GRACE_SCREEN": {
      "hex": "#111111",
      "rgb": [0.0667, 0.0667, 0.0667],
      "roughness": 0.05,
      "metallic": 0.00,
      "specular": [0.8, 0.8, 0.8],
      "description": "High-gloss dark glass OLED face display"
    },
    "GRACE_BLUE_GLOW": {
      "hex": "#00D9FF",
      "rgb": [0.0000, 0.8510, 1.0000],
      "roughness": 0.10,
      "emission": [0.0000, 0.8510, 1.0000],
      "description": "Cyan illuminated facial features, eye pupils, smile, wheel hubs"
    }
  }
}
```

---

## 2. Generated Material Library (`gracemo_palette.mtl`)

The export pipeline generates a standard Wavefront Material Template Library (`.mtl`) referencing these PBR properties:

```
newmtl GRACE_WHITE
Kd 0.9608 0.9608 0.9608
Ks 0.15 0.15 0.15
Ns 80.0
d 1.0
illum 2

newmtl GRACE_ACCENT
Kd 1.0000 0.4745 0.0000
Ks 0.20 0.20 0.20
Ns 60.0
d 1.0
illum 2

newmtl GRACE_TIRE
Kd 0.1333 0.1333 0.1333
Ks 0.02 0.02 0.02
Ns 10.0
d 1.0
illum 2

newmtl GRACE_BLUE_GLOW
Kd 0.0000 0.8510 1.0000
Ke 0.0000 0.8510 1.0000
Ks 0.50 0.50 0.50
Ns 100.0
d 1.0
illum 2
```

All 11 link visual `.obj` files declare `mtllib gracemo_palette.mtl` at their header and use `usemtl <NAME>` for each sub-geometry.

---

## 3. How to Update Colors (Zero URDF Editing Required)

To change the robot's appearance to a new custom palette:

1. **Edit the Palette Configuration:**
   Open `staging_blender_integration/config/palette_config.json` and change any hex color or roughness value.
2. **Re-run the Exporter:**
   ```bash
   /snap/bin/blender --background ~/gracemo_gazebo/gracemo_blender_to_gazebo/robot.blend \
     --python staging_blender_integration/scripts/export_blender_to_gazebo_obj.py
   ```
3. **Deploy Assets to Package Shares:**
   ```bash
   cp staging_blender_integration/meshes/* \
     ~/projects/VIRA/prototypes/gracemo_integrated_v1/ros2_ws/src/gracemo_robot_description/meshes/
   cp staging_blender_integration/meshes/* \
     ~/projects/VIRA-agent-bridge-migration/ros2_ws/src/gracemo_description/meshes/
   ```
4. **Result:** The new color scheme takes effect immediately upon next simulation launch. No URDF or Xacro files need to be modified.
