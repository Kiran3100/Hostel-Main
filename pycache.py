import os
import shutil
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
 
@dataclass
class ScanStats:
    """Statistics for the scanning operation."""
    total_pycache: int = 0
    deleted: int = 0
    failed: int = 0
    skipped: int = 0
    total_size_freed: int = 0
 
def get_directory_size(path: Path) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total
 
def format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"
 
def delete_all_pycache(
    root_path: Path,
    dry_run: bool = False,
    verbose: bool = True
) -> ScanStats:
    """
    Recursively traverse root_path and delete all __pycache__ directories.
   
    Args:
        root_path: Root directory to scan
        dry_run: If True, only simulate deletion
        verbose: If True, print detailed information
   
    Returns:
        ScanStats object with operation statistics
    """
    stats = ScanStats()
    pycache_dirs = []
   
    # First pass: find all __pycache__ directories
    if verbose:
        print(f"\n{'=' * 70}")
        print("SCANNING FOR __pycache__ DIRECTORIES")
        print(f"{'=' * 70}")
        print(f"Root: {root_path}")
        print(f"{'=' * 70}\n")
   
    for current_root, dirnames, _ in os.walk(root_path):
        # Skip hidden directories and common exclusions
        dirnames[:] = [d for d in dirnames if not d.startswith('.')
                       and d not in {'node_modules', 'venv', '.venv', '.git'}]
       
        for dirname in list(dirnames):
            if dirname == "__pycache__":
                pycache_path = Path(current_root) / dirname
                stats.total_pycache += 1
                pycache_dirs.append(pycache_path)
               
                if verbose:
                    size = get_directory_size(pycache_path)
                    print(f"Found: {pycache_path} ({format_size(size)})")
   
    # Report findings
    if verbose:
        print(f"\n{'=' * 70}")
        print("SCAN RESULTS")
        print(f"{'=' * 70}")
        print(f"Total __pycache__ directories found: {stats.total_pycache}")
        print(f"Skipped (permissions/errors): {stats.skipped}")
        print(f"{'=' * 70}\n")
   
    if not pycache_dirs:
        if verbose:
            print("✓ No __pycache__ directories found.")
        return stats
   
    # Second pass: delete directories
    if dry_run:
        if verbose:
            print("[DRY RUN MODE] The following would be deleted:\n")
            for pycache_path in pycache_dirs:
                size = get_directory_size(pycache_path)
                stats.total_size_freed += size
        stats.deleted = len(pycache_dirs)
        if verbose:
            print(f"\nTotal space that would be freed: {format_size(stats.total_size_freed)}")
        return stats
   
    if verbose:
        print(f"{'=' * 70}")
        print("DELETING DIRECTORIES")
        print(f"{'=' * 70}\n")
   
    for pycache_path in pycache_dirs:
        try:
            size = get_directory_size(pycache_path)
            shutil.rmtree(pycache_path)
            stats.deleted += 1
            stats.total_size_freed += size
           
            if verbose:
                print(f"✓ Deleted: {pycache_path} ({format_size(size)})")
               
        except PermissionError:
            stats.failed += 1
            if verbose:
                print(f"✗ Permission denied: {pycache_path}")
        except FileNotFoundError:
            # Directory may have been removed concurrently
            stats.skipped += 1
            if verbose:
                print(f"⚠ Not found (may have been removed): {pycache_path}")
        except OSError as exc:
            stats.failed += 1
            if verbose:
                print(f"✗ Error deleting {pycache_path}: {exc}")
   
    return stats
 
def main() -> None:
    """Main execution function with user interaction."""
    # 🔧 CONFIGURATION
    root_directory = Path(r"C:\Hostel-Main\app").resolve()  # Change this to your target directory
   
    print("=" * 70)
    print("__pycache__ DIRECTORY CLEANER")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
   
    # Validate root directory
    if not root_directory.exists():
        print(f"\n✗ Error: Root path does not exist: {root_directory}")
        return
   
    if not root_directory.is_dir():
        print(f"\n✗ Error: Path is not a directory: {root_directory}")
        return
   
    # Dry run first
    print("\nPerforming dry run to identify targets...\n")
    stats = delete_all_pycache(
        root_directory,
        dry_run=True,
        verbose=True
    )
   
    if stats.total_pycache == 0:
        print("\n✓ No __pycache__ directories found. Exiting.")
        return
   
    # Ask for confirmation
    print("\n" + "=" * 70)
    response = input(
        f"\nProceed with deleting {stats.total_pycache} __pycache__ "
        f"director{'y' if stats.total_pycache == 1 else 'ies'}? (yes/no): "
    ).strip().lower()
   
    if response in ['yes', 'y']:
        print("\nProceeding with deletion...\n")
        stats = delete_all_pycache(
            root_directory,
            dry_run=False,
            verbose=True
        )
       
        # Final summary
        print("\n" + "=" * 70)
        print("OPERATION SUMMARY")
        print("=" * 70)
        print(f"Total __pycache__ directories found: {stats.total_pycache}")
        print(f"Successfully deleted: {stats.deleted}")
        print(f"Failed to delete: {stats.failed}")
        print(f"Skipped: {stats.skipped}")
        print(f"Total space freed: {format_size(stats.total_size_freed)}")
        print("=" * 70)
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
    else:
        print("\n✓ Operation cancelled by user.")
 
if __name__ == "__main__":
    main()
 