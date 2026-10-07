import textwrap
from pathlib import Path
import yaml

yaml_dir = Path("dataset_yamls")
output_file = Path("docs/index.rst")

header = """mirdata Dataset Gallery
=======================

Explore all supported datasets in ``mirdata``.



"""

entries = []

for yml_path in sorted(yaml_dir.glob("*.yaml")):
    with open(yml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    name = data.get("name", yml_path.stem)
    license_str = data.get("license", "Not specified")
    if isinstance(license_str, str):
    # Collapse multi-line/whitespace into a single clean line
        license_str = " ".join(license_str.split())

    # 1. Format annotations as inline code tags
    annotations_list = data.get("annotations")
    if annotations_list and isinstance(annotations_list, list):
        annotations_str = ", ".join(f"``{a}``" for a in annotations_list)
    else:
        annotations_str = "*None*"

    # 2. Format remotes / downloadable components
    remotes_list = data.get("remotes")
    if remotes_list and isinstance(remotes_list, list):
        remotes_str = ", ".join(f"``{r}``" for r in remotes_list)
    else:
        remotes_str = "*No direct download available*"

    
    
    card = f"""{name}
{'-' * len(name)}


* **Annotations:** {annotations_str}

"""
     # 2. Add Dataset Information dropdown
    docstring = data.get("docstring")
    if docstring and docstring.strip():
        lines = docstring.strip().splitlines()
        filtered = []
        for line in lines:
            stripped = line.strip()
            # Remove redundant ".. admonition::", ":class:", and "<Dataset> Loader" headers
            if stripped.startswith(".. admonition::") or stripped.startswith(":class:"):
                continue
            if stripped.endswith("Loader") and len(stripped.split()) <= 4:
                continue
            filtered.append(line)
        
        # Dedent and re-indent cleanly
        clean_doc = textwrap.dedent("\n".join(filtered)).strip()
        indented_doc = textwrap.indent(clean_doc, "   ")
        about_text = data.get("summary") or clean_doc

        card += f"""
**About this dataset:**
   
{about_text}

"""

    # 3. License, Remotes & YAML Download
    card += f"""* **License:** {license_str}
* **Downloadable Remotes:** {remotes_str}
* **YAML File:** :download:`{yml_path.name}<../dataset_yamls/{yml_path.name}>`

"""
    

    # 3. Add Download Instructions dropdown if available
    download_info = data.get("download_info")
    if download_info and download_info.strip():
        # Detect if download_info contains a file tree
        tree_markers = ["├──", "|--", "└──", "> "]
        if any(marker in download_info for marker in tree_markers):
            lines = download_info.strip().splitlines()
            formatted_lines = []
            tree_started = False
            for line in lines:
                if not tree_started and (line.startswith("    ") or any(m in line for m in tree_markers)):
                    formatted_lines.extend(["", "::", ""])
                    tree_started = True
                formatted_lines.append(line)
            download_info = "\n".join(formatted_lines)
        
        indented_download = textwrap.indent(download_info.strip(), "   ")
        card += f"""
.. admonition:: Download Instructions
   :class: dropdown
   

{indented_download}
"""

    # 4. Add BibTeX dropdown if available
    bibtex = data.get("bibtex")
    if bibtex and bibtex.strip():
        indented_bibtex = textwrap.indent(bibtex.strip(), "      ")
        card += f"""
.. admonition:: BibTeX Citation
   :class: dropdown

   .. code-block:: bibtex

{indented_bibtex}
"""

    # 5. Keep the raw YAML viewable inside a collapsible toggle
    card += f"""
.. admonition:: View Full YAML Definition
   :class: dropdown

   .. literalinclude:: ../dataset_yamls/{yml_path.name}
      :language: yaml
"""

    entries.append(card)

output_file.write_text(header + "\n".join(entries), encoding="utf-8")
print(f"Successfully generated {len(entries)} parsed dataset cards in {output_file}")
