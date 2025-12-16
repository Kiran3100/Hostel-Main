import os
from pathlib import Path
from typing import List, Tuple

# Configuration
ROOT_FOLDER = r"D:\Last Github Push\Last\Hostel-Main\app"  # Change this to your actual path
TARGET_FILENAME = "all_folders_files_content.txt"

def delete_target_files(root_folder: str, dry_run: bool = False) -> Tuple[int, int]:
    """
    Delete all instances of TARGET_FILENAME in the folder tree.
    
    Args:
        root_folder: The root directory to search from
        dry_run: If True, only simulate deletion without actually deleting files
    
    Returns:
        Tuple of (successful_deletions, failed_deletions)
    """
    # Validate root folder exists
    root_path = Path(root_folder)
    if not root_path.exists():
        print(f"Error: Root folder does not exist: {root_folder}")
        return 0, 0
    
    if not root_path.is_dir():
        print(f"Error: Path is not a directory: {root_folder}")
        return 0, 0
    
    success_count = 0
    fail_count = 0
    files_found: List[Path] = []
    
    # Find all target files first
    print(f"Scanning for '{TARGET_FILENAME}' in: {root_folder}")
    print("-" * 60)
    
    try:
        for current_root, dirs, files in os.walk(root_folder):
            # Skip hidden directories and system folders
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            if TARGET_FILENAME in files:
                file_path = Path(current_root) / TARGET_FILENAME
                files_found.append(file_path)
    except PermissionError as e:
        print(f"Permission denied while scanning: {e}")
    
    # Report findings
    if not files_found:
        print("No files found to delete.")
        return 0, 0
    
    print(f"Found {len(files_found)} file(s) to delete:\n")
    for file_path in files_found:
        print(f"  • {file_path}")
    
    print("\n" + "-" * 60)
    
    # Delete files
    if dry_run:
        print("\n[DRY RUN MODE] No files were actually deleted.")
        return len(files_found), 0
    
    print("\nDeleting files...\n")
    
    for file_path in files_found:
        try:
            file_path.unlink()
            print(f"✓ Deleted: {file_path}")
            success_count += 1
        except PermissionError:
            print(f"✗ Permission denied: {file_path}")
            fail_count += 1
        except FileNotFoundError:
            print(f"✗ File not found (may have been moved): {file_path}")
            fail_count += 1
        except OSError as e:
            print(f"✗ Failed to delete {file_path}: {e}")
            fail_count += 1
    
    return success_count, fail_count

def main():
    """Main execution function with user confirmation."""
    print("=" * 60)
    print("FILE DELETION UTILITY")
    print("=" * 60)
    print(f"Target file: {TARGET_FILENAME}")
    print(f"Root folder: {ROOT_FOLDER}")
    print("=" * 60)
    
    # First, do a dry run to show what would be deleted
    print("\nPerforming dry run...\n")
    success, fail = delete_target_files(ROOT_FOLDER, dry_run=True)
    
    if success == 0:
        return
    
    # Ask for confirmation
    print("\n" + "=" * 60)
    response = input(f"\nProceed with deleting {success} file(s)? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        print("\nProceeding with deletion...")
        print("=" * 60 + "\n")
        success, fail = delete_target_files(ROOT_FOLDER, dry_run=False)
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Successfully deleted: {success}")
        print(f"Failed to delete: {fail}")
        print(f"Total processed: {success + fail}")
        print("=" * 60)
    else:
        print("\nOperation cancelled by user.")

if __name__ == "__main__":
    main()