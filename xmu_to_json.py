import json
import re

def read_feff_xmu(input_file, output_file):
    """
    Reads a FEFF xmu.dat file and writes its contents to a JSON file.
    """

    header_lines = []
    columns = []
    spectrum_columns = {}

    fermi_level = None
    gam_ch = None
    shell = None
    feff_version = None
    normalization_constant = None
    V_int = None
    Rs_int = None
    Vi = None
    Vr = None

    paths_used = None
    paths_total = None


    potential_entries = []

    # Regex patterns
    version_pattern = re.compile(r"FEFF\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    mu_pattern = re.compile(r"Mu\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
    gam_pattern = re.compile(r"Gam[_\s]*ch\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", re.IGNORECASE)
    shell_pattern = re.compile(r"\b([A-Za-z0-9]{1,2})\s+shell\b", re.IGNORECASE)

    pot_pattern = re.compile(
        r"POT\s+(\d+).*?Z\s*=\s*(\d+).*?Rmt\s*=\s*([-+]?\d*\.?\d+).*?Rnm\s*=\s*([-+]?\d*\.?\d+)",
        re.IGNORECASE
    )

    absorber_pattern = re.compile(
        r"Abs\b.*?Z\s*=\s*(\d+).*?Rmt\s*=\s*([-+]?\d*\.?\d+).*?Rnm\s*=\s*([-+]?\d*\.?\d+)",
        re.IGNORECASE
    )

    norm_pattern = re.compile(
        r"used to normalize mu.*?([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
        re.IGNORECASE
    )

    vint_pattern = re.compile(r"V[_\s]*int\s*=\s*([-+]?\d*\.?\d+)", re.IGNORECASE)
    rsint_pattern = re.compile(r"Rs[_\s]*int\s*=\s*([-+]?\d*\.?\d+)", re.IGNORECASE)

    # New patterns for Vi and Vr
    vi_pattern = re.compile(r"\bVi\s*=\s*([-+]?\d*\.?\d+)", re.IGNORECASE)
    vr_pattern = re.compile(r"\bVr\s*=\s*([-+]?\d*\.?\d+)", re.IGNORECASE)

    absorber_added = False

    with open(input_file, "r") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                clean = stripped.lstrip("# ").rstrip()
                header_lines.append(clean)

                if (m := paths_pattern.search(clean)):
                    paths_used = int(m.group(1))
                    paths_total = int(m.group(2))

                if (m := version_pattern.search(clean)):
                    feff_version = m.group(1)

                if (m := mu_pattern.search(clean)):
                    fermi_level = float(m.group(1))

                if (m := gam_pattern.search(clean)):
                    gam_ch = float(m.group(1))

                if (m := shell_pattern.search(clean)):
                    shell = m.group(1)

                if (m := norm_pattern.search(clean)):
                    normalization_constant = float(m.group(1))

                if (m := vint_pattern.search(clean)):
                    V_int = float(m.group(1))

                if (m := rsint_pattern.search(clean)):
                    Rs_int = float(m.group(1))

                if (m := vi_pattern.search(clean)):
                    Vi = float(m.group(1))

                if (m := vr_pattern.search(clean)):
                    Vr = -float(m.group(1))

                if not absorber_added and (m := absorber_pattern.search(clean)):
                    potential_entries.append({
                        "index": 0,
                        "Z": int(m.group(1)),
                        "Rmt": float(m.group(2)),
                        "Rnm": float(m.group(3))
                    })
                    absorber_added = True

                if (m := pot_pattern.search(clean)):
                    potential_entries.append({
                        "index": int(m.group(1)),
                        "Z": int(m.group(2)),
                        "Rmt": float(m.group(3)),
                        "Rnm": float(m.group(4))
                    })

                parts = clean.split()
                if all(not p.replace('.', '', 1).isdigit() for p in parts):
                    parts = [p for p in parts if p != "@#"]
                    columns = parts
                    spectrum_columns = {col: [] for col in columns}

                continue

            parts = stripped.split()

            if not columns:
                columns = [f"col{i+1}" for i in range(len(parts))]
                spectrum_columns = {col: [] for col in columns}

            for col, val in zip(columns, parts):
                spectrum_columns[col].append(float(val))

    potential_entries.sort(key=lambda p: p["index"])

    output = {
        "source": input_file,
        "header": header_lines,
        "feff_version": feff_version,
        "fermi_level_Mu": fermi_level,

        "potentials": {
            "V_int": V_int,
            "Rs_int": Rs_int,
            "entries": potential_entries
        },

        "spectrum": {
            "shell": shell,
            "core_hole_broadening": gam_ch,
            "normalization_constant": normalization_constant,
            "extra_broadening_Vi": Vi,
            "fermi_shift": Vr,
            "paths_used": paths_used, 
            "paths_total": paths_total,
            "data": spectrum_columns
        }
    }

    with open(output_file, "w") as out:
        json.dump(output, out, indent=4)

    print(f"JSON written to {output_file}")

