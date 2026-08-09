# Mixamo Rig Kai

Mixamo Rig Kai is a Blender add-on forked from the original Mixamo Rig project created by BeyondDev (Tyler Walker).

This project is currently under active development. Kai focuses on flexible humanoid rig generation from editable Reference Skeletons, with safer iteration during character production.

## Features

- Reference Skeleton generation from bundled templates
- Reference Skeleton Mapping for non-standard humanoid skeletons
- Variable Spine support
- Variable Neck support
- Optional Shoulder support
- Flexible humanoid control rig generation
- Rebuild Rig workflow for safely regenerating generated rig data
- Improved support for production workflows where skeleton edits continue after rig generation

## Reference Templates

Available templates:

- Humanoid Basic
- Humanoid Fingers

## Control Rig Workflow

A typical humanoid workflow is:

1. Create a Reference Skeleton from a bundled template.
2. Edit the Reference Skeleton as needed.
3. Configure the Reference Mapping.
4. Run Generate Rig.
5. If the Reference Skeleton changes later, run Rebuild Rig.

The Reference Skeleton is treated as the source of truth. Kai-generated rig data, such as controllers, helper bones, constraints, and control collections, can be reset and generated again.

## Rebuild Rig

Rebuild Rig regenerates a previously generated rig from the current Reference Skeleton.

Internally, Rebuild Rig runs:

1. Reset Generated Rig
2. Generate Rig

Reset Generated Rig removes Kai-generated rig data while keeping the Reference Skeleton and saved `kai_*` Mapping data. This allows the user to adjust Reference Skeleton bone positions, rolls, parenting, and connection settings, then rebuild the generated controls without recreating the entire setup from scratch.

Rebuild Rig is intended for humanoid workflows first. Future template types, such as quadrupeds or additional appendages, can build on the same reset-and-regenerate design.

## Safety Validation

Before Rebuild Rig resets the generated rig, Kai validates the saved Mapping data.

Rebuild checks:

- Required Mapping bones: `Hip`, `Chest`, and `Head`
- Optional Mapping bones: `Spine`, `Neck`, and `Shoulder`
- Reference Skeleton hierarchy changes
- Reference Skeleton `connected` state changes

If a required Mapping bone is missing, Rebuild Rig stops before Reset Generated Rig runs. This protects the existing generated rig from being removed when the saved Mapping is no longer valid.

If optional Mapping bones are missing, Kai shows a warning and ignores those missing optional entries for the rebuild.

If hierarchy or `connected` changes are detected, Kai shows a warning and continues. These warnings are intended to help the user notice structural Reference Skeleton edits before reviewing the rebuilt rig.

## Mapping Notes

Current behavior:

- Rebuild Rig uses the saved `kai_*` Mapping data.
- Mapping is not automatically rediscovered or updated.
- Newly added Spine or Neck bones are not automatically adopted by Rebuild Rig.
- To use newly added bones, the user must explicitly update the Mapping through Generate Rig or a future dedicated Mapping workflow.
- Automatic Mapping refresh and candidate confirmation UI are planned as a separate future stage.

This keeps Rebuild Rig predictable and avoids accidentally treating user-created or helper bones as part of the Reference Skeleton Mapping.

## Credits

Original Author: BeyondDev (Tyler Walker)

Kai Maintainer: Gonsaku

## Roadmap

Completed:

- Variable Spine Support
- Variable Neck Support
- Reference Skeleton Mapping
- Optional Shoulder Support
- Reference Bone Generator
- Reference Template System
- Humanoid Basic Template
- Humanoid Fingers Template
- Rebuild Rig
- Reset Generated Rig
- Rebuild Safety Validation

Planned:

- Refresh Mapping from Skeleton with candidate confirmation UI
- Quadruped Support
- Eye Controller
- Additional UI Improvements

## Changelog

### v0.6.0 Preview

Feature release for Retarget Bake rotation output and Kai default controller rotation modes.

- Added Retarget Bake Rotation Output options: `Quaternion`, `Euler`, and `Target Original`
- Set `Quaternion` as the default retarget rotation output
- Added Quaternion bake output using `rotation_quaternion` F-curves without generating `rotation_euler` F-curves
- Added quaternion sign compatibility correction to avoid curve jumps between frames
- Improved `Target Original` so it preserves each target controller's pre-bake rotation mode, including mixed Euler and Quaternion rigs
- Updated Kai default control rig rotation modes: `Ctrl_Master` uses XYZ Euler, while other `mixamo_ctrl` controllers use Quaternion
- Preserved existing controller rotation modes during Refresh, Reconnect, and Retarget setup so user changes are not reset to XYZ Euler

### v0.5.1 Preview

Bug fix release for the v0.5.0 Preview retarget regression.

- Fixed the Hips / Spine / Chest retarget regression
- Improved prefix-safe Mapping name resolution
- Unified bone name resolution between Rebuild and Retarget
- Improved Hip Mapping support so mapped hips such as `Pelvis` can receive Copy Location constraints
- Added retarget debug logging for missing source and target bones

### v0.5.0 Preview

- Added Rebuild Rig
- Added Reset Generated Rig
- Added generated bone and constraint tracking for safe rig reset
- Added Rebuild safety validation for required and optional Mapping data
- Added hierarchy and connected-state change warnings before Rebuild

### v0.4.0 Preview

- Reference Bone Generator
- Humanoid Basic Template
- Humanoid Fingers Template
- Template Selection UI
- Reference Template Validation Tools

### v0.3.0 Preview

- Optional Shoulder Support
- Support for shoulder-less humanoid skeletons
- Updated Reference Mapping workflow
- Additional Rig Generation improvements
