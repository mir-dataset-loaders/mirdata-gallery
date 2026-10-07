"""Script to generate yamls from mirdata dataset loaders.

Usage:
    python make_dataset_gallery_yaml.py
    python make_dataset_gallery_yaml.py --output your/folder/containing/dataset_yamls
"""
import typing
import argparse
import os
import mirdata
from mirdata.annotations import Annotation

import yaml
import sys
###helper function for the yaml format
def str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

yaml.add_representer(str, str_presenter)

### for annotations that might be partial in naming and not exact: "pitch_finetuned", "chords_majmin"
FALLBACK_MAP = {
    "beat": "BeatData",
    "chord": "ChordData",
    "key": "KeyData",
    "tempo": "TempoData",
    "section": "SectionData",
    "segment": "SectionData",
    "pitch": "F0Data",
    "f0": "F0Data",
    "melody": "F0Data",
    "note": "NoteData",
    "midi": "NoteData",
    "lyric": "LyricData",
    "phoneme": "LyricData",
    "syllable": "LyricData",
    "phrase": "LyricData",
    "tonic": "KeyData",
    "event": "EventData",
    "instrument": "Instrument",
}


def get_annotation_class_name(attr_name,item):
    """Extracts the class name (e.g. 'BeatData') if the property returns a mirdata Annotation."""
    # 1. Standard @property uses .fget, @cached_property uses .func

    func = getattr(item, "func", None)or getattr(item, "fget", None)
    if not func:
        return None
    # 1. first - Get return type hint from the function
    ret = getattr(func, "__annotations__", {}).get("return") 
    if ret:
        for arg in typing.get_args(ret):
            if arg is not type(None):
                ret = arg
                break
        if isinstance(ret, type) and issubclass(ret, Annotation) and ret is not Annotation:
            return ret.__name__
    # 2. Fallback: Keyword match for niche mirdata loaders 
    attr_lower = attr_name.lower()
    for keyword, class_name in FALLBACK_MAP.items():
        if keyword in attr_lower:
            return class_name
    return None


def collect_dataset_info(dataset_name=None):
    """Scans all mirdata datasets and extracts metadata for the gallery."""
    successful = []
    skipped = {}
    datasets = mirdata.list_datasets()
    #if given dataset name in CLI
    if dataset_name:
        if dataset_name in datasets:
            datasets = [dataset_name]
        else:
            raise ValueError(f"Dataset {dataset_name} not found in mirdata.")

    print(f"Scanning all {len(datasets)} datasets in mirdata...")

    for name in datasets:
        try:
            dataset = mirdata.initialize(name)
            
            # Extract basic info
            license_info = getattr(dataset, "_license_info", "Not specified")
            #mitigate new line issue with license
            if isinstance(license_info, str):
                license_info = license_info.strip()
            download_info = getattr(dataset, "_download_info", None)
            bibtex = getattr(dataset, "bibtex", None)
            remotes = list(dataset.remotes.keys()) if dataset.remotes else []
            docstring = sys.modules[f"mirdata.datasets.{name}"].__doc__
            
            # Extract ground-truth annotations (cached_property)
            track_class = getattr(dataset, "_track_class", None)
            annotations = set()
            if track_class:
                for attr in dir(track_class):
                    if attr.startswith("_"):
                        continue
                    item = getattr(track_class, attr, None)
                    if isinstance(item,(property, mirdata.core.cached_property)):
                        ann_cls = get_annotation_class_name(attr,item)
                        if ann_cls:
                            annotations.add(ann_cls)
            # If the dataset is a dedicated genre dataset (e.g. acousticbrainz_genre, gtzan_genre)
            if name.endswith("_genre"):
                annotations.add("Genre")

            successful.append({
                "name": name,
                "license": license_info,
                "remotes": remotes,
                "annotations": list(annotations),
                "download_info": download_info,
                "bibtex": bibtex,
                "docstring": docstring

            })
            print(f"  [OK]    {name:30s} | Annotations: {len(annotations)}")

        except ModuleNotFoundError as e:
            missing_pkg = str(e).replace("No module named ", "").strip("'")
            skipped[name] = f"Missing library: {missing_pkg}"
            print(f"  [SKIP]  {name:30s} | Skipped (needs: {missing_pkg})")

        except Exception as e:
            skipped[name] = str(e)
            print(f"  [ERROR] {name:30s} | Error: {e}")

    print(f"\nDone! Processed: {len(successful)}, Skipped: {len(skipped)}\n")
    return successful

def generate_gallery_yaml(datasets, output_dir):
  for dataset in datasets:
    name = dataset["name"]
    filepath = os.path.join(output_dir,f"{name}.yaml")
    with open(filepath, "w", encoding="utf-8") as f:
      yaml.dump(dataset, f, sort_keys=False,allow_unicode=True) ##allow unicode for some nicer formatting
    print(f"[SUCCESS] Written to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Generate dataset yaml files for mirdata.")
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join("dataset_yamls"),
        help="Path where yaml files will be saved (default: dataset_yamls)",
    )
    parser.add_argument("--dataset", type=str, default=None,help="Specific dataset to generate yaml for")
    
    
    args = parser.parse_args()

    datasets = collect_dataset_info(args.dataset)
    generate_gallery_yaml(datasets, args.output)


if __name__ == "__main__":
    main()
