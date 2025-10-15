#!/usr/bin/env python3
"""
code2llm.py - A script to prepare code files for language model input.

This script collects code files from specified paths, respecting gitignore rules,
and formats them into a single output suitable for sending to a language model.
"""

import os
import argparse
import glob
import fnmatch
import re
from pathlib import Path


def find_git_root(path):
    """Find the git repository root for a given path."""
    current = Path(os.path.abspath(path))
    
    # If the path is a file, start from its directory
    if os.path.isfile(current):
        current = current.parent
        
    while current != current.parent:
        if (current / ".git").is_dir():
            return current
        current = current.parent
    
    return None


def parse_gitignore(gitignore_path):
    """Parse a .gitignore file and return a list of patterns."""
    if not os.path.exists(gitignore_path):
        return []
    
    patterns = []
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            patterns.append(line)
    
    return patterns


def should_ignore(path, base_path, gitignore_patterns):
    """Check if a path should be ignored based on gitignore patterns."""
    # Convert path to relative path from base_path
    rel_path = os.path.relpath(path, base_path)
    
    for pattern in gitignore_patterns:
        # Handle negation patterns
        if pattern.startswith('!'):
            continue  # For simplicity, we're not handling negation patterns
        
        # Handle directory-only patterns
        if pattern.endswith('/'):
            if os.path.isdir(path) and fnmatch.fnmatch(rel_path + '/', pattern):
                return True
        # Handle normal patterns
        elif fnmatch.fnmatch(rel_path, pattern):
            return True
        # Handle patterns that match at any level
        elif '/' not in pattern and fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    
    return False


def should_exclude(path, base_path, exclude_patterns):
    """Check if a path should be excluded based on user-provided patterns."""
    rel_path = os.path.relpath(path, base_path)
    
    for pattern in exclude_patterns:
        # Convert glob patterns to regex
        if '*' in pattern:
            regex_pattern = fnmatch.translate(pattern)
            if re.match(regex_pattern, rel_path) or re.match(regex_pattern, os.path.basename(path)):
                return True
        # Direct path prefix check
        elif rel_path.startswith(pattern):
            return True
    
    return False


def collect_files(input_paths, exclude_patterns):
    """Collect files from input paths respecting gitignore and exclusion rules."""
    all_files = []
    
    for input_path in input_paths:
        input_path = os.path.abspath(input_path)
        
        # Find git root
        git_root = find_git_root(input_path)
        if git_root is None:
            base_path = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
            gitignore_patterns = []
        else:
            base_path = git_root
            gitignore_patterns = parse_gitignore(os.path.join(git_root, '.gitignore'))
        
        # If input is a file, just add it if it's not excluded
        if os.path.isfile(input_path):
            if (not should_ignore(input_path, base_path, gitignore_patterns) and 
                not should_exclude(input_path, base_path, exclude_patterns)):
                all_files.append((input_path, base_path))
        else:
            # Walk through the directory tree
            for root, dirs, files in os.walk(input_path):
                # Filter out directories that should be ignored or excluded
                dirs_to_remove = []
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    if (should_ignore(dir_path, base_path, gitignore_patterns) or 
                        should_exclude(dir_path, base_path, exclude_patterns)):
                        dirs_to_remove.append(d)
                
                # Remove directories in-place to prevent os.walk from traversing them
                for d in dirs_to_remove:
                    dirs.remove(d)
                
                # Add files that should not be ignored or excluded
                for file in files:
                    file_path = os.path.join(root, file)
                    if (not should_ignore(file_path, base_path, gitignore_patterns) and 
                        not should_exclude(file_path, base_path, exclude_patterns)):
                        all_files.append((file_path, base_path))
    
    return all_files


def build_file_tree(files):
    """Build a tree structure of the files for display."""
    tree = {}
    
    for file_path, base_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        parts = rel_path.split(os.sep)
        
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # Leaf node (file)
                current[part] = None
            else:  # Directory
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    return tree


def print_tree(tree, prefix="", is_last=True, output_lines=None):
    """Print the tree structure using ASCII characters."""
    if output_lines is None:
        output_lines = []
    
    items = list(tree.items())
    
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        
        # Print current node with ASCII characters
        if prefix:
            output_lines.append(f"{prefix}{'`-- ' if is_last_item else '|-- '}{name}")
        else:
            output_lines.append(name)
        
        # Print children
        if subtree is not None:  # It's a directory
            extension = "    " if is_last_item else "|   "
            print_tree(subtree, prefix + extension, is_last_item, output_lines)
    
    return output_lines


def format_output(files):
    """Format collected files for language model input."""
    system_prompt = """Act as an experienced senior software engineer. Generate clean, well-structured, production-ready code that follows current best practices and avoids deprecated APIs.

Requirements:
- Code must be complete and ready to copy-paste without modifications
- Use current, non-deprecated APIs and libraries
- Follow proper naming conventions and code organization
- Include error handling where appropriate
- Ensure code is performant and follows security best practices

Comments policy:
- Good code comments itself
- Comment code, not your actions
- Since I use git for change tracking, never add placeholder comments marking changes that has been made
- Only add comments that explain complex logic, algorithms, or non-obvious decisions
- Avoid obvious comments that simply restate what the code does
- Remember: good code should be self-documenting through clear naming and structure

Changes policy:
- Apply only and only requested changes and nothing else
- Avoid removing existing comments or reformatting non-changed parts of the code
- Follow the same coding and documentation style as it is in the modified file

If the requirements are unclear, ask for clarification rather than making assumptions."""
    
    output = system_prompt + "\n\n"
    
    # Build and add file tree
    file_tree = build_file_tree(files)
    tree_lines = print_tree(file_tree)
    output += "Files listed in this prompt:\n"
    for line in tree_lines:
        output += line + "\n"
    output += "\n"
    
    # Add file contents
    for file_path, base_path in files:
        rel_path = os.path.relpath(file_path, base_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            output += f"{rel_path}:\n```\n{content}\n```\n\n"
        except UnicodeDecodeError:
            # Skip binary files
            continue
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return output


def main():
    """Main function to run the script."""
    parser = argparse.ArgumentParser(description='Prepare code files for language model input.')
    parser.add_argument('-i', '--input', action='append', default=None, 
                        help='Input paths (files or directories). Can be specified multiple times. Default is current directory.')
    parser.add_argument('-e', '--exclude', action='append', default=[],
                        help='Patterns to exclude. Can be specified multiple times.')
    
    args = parser.parse_args()
    
    # If no input is provided, use current directory
    if args.input is None:
        args.input = ['.']
    
    # Collect files
    files = collect_files(args.input, args.exclude)
    
    # Format and print output
    output = format_output(files)
    
    # Print output with utf-8 encoding handling
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.buffer.write(output.encode('utf-8'))
    else:
        print(output)


if __name__ == "__main__":

    main()

