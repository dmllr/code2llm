# `code2llm`

A smart script to package your entire codebase into a single, context-rich prompt for Large Language Models (LLMs).

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/release/python-360/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Why `code2llm`?](#why-code2llm)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Specifying Inputs](#specifying-inputs)
  - [Excluding Files and Directories](#excluding-files-and-directories)
  - [Piping to Clipboard](#piping-to-clipboard)
- [Example Output](#example-output)
- [How It Works](#how-it-works)
- [Contributing](#contributing)
- [License](#license)

## Why `code2llm`?

When working with LLMs like GPT-4 or Claude, providing sufficient context is key to getting high-quality responses. Simply pasting a single file is often not enough. You need to show the model the project structure and related files.

`code2llm` automates this process by:
1.  Intelligently selecting relevant project files.
2.  Ignoring unnecessary files like build artifacts, dependencies, and secrets (by respecting `.gitignore`).
3.  Generating a clean file tree so the LLM understands the project architecture.
4.  Bundling everything into a single, perfectly formatted block of text, ready to be pasted into your chat.

Stop wasting time manually copying and pasting files and give the LLM the context it needs to be a true coding assistant.

## Features

-   **Git-Aware:** Automatically finds the git root and respects `.gitignore` rules to exclude irrelevant files.
-   **Custom Exclusions:** Add your own glob patterns (e.g., `*.log`, `dist/*`) to exclude specific files or directories.
-   **Directory Tree:** Generates a clear file tree overview so the LLM understands your project's structure.
-   **Single Output:** Concatenates all relevant code into a single block, ready to be copied.
-   **Optimized System Prompt:** Includes a built-in system prompt to guide the LLM towards generating high-quality, production-ready code.
-   **Flexible Input:** Specify multiple files or directories as input.
-   **Handles Binary Files:** Gracefully skips binary files that cannot be read as text.

## Installation

`code2llm` is a single-file Python script with no external dependencies. All you need is Python 3.

1.  **Download the script:**
    Save the `code2llm.py` file to your computer.

2.  **Make it executable (Optional, for Unix-like systems):**
    ```bash
    chmod +x code2llm.py
    ```

3.  **Add it to your PATH (Optional, recommended for easy access):**
    Move the `code2llm.py` script to a directory in your system's `PATH` (e.g., `/usr/local/bin` on macOS/Linux or a custom scripts folder on Windows). This allows you to run `code2llm.py` from any directory.

## Usage

The script is run from the command line. The output is printed to standard output, making it easy to pipe to other commands like a clipboard utility.

### Basic Usage

To process the current directory, simply run the script. It will automatically detect the git repository and use the corresponding `.gitignore`.

```bash
# If in your PATH
code2llm.py

# Or if running from its location
./code2llm.py
python3 code2llm.py
```

### Specifying Inputs

You can specify multiple files or directories using the `-i` or `--input` flag.

```bash
# Process a specific source directory and a single test file
code2llm.py -i src/ -i tests/test_main.py
```

### Excluding Files and Directories

Use the `-e` or `--exclude` flag to add custom exclusion patterns. This is useful for temporarily ignoring files that are not in your `.gitignore`. The patterns support wildcards (`*`).

```bash
# Process the current directory but exclude all .md files and the config folder
code2llm.py -e "*.md" -e "config/*"
```

### Piping to Clipboard

The most powerful way to use `code2llm` is to pipe its output directly to your clipboard.

**macOS:**
```bash
code2llm.py | pbcopy
```

**Linux (requires `xclip`):**
```bash
code2llm.py | xclip -selection clipboard
```

**Windows (Command Prompt):**
```bash
python code2llm.py | clip
```

Now you can just paste (Ctrl+V or Cmd+V) the entire project context into your LLM chat window!

## Example Output

Given a project structure like this:
```
my-project/
├── .gitignore   (contains 'dist/' and '*.log')
├── main.py
├── utils/
│   └── helpers.py
└── dist/
    └── app.bin
```

Running `code2llm.py` from within `my-project/` would produce the following output:

```
Act as an experienced senior software engineer. Generate clean, well-structured, production-ready code that follows current best practices and avoids deprecated APIs.

Requirements:
- Code must be complete and ready to copy-paste without modifications
- Use current, non-deprecated APIs and libraries
- Follow proper naming conventions and code organization
- Include error handling where appropriate
- Ensure code is performant and follows security best practices

Comments policy:
- Since I use git for change tracking, never add placeholder comments like "keep this", "modify this", or "New: [feature]"
- Only add comments that explain complex business logic, algorithms, or non-obvious technical decisions
- Avoid obvious comments that simply restate what the code does
- Remember: good code should be self-documenting through clear naming and structure

If the requirements are unclear, ask for clarification rather than making assumptions.

Files listed in this prompt:
main.py
utils/
`-- helpers.py

main.py:
```
# Contents of main.py would be here...
print("Hello from main.py")
```

utils/helpers.py:
```
# Contents of helpers.py would be here...
def helper_function():
    return "This is a helper."
```

```
> *Note: The `dist/` directory and any `.log` files would be automatically excluded.*

## How It Works

1.  **Input Parsing:** The script parses command-line arguments for input paths and exclusion patterns.
2.  **Git Root Discovery:** For each input path, it walks up the directory tree to find the `.git` directory. This serves as the project root.
3.  **`.gitignore` Parsing:** It reads and parses the `.gitignore` file from the root.
4.  **File Collection:** The script walks through the specified input directories. For each file and directory, it checks against both the `.gitignore` patterns and the custom exclusion patterns.
5.  **Tree Generation:** It builds an ASCII tree structure from the list of collected files to provide a visual map of the project.
6.  **Formatting:** Finally, it assembles the output: the system prompt, the file tree, and the content of each file, formatted neatly with Markdown code blocks.

## Contributing

Contributions are welcome! If you have an idea for an improvement or find a bug, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
