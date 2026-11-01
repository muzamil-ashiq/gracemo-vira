#!/usr/bin/env python3
"""
GRaCEmo ViRa — Standardize and Fix Gazebo Fuel Model Symlinks
Ensures that all downloaded Fuel models in ~/.gz/fuel can properly resolve:
  - model.config
  - model.sdf
  - meshes/
  - materials/ (including materials/textures/)
  - root diffuse textures (e.g. Table_Diffuse.jpg, bookshelf_diffuse.jpg)
  - snake_case aliases (cardboard_box, coke_can)
"""

import os
from pathlib import Path

def setup_fuel_symlinks():
    fuel_models_dir = Path(os.path.expanduser("~/.gz/fuel/fuel.gazebosim.org/openrobotics/models"))
    if not fuel_models_dir.exists():
        print(f"Directory not found: {fuel_models_dir}")
        return

    print(f"Standardizing Fuel model cache at: {fuel_models_dir}")

    for model_dir in sorted(fuel_models_dir.iterdir()):
        if not model_dir.is_dir() or model_dir.is_symlink():
            continue

        # Find version subdirectories (e.g., '1', '2', '3', '4')
        version_dirs = [d for d in model_dir.iterdir() if d.is_dir() and not d.is_symlink() and d.name.isdigit()]
        if not version_dirs:
            continue

        # Pick highest version
        version_dirs.sort(key=lambda d: int(d.name))
        latest_ver = version_dirs[-1]
        ver_name = latest_ver.name
        print(f"\nProcessing model: '{model_dir.name}' (using version '{ver_name}')")

        # 1. Ensure 'current' symlink
        current_symlink = model_dir / "current"
        if not current_symlink.exists():
            current_symlink.symlink_to(ver_name)
            print(f"  + Created: current -> {ver_name}")

        # 2. Check all items in latest_ver and link them to model_dir if missing
        for item in latest_ver.iterdir():
            target_link = model_dir / item.name
            if target_link.is_symlink():
                # Check if valid
                if not target_link.exists():
                    print(f"  - Removing dead symlink: {target_link.name}")
                    target_link.unlink()
                else:
                    continue

            if not target_link.exists():
                # Create relative symlink
                rel_target = f"{ver_name}/{item.name}"
                target_link.symlink_to(rel_target)
                print(f"  + Created: {item.name} -> {rel_target}")

        # 3. Clean up any remaining dead symlinks at model root
        for item in model_dir.iterdir():
            if item.is_symlink() and not item.exists():
                print(f"  - Removing dead symlink: {item.name} -> {os.readlink(item)}")
                item.unlink()

    # 4. Create common name aliases (e.g. 'cardboard box' -> 'cardboard_box')
    aliases = {
        "cardboard_box": "cardboard box",
        "coke_can": "coke can",
    }
    for alias, target in aliases.items():
        alias_path = fuel_models_dir / alias
        target_path = fuel_models_dir / target
        if target_path.exists():
            if alias_path.is_symlink() and not alias_path.exists():
                alias_path.unlink()
            if not alias_path.exists():
                alias_path.symlink_to(target)
                print(f"\n+ Created Model Alias: {alias} -> '{target}'")

    # 5. Fix mesh-internal relative texture paths (e.g. cardboard_box expects texture in meshes/)
    cb_tex = fuel_models_dir / "cardboard box" / "3" / "materials" / "textures" / "cardboard_box.png"
    cb_mesh_tex = fuel_models_dir / "cardboard box" / "3" / "meshes" / "cardboard_box.png"
    if cb_tex.exists() and not cb_mesh_tex.exists():
        cb_mesh_tex.symlink_to("../materials/textures/cardboard_box.png")
        print("  + Created cardboard_box mesh texture symlink")

    print("\n✅ All Fuel model symlinks verified successfully.")

if __name__ == "__main__":
    setup_fuel_symlinks()
