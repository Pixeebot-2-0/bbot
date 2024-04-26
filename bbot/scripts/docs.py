#!/usr/bin/env python3

import os
import re
import yaml
from pathlib import Path

from bbot.scanner import Preset

DEFAULT_PRESET = Preset()

os.environ["BBOT_TABLE_FORMAT"] = "github"


# Make a regex pattern which will match any group of non-space characters that include a blacklisted character
blacklist_chars = ["<", ">"]
blacklist_re = re.compile(r"\|([^|]*[" + re.escape("".join(blacklist_chars)) + r"][^|]*)\|")

bbot_code_dir = Path(__file__).parent.parent.parent


def homedir_collapseuser(f):
    f = Path(f)
    home_dir = Path.home()
    if f.is_relative_to(home_dir):
        return Path("~") / f.relative_to(home_dir)
    return f


def enclose_tags(text):
    # Use re.sub() to replace matched words with the same words enclosed in backticks
    result = blacklist_re.sub(r"|`\1`|", text)
    return result


def find_replace_markdown(content, keyword, replace):
    begin_re = re.compile(r"<!--\s*" + keyword + r"\s*-->", re.I)
    end_re = re.compile(r"<!--\s*END\s+" + keyword + r"\s*-->", re.I)

    begin_match = begin_re.search(content)
    end_match = end_re.search(content)

    new_content = str(content)
    if begin_match and end_match:
        start_index = begin_match.span()[-1] + 1
        end_index = end_match.span()[0] - 1
        new_content = new_content[:start_index] + enclose_tags(replace) + new_content[end_index:]
    return new_content


def find_replace_file(file, keyword, replace):
    with open(file) as f:
        content = f.read()
        new_content = find_replace_markdown(content, keyword, replace)
    if new_content != content:
        if not "BBOT_TESTING" in os.environ:
            with open(file, "w") as f:
                f.write(new_content)


def update_docs():
    md_files = [p for p in bbot_code_dir.glob("**/*.md") if p.is_file()]

    def update_md_files(keyword, s):
        for file in md_files:
            find_replace_file(file, keyword, s)

    def update_individual_module_options():
        regex = re.compile("BBOT MODULE OPTIONS ([A-Z_]+)")
        for file in md_files:
            with open(file) as f:
                content = f.read()
            for match in regex.finditer(content):
                module_name = match.groups()[0].lower()
                bbot_module_options_table = DEFAULT_PRESET.module_loader.modules_options_table(modules=[module_name])
                find_replace_file(file, f"BBOT MODULE OPTIONS {module_name.upper()}", bbot_module_options_table)

    # Example commands
    bbot_example_commands = []
    for title, description, command in DEFAULT_PRESET.args.scan_examples:
        example = ""
        example += f"**{title}:**\n\n"
        # example += f"{description}\n"
        example += f"```bash\n# {description}\n{command}\n```"
        bbot_example_commands.append(example)
    bbot_example_commands = "\n\n".join(bbot_example_commands)
    assert len(bbot_example_commands.splitlines()) > 10
    update_md_files("BBOT EXAMPLE COMMANDS", bbot_example_commands)

    # Help output
    bbot_help_output = DEFAULT_PRESET.args.parser.format_help().replace("docs.py", "bbot")
    bbot_help_output = f"```text\n{bbot_help_output}\n```"
    assert len(bbot_help_output.splitlines()) > 50
    update_md_files("BBOT HELP OUTPUT", bbot_help_output)

    # BBOT events
    bbot_event_table = DEFAULT_PRESET.module_loader.events_table()
    assert len(bbot_event_table.splitlines()) > 10
    update_md_files("BBOT EVENTS", bbot_event_table)

    # BBOT modules
    bbot_module_table = DEFAULT_PRESET.module_loader.modules_table()
    assert len(bbot_module_table.splitlines()) > 50
    update_md_files("BBOT MODULES", bbot_module_table)

    # BBOT output modules
    bbot_output_module_table = DEFAULT_PRESET.module_loader.modules_table(mod_type="output")
    assert len(bbot_output_module_table.splitlines()) > 10
    update_md_files("BBOT OUTPUT MODULES", bbot_output_module_table)

    # BBOT module options
    bbot_module_options_table = DEFAULT_PRESET.module_loader.modules_options_table()
    assert len(bbot_module_options_table.splitlines()) > 100
    update_md_files("BBOT MODULE OPTIONS", bbot_module_options_table)
    update_individual_module_options()

    # BBOT module flags
    bbot_module_flags_table = DEFAULT_PRESET.module_loader.flags_table()
    assert len(bbot_module_flags_table.splitlines()) > 10
    update_md_files("BBOT MODULE FLAGS", bbot_module_flags_table)

    # BBOT presets
    bbot_presets_table = DEFAULT_PRESET.presets_table(include_modules=True)
    assert len(bbot_presets_table.splitlines()) > 5
    update_md_files("BBOT PRESETS", bbot_presets_table)

    # BBOT subdomain enum preset
    for yaml_file, (loaded_preset, category, preset_path, original_filename) in DEFAULT_PRESET.all_presets.items():
        if loaded_preset.name == "subdomain-enum":
            subdomain_enum_preset = f"""```yaml title="{yaml_file.name}"
{loaded_preset._yaml_str}
```"""
            update_md_files("BBOT SUBDOMAIN ENUM PRESET", subdomain_enum_preset)
            break

    content = []
    for yaml_file, (loaded_preset, category, preset_path, original_filename) in DEFAULT_PRESET.all_presets.items():
        yaml_str = loaded_preset._yaml_str
        indent = " " * 4
        yaml_str = f"\n{indent}".join(yaml_str.splitlines())
        filename = homedir_collapseuser(yaml_file)

        num_modules = len(loaded_preset.scan_modules)
        modules = ", ".join(sorted([f"`{m}`" for m in loaded_preset.scan_modules]))
        category = f"Category: {category}" if category else ""

        content.append(
            f"""## **{loaded_preset.name}**

{loaded_preset.description}

??? note "`{filename.name}`"
    ```yaml title="{filename}"
    {yaml_str}
    ```

{category}

Modules: [{num_modules:,}]("{modules}")"""
        )
    assert len(content) > 5
    update_md_files("BBOT PRESET YAML", "\n\n".join(content))

    # Default config
    default_config_file = bbot_code_dir / "bbot" / "defaults.yml"
    with open(default_config_file) as f:
        default_config_yml = f.read()
    default_config_yml = f'```yaml title="defaults.yml"\n{default_config_yml}\n```'
    assert len(default_config_yml.splitlines()) > 20
    update_md_files("BBOT DEFAULT CONFIG", default_config_yml)

    # Table of Contents
    base_url = "https://www.blacklanternsecurity.com/bbot"

    def format_section(section_title, section_path):
        path = section_path.split("index.md")[0]
        path = path.split(".md")[0]
        return f"- [{section_title}]({base_url}/{path})\n"

    bbot_docs_toc = ""

    def update_toc(section, level=0):
        nonlocal bbot_docs_toc
        indent = " " * 4 * level
        if isinstance(section, dict):
            for section_title, subsections in section.items():
                if isinstance(subsections, str):
                    bbot_docs_toc += f"{indent}{format_section(section_title, subsections)}"
                else:
                    bbot_docs_toc += f"{indent}- **{section_title}**\n"
                    for subsection in subsections:
                        update_toc(subsection, level=level + 1)

    mkdocs_yml_file = bbot_code_dir / "mkdocs.yml"
    yaml.SafeLoader.add_constructor(
        "tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format", lambda x, y: {}
    )

    with open(mkdocs_yml_file, "r") as f:
        mkdocs_yaml = yaml.safe_load(f)
        nav = mkdocs_yaml["nav"]
        for section in nav:
            update_toc(section)
    bbot_docs_toc = bbot_docs_toc.strip()
    # assert len(bbot_docs_toc.splitlines()) == 2
    update_md_files("BBOT DOCS TOC", bbot_docs_toc)


update_docs()
