#!/usr/bin/env python3
"""
Stella CLI - Command-line interface for building .stella world files.

Usage:
    stella build-floorplan --input plan.png --output world.stella
    stella build-video --input scan.mp4 --output world.stella
    stella info world.stella
    stella extract world.stella --output ./extracted/
    stella verify world.stella
"""

import argparse
import sys
import json
from pathlib import Path


def cmd_build_floorplan(args):
    """Build .stella from floorplan image."""
    from stella.pipeline_floorplan import build_floorplan
    
    try:
        result = build_floorplan(
            input_image=args.input,
            output_stella=args.output,
            wall_height=args.wall_height,
            voxel_size=args.voxel,
            pixels_per_meter=args.pixels_per_meter,
            title=args.title or Path(args.input).stem,
            invert=args.invert,
            threshold=args.threshold,
        )
        print(f"Success: {result}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_build_video(args):
    """Build .stella from video using MASt3R-SLAM."""
    from stella.pipeline_video import build_video
    
    try:
        result = build_video(
            input_video=args.input,
            output_stella=args.output,
            voxel_size=args.voxel,
            max_frames=args.max_frames,
            title=args.title or Path(args.input).stem,
            mast3r_path=args.mast3r_path,
            use_existing_ply=args.use_ply,
        )
        print(f"Success: {result}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_info(args):
    """Show information about a .stella file."""
    from stella.package import get_stella_info
    
    try:
        info = get_stella_info(args.stella_file)
        
        manifest = info["manifest"]
        print(f"Format: {manifest['format']} v{manifest['version']}")
        print(f"Created: {manifest['created_utc']}")
        
        if "world" in manifest and manifest["world"]:
            print(f"Title: {manifest['world'].get('title', 'Untitled')}")
            tags = manifest['world'].get('tags', [])
            if tags:
                print(f"Tags: {', '.join(tags)}")
        
        print(f"\nLevels: {len(manifest['levels'])}")
        for level in manifest["levels"]:
            name = level.get("name", level["id"])
            print(f"  - {name} ({level['path']})")
        
        print(f"\nFiles: {len(info['files'])}")
        for f in info["files"]:
            size_kb = f["uncompressed_size"] / 1024
            print(f"  {f['path']}: {size_kb:.1f} KB")
        
        total_mb = info["total_uncompressed_size"] / (1024 * 1024)
        archive_mb = info["archive_size"] / (1024 * 1024)
        print(f"\nTotal: {total_mb:.2f} MB (compressed: {archive_mb:.2f} MB)")
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_extract(args):
    """Extract contents of a .stella file."""
    from stella.package import unpack_stella
    
    try:
        output_dir = Path(args.output or f"{Path(args.stella_file).stem}_extracted")
        
        manifest, zf = unpack_stella(args.stella_file, extract_to=output_dir)
        zf.close()
        
        print(f"Extracted to: {output_dir}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_verify(args):
    """Verify checksums in a .stella file."""
    from stella.package import verify_stella_checksums
    
    try:
        valid, errors = verify_stella_checksums(args.stella_file)
        
        if valid:
            print("✓ All checksums valid")
            return 0
        else:
            print("✗ Verification failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_preview_floorplan(args):
    """Preview wall detection on a floorplan image."""
    from stella.pipeline_floorplan import preview_floorplan
    
    try:
        import cv2
        
        preview = preview_floorplan(
            args.input,
            threshold=args.threshold,
            invert=args.invert,
        )
        
        if args.output:
            cv2.imwrite(args.output, preview)
            print(f"Preview saved to: {args.output}")
        else:
            cv2.imshow("Floorplan Preview (walls in red)", preview)
            print("Press any key to close...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        
        return 0
    except ImportError:
        print("Error: opencv-python required for preview", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Stella CLI - Build and manage .stella world files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  stella build-floorplan --input plan.png --output world.stella
  stella build-video --input scan.mp4 --output world.stella
  stella info world.stella
  stella extract world.stella --output ./extracted/
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # build-floorplan
    fp_parser = subparsers.add_parser(
        "build-floorplan",
        help="Build .stella from a floorplan image",
    )
    fp_parser.add_argument("--input", "-i", required=True, help="Input floorplan image (PNG/JPG)")
    fp_parser.add_argument("--output", "-o", required=True, help="Output .stella file")
    fp_parser.add_argument("--wall-height", type=float, default=2.7, help="Wall height in meters (default: 2.7)")
    fp_parser.add_argument("--voxel", type=float, default=0.1, help="Voxel size in meters (default: 0.1)")
    fp_parser.add_argument("--pixels-per-meter", type=float, default=50, help="Image scale (default: 50)")
    fp_parser.add_argument("--title", help="World title")
    fp_parser.add_argument("--invert", action="store_true", help="Invert wall detection (dark = empty)")
    fp_parser.add_argument("--threshold", type=int, default=128, help="Grayscale threshold (default: 128)")
    fp_parser.set_defaults(func=cmd_build_floorplan)
    
    # build-video
    vid_parser = subparsers.add_parser(
        "build-video",
        help="Build .stella from video using MASt3R-SLAM",
    )
    vid_parser.add_argument("--input", "-i", required=True, help="Input video file (MP4)")
    vid_parser.add_argument("--output", "-o", required=True, help="Output .stella file")
    vid_parser.add_argument("--voxel", type=float, default=0.1, help="Voxel size in meters (default: 0.1)")
    vid_parser.add_argument("--max-frames", type=int, default=1500, help="Max frames to process (default: 1500)")
    vid_parser.add_argument("--title", help="World title")
    vid_parser.add_argument("--mast3r-path", help="Path to MASt3R-SLAM main.py")
    vid_parser.add_argument("--use-ply", help="Skip SLAM and use existing PLY file")
    vid_parser.set_defaults(func=cmd_build_video)
    
    # info
    info_parser = subparsers.add_parser(
        "info",
        help="Show information about a .stella file",
    )
    info_parser.add_argument("stella_file", help="Path to .stella file")
    info_parser.set_defaults(func=cmd_info)
    
    # extract
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract contents of a .stella file",
    )
    extract_parser.add_argument("stella_file", help="Path to .stella file")
    extract_parser.add_argument("--output", "-o", help="Output directory")
    extract_parser.set_defaults(func=cmd_extract)
    
    # verify
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify checksums in a .stella file",
    )
    verify_parser.add_argument("stella_file", help="Path to .stella file")
    verify_parser.set_defaults(func=cmd_verify)
    
    # preview-floorplan
    preview_parser = subparsers.add_parser(
        "preview-floorplan",
        help="Preview wall detection on a floorplan",
    )
    preview_parser.add_argument("--input", "-i", required=True, help="Input floorplan image")
    preview_parser.add_argument("--output", "-o", help="Save preview to file")
    preview_parser.add_argument("--threshold", type=int, default=128, help="Grayscale threshold")
    preview_parser.add_argument("--invert", action="store_true", help="Invert wall detection")
    preview_parser.set_defaults(func=cmd_preview_floorplan)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
