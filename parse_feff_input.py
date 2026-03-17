from typing import Any, Callable, Dict, List, Optional, Tuple, Union


# -----------------------------
# Exceptions
# -----------------------------

class ParseError(Exception):
    pass


# Range validation.
def validate_range(rng,result):
    if "min" in rng:
        if result < rng["min"]: return False
    if "max" in rng:
        if result > rng["max"]: return False
    if "seq" in rng:
        if result not in rng["seq"]: return False

    return True

# -----------------------------
# Header parsing (required/optional/rest)
# -----------------------------

def parse_typed_line_with_optional_and_rest(
    line: str,
    keyword: str,
    required: Dict[str,Any],
    optional: Dict[str,Any]
) -> List[Any]:
    """
    required: list of (name, converter) or (name, "rest")
    optional: list of (name, converter[, default]) or (name, "rest"[, default])
    """
    tokens = line.strip().split()
    tk = tokens[0]
    tokens[0] = keyword
    if not tokens:
        raise ParseError("Empty line")

    if tokens[0] != keyword:
        raise ParseError(f"Expected keyword '{keyword}', got '{tokens[0]}'")

    # Everything after the keyword
    body = line.strip()[len(tk):].lstrip()
    values = body.split()

    results: List[Any] = []

    def is_rest(field) -> bool:
        return field["type"] == "rest"

    # Validate rest-of-line placement
    if any(is_rest(f) for f in required[:-1]):
        raise ParseError(f"{keyword}: rest-of-line field must be last required field")

    if any(is_rest(f) for f in optional[:-1]):
        raise ParseError(f"{keyword}: rest-of-line field must be last optional field")

    # --- Parse required fields ---
    idx = 0
    for req in required:
        name = req["name"]
        conv = req["type"]
        if conv == "rest":
            result =  (name,body) if body else ""
            results.append(result)
            return results

        if idx >= len(values):
            raise ParseError(
                f"{keyword}: expected at least {len(required)} fields, got {len(values)}"
            )

        raw = values[idx]
        try:
            result = (name,conv(raw))
            results.append(result)
        except Exception as e:
            raise ParseError(
                f"{keyword}: required field '{name}' ('{raw}') failed conversion: {e}"
            )
        if "range" in req:
            rng = req["range"]
            if not validate_range(rng,result[1]):
                raise ParseError(f"Error in '{keyword}': invalid value of '{name}'."
                    + f"\n           Valid values: '{rng}'")

        idx += 1

    # --- Parse optional fields ---
    for opt in optional:
        name = opt["name"]
        conv = opt["type"]
        if "default" in opt:
            detault = opt["default"]
        else:
            default = None

        if conv == "rest":
            if idx < len(values):
                result = (name," ".join(values[idx:]))
            else:
                result = (name,default)
            results.append(result)
            return results

        if idx < len(values):
            raw = values[idx]
            try:
                result = (name,conv(raw))
                results.append(result)
            except Exception as e:
                raise ParseError(
                    f"{keyword}: optionoptfield '{name}' ('{raw}') failed conversion: {e}"
                )
            if "range" in opt:
                rng = opt["range"]
                if not validate_range(rng,result[name]):
                    raise ParseError(f"Error in '{keyword}': invalid value of '{name}'."
                      + f"\n           Valid values: '{rng}'")
            idx += 1
        else:
            result = (name,default)
            results.append(result)

    if idx < len(values):
        raise ParseError(
            f"{keyword}: too many fields; expected {idx}, got {len(values)}"
        )

    return results


# -----------------------------
# Body line parsing (per-keyword schemas)
# -----------------------------

def parse_body_line(
    line: str,
    keyword: str,
    required: Dict[str, Any],
    optional: Dict[str,Any],
    rest: Optional[Tuple[str]] = None,
) -> List[Any]:

    tokens = line.strip().split()
    values = tokens
    results: List[Any] = []

    # Required
    idx = 0
    for req in required:
        name = req["name"]
        conv = req["type"]
        if idx >= len(values):
            raise ParseError(
                f"{keyword} body: expected at least {len(required)} fields, got {len(values)}"
            )
        raw = values[idx]
        try:
            results.append((name,conv(raw)))
        except Exception as e:
            raise ParseError(
                f"{keyword} body: required field '{name}' ('{raw}') failed conversion: {e}"
            )
        if "range" in req:
             rng = req["range"]
             if not validate_range(rng,results[-1][1]):
                 raise ParseError(f"Error in '{keyword}': invalid value of '{name}'."
                     + f"\n           Valid values: '{rng}'")
        idx += 1

    # Optional
    for opt in optional:
        name = opt["name"]
        conv = opt["type"]
        if "default" in opt:
            default = opt["default"]
        else:
            default = None

        if idx < len(values):
            raw = values[idx]
            try:
                if conv == "rest":
                   results.append((name, " ".join(values[idx:])))
                else:
                   results.append((name,conv(raw)))
            except Exception as e:
                raise ParseError(
                    f"{keyword} body: optional field '{name}' ('{raw}') failed conversion: {e}"
                )
            idx += 1
        else:
            results.append((name,default))

        if "range" in opt:
             rng = opt["range"]
             if not validate_range(rng,results[-1][1]):
                 raise ParseError(f"Error in '{keyword}': invalid value of '{name}'." 
                     + f"\n           Valid values: '{rng}'")
    # Rest-of-line
    if rest is not None:
        (rest_name,) = rest
        if idx < len(values):
            results.append((rest_name," ".join(values[idx:])))
        else:
            results.append((rest_name, ""))
    else:
        print(results)
        if idx < len(values):
            raise ParseError(
                f"{keyword} body: too many fields; expected {idx}, got {len(values)}"
            )

    return results


# -----------------------------
# Block finalization
# -----------------------------

def finalize_block(keyword: str, block: Dict[str, Any], registry: Dict[str, Dict[str, Any]]) -> None:
    spec = registry[keyword]
    body_spec = spec.get("body", {"mode": "none"})

    mode = body_spec.get("mode", "none")
    body = block["body"]

    min_lines = body_spec.get("min")
    max_lines = body_spec.get("max")

    if min_lines is not None and len(body) < min_lines:
        raise ParseError(
            f"{keyword}: expected at least {min_lines} body lines, got {len(body)}"
        )

    if max_lines is not None and len(body) > max_lines:
        raise ParseError(
            f"{keyword}: expected at most {max_lines} body lines, got {len(body)}"
        )

    if mode == "none":
        if body:
            raise ParseError(f"{keyword}: body not allowed")
        block["body"] = None

    elif mode == "raw":
        pass

    elif mode == "typed":
        required = body_spec.get("required", [])
        optional = body_spec.get("optional", [])
        rest = body_spec.get("rest", None)

        parsed = []
        for line in body:
            parsed.append(parse_body_line(line, keyword, required, optional, rest))
        block["body"] = parsed

    elif callable(mode):
        block["body"] = mode(body)

    else:
        raise ParseError(f"{keyword}: unknown body mode '{mode}'")


# -----------------------------
# Block parsing (with comment/blank-line handling)
# -----------------------------

def strip_comment(line: str) -> str:
    """Remove everything after '*'."""
    if "*" in line:
        return line.split("*", 1)[0].rstrip()
    return line


def parse_blocks(lines: List[str], registry: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    blocks = dict()
    current = None
    line_num = 0
    keys = registry.keys()


    for raw in lines:
        line_num += 1

        # Remove trailing comments
        raw = strip_comment(raw)

        # Skip blank lines
        if not raw.strip():
            continue

        # Skip full-line comments
        if raw.lstrip().startswith("*"):
            continue

        stripped = raw.lstrip()
        token = stripped.split()[0] if stripped else None
        #is_keyword = token.upper in registry if token else False
        # Check if token is a keyword
        token = token.upper()
        is_keyword = False
        nmatch = 0
        for k in keys:
            if k.startswith(token):
                token = k
                nmatch = nmatch + 1
                is_keyword = True
        # Can't match more than one card.
        if nmatch > 1: raise ParseError(f"Input '{token}' matches more than one input card.")

        if is_keyword:
            if current is not None:
                current["end_line"] = line_num - 1
                finalize_block(keyword, current, registry)
                if keyword not in blocks:
                    blocks[keyword] = [current]
                elif registry[keyword]["repeatable"]:
                    blocks[keyword].append(current)
                else:
                    raise ParseError(f"Found multiple instances of '{token}' in input file.")
            keyword = token

            if keyword in blocks and not registry[keyword]["repeatable"]:
                raise ParseError(f"Found multiple instances of '{token}' in input file.")

            spec = registry[token]
            header = parse_typed_line_with_optional_and_rest(
                stripped,
                token,
                spec.get("required", []),
                spec.get("optional", []),
            )

            current = {
                "header": header,
                "body": [],
                "start_line": line_num,
                "end_line": None,
            }

        else:
            if current is None:
                continue
            current["body"].append(raw.rstrip("\n"))

        # If END keyword, exit loop
        if keyword == "END": break

    if current is not None:
        current["end_line"] = line_num
        finalize_block(keyword, current, registry)
        if keyword in blocks:
            blocks[keyword].append(current)
        else:
            blocks[keyword] = [current]

    return blocks

'''
ELNES has header data, + 4 to 5 non-repeating lines of body. Use specialized
parsing function for ELNES.
'''
def parse_elnes_input(lines):
    keyword = "ELNES"
    elnes_required = [
          [{"name": "E","type": float,"range": {"min":0}}],
          [{"name": "kx", "type": float},
           {"name": "ky", "type": float},
           {"name": "kz", "type":float}],
          [{"name": "alpha", "type": float, "range": {"min":0}},
           {"name": "beta", "type": float, "range": {"min":0}}],
          [{"name": "nr", "type": int, "range": {"min": 1}},
           {"name": "na", "type": int, "range": {"min": 1}}],
          [{"name": "dx", "type": float},{"name": "dy", "type": float}]]
    elnes_optional = [
        [{"name": "aver", "type": int},
         {"name": "cross","type": int},
         {"name": "relat","type": int}],[],[],[],[]]
    elnes_body = []
    nlines=0
    aver = 0
    for i,line in enumerate(lines):
        if i == 0:
            body = parse_body_line(line, keyword, elnes_required[0],
                elnes_optional[0])
            # Don't expect second line if  aver == 0.
            aver = body[2][1] if (body[2][1] is not None) else 0 
            j = 1 if (aver == 1) else 0
        else:
            body = parse_body_line(line, keyword, elnes_required[j],
                elnes_optional[j])

        elnes_body.append(body)
        j=j+1
        nlines=nlines+1

    # Now check that the number of lines is consistent and throw an error if
    # not.
    if aver == 0 and len(lines) !=5: 
        raise ParseError("Inconsistent input in ELNES card.")
    elif aver == 1 and len(lines) !=4: 
        raise ParseError("Inconsistent input in ELNES card.")
    elif aver !=1 and aver != 0:
        raise ParseError("Inconsistent input in ELNES card.")
    return elnes_body

def parse_egrid_input(lines):
    keyword = "EGRID"
    egrid_normal_required = [
        {"name": "grid_type", "type": str, "range":
            {"seq":('e_grid','k_grid','exp_grid')}},
        {"name": "grid_min", "type": str},
        {"name": "grid_max", "type": float},
        {"name": "grid_step", "type": float}
    ]
    egrid_user_required = [{"name": "energy", "type": float}]
    egrid_optional = []
    egrid_body = []
    user_mode=False
    igrid = 0
    for iline, line in enumerate(lines):
        token = line.strip().split()[0]
        if token == "user_grid":
            body = [('grid_type', 'user_grid')]
            igrid = igrid + 1
            grid = 'user_grid'
            user_mode = True
            #req = [{"name": "grid_type", "type": str}]
            #body = parse_body_line(line,keyword,req,egrid_optional)
            user_energies = []
        elif token in ("e_grid", "k_grid", "exp_grid"):
            if user_mode: 
                body.append(("energies",user_energies))
                egrid_body.append(body)
            grid = token
            user_mode = False
            body = parse_body_line(line,keyword,egrid_normal_required,egrid_optional)
            igrid = igrid + 1
        elif user_mode:
            bdy = parse_body_line(line,keyword,egrid_user_required,egrid_optional)
            user_energies.append(bdy[0][0])
            if iline + 1 == len(lines): 
                body.append(('energies', user_energies))
                egrid_body.append(body)
        else:
            raise ParseError(f"Error in EGRID card. Unexpected line after '{grid}'."
                + f"\n'{line}'")

        if not user_mode: egrid_body.append(body)

    return egrid_body
# -----------------------------
# registry definitions
# -----------------------------
''' 
Registry entries are dictionaries with the following definition:
 The dictionary keys to entries should be the name of the card in FEFF.
     The data for a card entry is another dictionary with the all of the following
     entries defined:
        "required" - list of "field" dictionaries defining the required fields on same line as
                     the key. Each field dictionary must contain "name" and "type"
                     entries. "default" and "range" entries are optional. The
                     "type" entry should list the type of data, which can be
                     str, int, float, "rest" (rest of line), or a callable
                     function. Can be an empty list if no required fields exist.
        "optional" - list of "field" dictionaries defining the optional fields
                     on the same line as the key. Same mandatory and optional
                     entries. Can be an empty list if no optional field exist.
        "repeatable" - Logical entry. If true, keyword can show be repeated in
                       input file.
        "body"     - Another definition defining how to process multi-line
                     cards. This dictionary has the following entries:
                         "mode" - required entry, defines the mode used for processing the
                                  multi-line block. The options are:
                                  "none"  - multi-line blocks not allowed.
                                  "typed" - each line has the same set of
                                            typed fields.
                                  "callable" - call a specialized parser for
                                               this block of lines.
                         "rest" - optional tuple entry ("name",) , saves the rest of each
                                  line in the field dictionary with key name "name".
                         "min"  - optional integer entry giving the min number
                                  of body lines.
                         "max"  - optional integer entry giving the max number
                                  of body lines.
'''
metadata_registry: Dict[str, Dict[str, Any]] = {
    "TITLE": {
        "required": [{"name": "text", "type": "rest"}],
        "optional": [],
        "repeatable": True,
        "body": {
            "mode": "none",
        },
    },
}

structure_registry: Dict[str, Dict[str, Any]] = {
    "CIF": {
        "required": [{"name": "cif_file", "type": str}],
        "optional": [{"name": "comment", "type": "rest"}],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "LATTICE": {
        "required": [
             {"name": "type", "type": str},
             {"name": "scale","type": float}
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "typed",
            "required": [
                {"name": "x", "type": float},
                {"name": "y", "type": float},
                {"name": "z", "type": float},
            ],
            "optional": [],
            "rest": ("comment",),
            "min": 3,
            "max": 3,
        },
    },

    "POTENTIALS": {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "typed",
            "required": [
                {"name": "ipot", "type": int},
                {"name": "z", "type": int},
                {"name": "symbol", "type": str},
            ],
            "optional": [
                {"name": "lmax_scf", "type": int, "default": -1},
                {"name": "lmax_fms", "type": int, "default": -1},
                {"name": "xnat", "type": float},
                {"name": "spinph", "type": float},
            ],
            "rest": ("comment",),
            "min": 2,
            "max": None,
        },
    },

    "REAL" : {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "RECIPROCAL" : {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "TARGET" : {
        "required": [{"name": "ic", "type": int}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "COORDINATES" : {
        "required": [{"name": "i", "type": int}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "RMULTIPLIER" : {
        "required": [{"name": "rmult", "type": float}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "SGROUP" : {
        "required": [{"name": "igroup", "type": int}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "CFAVERAGE" : {
        "required": [
           {"name": "iphabs", "type": int},
           {"name": "nabs", "type": int},
           {"name": "rclabs", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "OVERLAP" : {
        "required": [{"name": "iph", "type": int}],
        "optional": [],
        "repeatable": True,
        "body": {
            "mode": "typed",
            "required": [
                {"name": "iphovr",  "type": int},
                {"name": "novr",  "type": int},
                {"name": "rovr",  "type": float},
            ],
            "optional": [],
            "rest": None,
            "min": 1,
            "max": 1,
        },
    },

    "EQUIVALENCE" : {
        "required": [{"name": "ieq", "type": int}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },


    "ATOMS": {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "typed",
            "required": [
                {"name": "x", "type": float},
                {"name": "y", "type": float},
                {"name": "z", "type": float},
                {"name": "ipot", "type": int},
            ],
            "optional": [
                {"name": "label", "type": "rest"},
            ],
            "rest": None,
            "min": 2,
            "max": None,
        },
    },
}

spectrum_registry: Dict[str, Dict[str, Any]] = {
    "EXAFS" : {
        "required": [],
        "optional": [{"name": "xkmax", "type": float}],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "ELNES" : {
        "required": [],
        "optional": [
            {"name": "xkmax", "type": float},
            {"name": "xkstep", "type": float},
            {"name": "vixan", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": parse_elnes_input,
        },
    },

    "EXELFS" : {
        "required": [{"name": "xkmax", "type": float}],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": parse_elnes_input,
        },
    },

    "LDOS" : {
        "required": [
             {"name": "emin", "type": float},
             {"name": "emax", "type": float},
             {"name": "eimag", "type": float},
        ],
        "optional": [
             {"name": "neldos", "type": int}
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "XANES" : {
        "required": [],
        "optional": [
            {"name": "xkmax", "type": float},
            {"name": "xkstep", "type": float},
            {"name": "vixan", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "ELLIPTICITY" : {
        "required": [
            {"name": "elpty", "type": float},
            {"name": "x", "type": float},
            {"name": "y", "type": float},
            {"name": "z", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "MULTIPOLE" : {
        "required": [
            {"name": "le2", "type": int},
        ],
        "optional": [
            {"name": "l2lp", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "POLARIZATION" : {
        "required": [
            {"name": "x", "type": float},
            {"name": "y", "type": float},
            {"name": "z", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "COMPTON" : {
        "required": [],
        "optional": [
            {"name": "pqmax", "type": float},
            {"name": "npq", "type": int},
            {"name": "force-jzzp", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "DANES" : {
        "required": [],
        "optional": [
            {"name": "xkmax", "type": float},
            {"name": "xkstep", "type": float},
            {"name": "vixan", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "FPRIME" : {
        "required": [
            {"name": "emin", "type": float},
            {"name": "emax", "type": float},
            {"name": "estep", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "NRIXS" : {
        "required": [
            {"name": "nq", "type": int},
            {"name": "qx", "type": float},
            {"name": "qy", "type": float},
            {"name": "qz", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "XES" : {
        "required": [
            {"name": "emin", "type": float},
            {"name": "emax", "type": float},
            {"name": "estep", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "XMCD" : {
        "required": [],
        "optional": [
            {"name": "xkmax", "type": float},
            {"name": "xkstep", "type": float},
            {"name": "estep", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "XNCD" : {
        "required": [],
        "optional": [
            {"name": "xkmax", "type": float},
            {"name": "xkstep", "type": float},
            {"name": "estep", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "EDGE" : {
        "required": [
            {"name": "label", "type": str},
        ],
        "optional": [
            {"name": "s02", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "HOLE" : { 
        "required": [
            {"name": "ihole", "type": int},
            {"name": "s02", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },
}

program_control_registry = {
    "CONTROL" : {
        "required": [
            {"name": "ipot", "type": int},
            {"name": "ixsph", "type": int},
            {"name": "ifms", "type": int},
            {"name": "ipaths", "type": int},
            {"name": "igenfmt", "type": int},
            {"name": "iff2x", "type": int},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "PRINT" : {
        "required": [
            {"name": "ppot", "type": int},
            {"name": "pxsph", "type": int},
            {"name": "pfms", "type": int},
            {"name": "ppaths", "type": int},
            {"name": "pgenfmt", "type": int},
            {"name": "pff2x", "type": int},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "DIMS" : {
        "required": [
            {"name": "nmax", "type": int},
            {"name": "lmax", "type": int},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "KMESH" : {
        "required": [],
        "optional": [
            {"name": "nkp(x)", "type": int},
            {"name": "nkpy", "type": int},
            {"name": "nkpz", "type": int},
            {"name": "ktype", "type": int},
            {"name": "usesym", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "END" : {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "EGRID" : {
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": parse_egrid_input,
        },
    },

}

potentials_registry = {

    "AFOLP" : {
        "required": [
            {"name": "folpx", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "COREHOLE" : {
        "required": [
            {"name": "type", "type": str},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "SCF" : {
        "required": [
            {"name": "rscf", "type": float},
        ],
        "optional": [
            {"name": "lfms1", "type": int},
            {"name": "nscmt", "type": int},
            {"name": "ca", "type": float},
            {"name": "nmix", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "S02" : {
        "required": [
            {"name": "s02", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none",
        },
    },

    "CONFIG" : { 
        "required": [{"name": "input", "type": str}],
        "optional": [{"name": "nlines", "type": int}],
        "repeatable": False,
        "body": {
            "mode": "rest",
        },
    }, 

    "EXCHANGE" : { 
        "required": [
            {"name": "ixc", "type": int},
            {"name": "vr", "type": float},
            {"name": "vi", "type": float},
        ],
        "optional": [
            {"name": "ixc0", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    }, 

    "NOHOLE" : { 
        "required": [],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RGRID" : { 
        "required": [
            {"name": "delta", "type": float},
        ],
        "optional": [],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "UNFREEZEF" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CHSHIFT" : { 
        "required": [
            {"name": "ichsh", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CHBROADENING" : { 
        "required": [
            {"name": "igammach", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },


    "CHWIDTH" : {
        "required": [
            {"name": "gammach", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CORVAL" : { 
        "required": [
            {"name": "emin", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "EGAP" : { 
        "required": [
            {"name": "egap", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "EPS0" : { 
        "required": [
            {"name": "eps0", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "FOLP" : { 
        "required": [
            {"name": "ipot", "type": int},
            {"name": "folp", "type": float},
        ],
        "optional": [
        ],
        "repeatable": True,
        "body": {
            "mode": "none"
        },
    },

    "INTERSTITIAL" : { 
        "required": [
            {"name": "inters", "type": int},
            {"name": "vtot", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "ION" : { 
        "required": [
            {"name": "ipot", "type": int},
            {"name": "charge", "type": float},
        ],
        "optional": [
        ],
        "repeatable": True,
        "body": {
            "mode": "none"
        },
    },

    "JUMPRM" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "NUMDENS" : { 
        "required": [
            {"name": "ipot", "type": int},
            {"name": "numdens", "type": float},
        ],
        "optional": [
        ],
        "repeatable": True,
        "body": {
            "mode": "none"
        },
    },

    "OPCONS" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "PREPS" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SCREEN" : { 
        "required": [
            {"name": "parameter", "type": str},
            {"name": "value", "type": str},
        ],
        "optional": [
        ],
        "repeatable": True,
        "body": {
            "mode": "none"
        },
    },

    "SETEDGE" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SPIN" : { 
        "required": [
            {"name": "ispin", "type": int},
        ],
        "optional": [
            {"name": "x", "type": float},
            {"name": "y", "type": float},
            {"name": "z", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "LDEC" : { 
        "required": [
            {"name": "ld", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "LJMAX" : { 
        "required": [
            {"name": "lj", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "MPSE" : { 
        "required": [
            {"name": "ipl", "type": int},
        ],
        "optional": [
            {"name": "npole", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "PMBSE" : { 
        "required": [
            {"name": "ipmbse", "type": int},
            {"name": "nonlocal", "type": int},
            {"name": "ifxc", "type": int},
            {"name": "ibasis", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RPHASES" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RSIGMA" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "TDLDA" : { 
        "required": [
            {"name": "ifxc", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "FMS" : { 
        "required": [
            {"name": "rfms", "type": float},
        ],
        "optional": [
            {"name": "lfms2", "type": int},
            {"name": "minv", "type": int},
            {"name": "toler1", "type": float},
            {"name": "toler2", "type": float},
            {"name": "rdirec", "type": float},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "DEBYE" : { 
        "required": [
            {"name": "temp", "type": float},
            {"name": "thetad", "type": float},
        ],
        "optional": [
            {"name": "idwopt", "type": int},
            {"name": "opts", "type": "rest"},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "STRFAC" : { 
        "required": [
            {"name": "eta", "type": float},
            {"name": "gmax", "type": float},
            {"name": "rmax", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RPATH" : { 
        "required": [
            {"name": "rpath", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "NLEG" : { 
        "required": [
            {"name": "nleg", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "PCRITERIA" : { 
        "required": [
            {"name": "pcritk", "type": float},
            {"name": "pcrith", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SS" : { 
        "required": [
            {"name": "index", "type": int},
            {"name": "ipot", "type": int},
            {"name": "deg", "type": int},
            {"name": "rss", "type": float},
        ],
        "optional": [
        ],
        "repeatable": True,
        "body": {
            "mode": "none"
        },
    },

    "SYMMETRY" : { 
        "required": [
            {"name": "isym", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CRITERIA" : { 
        "required": [
            {"name": "critcw", "type": float},
            {"name": "critpw", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "IORDER" : { 
        "required": [
            {"name": "iord", "type": int},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "NSTAR" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "ABSOLUTE" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CORRECTIONS" : { 
        "required": [
            {"name": "vr", "type": float},
            {"name": "vi", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SIG2" : { 
        "required": [
            {"name": "sig2", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SIG3" : { 
        "required": [
            {"name": "alphat", "type": float},
            {"name": "thetae", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "MBCONV" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SFCONV" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RCONV" : { 
        "required": [
            {"name": "cen", "type": float},
            {"name": "cname", "type": str},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SELF" : { 
        "required": [
            {"name": "sig2", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "SFSE" : { 
        "required": [
            {"name": "k0", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "CGRID" : { 
        "required": [
        ],
        "optional": [
            {"name": "zpmax", "type": float},
            {"name": "ns", "type": int},
            {"name": "nphi", "type": int},
            {"name": "nz", "type": int},
            {"name": "nzp", "type": int},
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "RHOZZP" : { 
        "required": [
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

    "MAGIC" : { 
        "required": [
            {"name": "emagic", "type": float},
        ],
        "optional": [
        ],
        "repeatable": False,
        "body": {
            "mode": "none"
        },
    },

}


metadata_cards = ['TITLE']
program_control_cards = ['CONTROL', 'PRINT', 'DIMS']
structure_cards = ['CIF', 'LATTICE', 'REAL', 'RECIPROCAL', 'TARGET', 'EQUIVALENCE',
                   'COORDINATES', 'STRFAC', 'SGROUP', 'RMULTIPLIER', 'CFAVERAGE', 'OVERLAP', 
                   'POTENTIALS', 'ATOMS']
potentials_cards = ['AFOLP', 'COREHOLE', 'SCF','UNFREEZEF', 'CORVAL',
'INTERSTITIAL', 'NOHOLE', 'FOLP', 'ION', 'JUMPRM', 'SCREEN', 'SPIN', 'CONFIG']
selfenergy_cards = ['EXCHANGE', 'MPSE', 'OPCONS','NUMDENS','EPS0', 'PREPS',
'EGAP', 'RSIGMA', 'S02', 'MBCONV', 'SFCONV', 'RCONV', 'SELF', 'SFSE']
path_expansion_cards = ['PCRITERIA','CRITERIA', 'SYMMETRY','IORDER',
'NSTAR','SS']
grid_cards = ['RGRID', 'EGRID', 'KMESH']
nrixs_cards = ['LDEC', 'LJMAX'] 
method_cards = ['PMBSE', 'TDLDA', 'FMS', 'RPATH']
compton_cards = ['CGRID', 'RHOZZP']
eels_cards = ['MAGIC']
spectrum_cards = ['EXAFS', 'ELNES', 'EXELFS', 'LDOS', 'XANES', 'ELLIPTICITY',
'MULTIPOLE', 'POLARIZATION', 'COMPTON', 'DANES', 'FPRIME', 'NRIXS', 'XES',
'XMCD', 'XNCD', 'EDGE',
'HOLE','CHSHIFT','CHBROADENING','CHWIDTH','SETEDGE','CORRECTIONS','ABSOLUTE']
vibrational_cards = ['DEBYE', 'SIG2', 'SIG3']
# -----------------------------
# Convenience: parse from file path
# ----------------------------- 
def parse_file(path: str, registry: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]: 
    with open(path) as f: 
        lines = f.readlines() 
        return parse_blocks(lines, registry)

# ------------------------------
# Convenience: Write to feff input file.
# ------------------------------  

def write_block(f,card,block):
    def fmt(a):
        return "{:<10}".format(a)

    for i,block_dict in enumerate(block):
        # Write header line (starts with card, then parameters).
        header_names  = [fmt(field[0]) for field in block_dict["header"]]
        header_values = [fmt(str(field[1])) for field in block_dict["header"] 
                                            if field[1] is not None]
        header_comment_line = fmt("* " + card) + " " + " ".join(header_names) + "\n"
        header_value_line  = fmt(card + " ") + " " + " ".join(header_values) + "\n"
        if i == 0:
           f.writelines([header_comment_line,header_value_line])
        else:
           f.write(header_value_line)

        # Write body lines
        if block_dict["body"]:
            for iline,bline in enumerate(block_dict["body"]):
                if iline == 0:
                    comment_line = "* " + " ".join([fmt(field[0]) for field in bline])
                    f.write(comment_line + "\n")
    
                value_line = " ".join([fmt(str(field[1])) for field in bline
                                           if field[1] is not None]) + "\n"
                #if value_line.startswith("-"): 
                #    value_line = " " + value_line
                #else:
                value_line = "  " + value_line
                f.write(value_line) 

    f.write("\n")

def write_to_feff_input(blocks):
    def wmsg(f,msg):
        cline = "*******************************\n"
        f.write(cline)
        f.write("* " + msg + "\n")
        f.write(cline)
        return True

    # Open file.
    with open('feff_rewrite.inp','w') as f:
        written = False
        for card in metadata_cards:
            if card in blocks: 
                if not written: written = wmsg(f,"Metadata cards")
                write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* Program control cards\n")
        f.write("*******************************\n")
        for card in program_control_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* spectrum cards\n")
        f.write("*******************************\n")
        for card in spectrum_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        #f.write("\n*******************************\n")
        #f.write("* nrixs cards\n")
        #f.write("*******************************\n")
        for card in nrixs_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        #f.write("\n*******************************\n")
        #f.write("* compton cards\n")
        #f.write("*******************************\n")
        for card in compton_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        #f.write("\n*******************************\n")
        #f.write("* EELS cards\n")
        #f.write("*******************************\n")
        for card in eels_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* vibrational cards\n")
        f.write("*******************************\n")
        for card in vibrational_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* grid cards\n")
        f.write("*******************************\n")
        for card in grid_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* method cards\n")
        f.write("*******************************\n")
        for card in method_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* path expansion cards\n")
        f.write("*******************************\n")
        for card in path_expansion_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* self-energy cards\n")
        f.write("*******************************\n")
        for card in selfenergy_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* potentials cards\n")
        f.write("*******************************\n")
        for card in potentials_cards:
            if card in blocks: write_block(f,card,blocks[card])

        written = False
        f.write("\n*******************************\n")
        f.write("* structure cards\n")
        f.write("*******************************\n")
        for card in structure_cards:
            if card in blocks: write_block(f,card,blocks[card])


if __name__ == "__main__": 
    registry = (metadata_registry | structure_registry | spectrum_registry |
                program_control_registry | potentials_registry)
    from pprint import pprint 
    blocks=parse_file('feff.inp', registry)
    pprint(blocks)
    write_to_feff_input(blocks)

    # Make a dictionary with the same entries as above.
    cards_dict = {}
    cards_dict['metadata'] = {}
    for card in metadata_cards:
            if card in blocks: 
                cards_dict['metadata'][card] = blocks[card]
    cards_dict['program_control'] = {}
    for card in program_control_cards:
            if card in blocks: 
                cards_dict['program_control'][card] = blocks[card]
    cards_dict['spectrum'] = {}
    for card in spectrum_cards + nrixs_cards + eels_cards + compton_cards:
            if card in blocks: 
                cards_dict['spectrum'][card] = blocks[card]
    cards_dict['grids'] = {}
    for card in grid_cards:
            if card in blocks: 
                cards_dict['grids'][card] = blocks[card]
    cards_dict['method'] = {}
    for card in method_cards:
            if card in blocks: 
                cards_dict['method'][card] = blocks[card]
    cards_dict['path_expansion'] = {}
    for card in path_expansion_cards:
            if card in blocks: 
                cards_dict['path_expansion'][card] = blocks[card]
    cards_dict['self_energy'] = {}
    for card in selfenergy_cards:
            if card in blocks: 
                cards_dict['self_energy'][card] = blocks[card]
    cards_dict['potentials'] = {}
    for card in potentials_cards:
            if card in blocks: 
                cards_dict['potentials'][card] = blocks[card]
    cards_dict['structure'] = {}
    for card in structure_cards:
            if card in blocks: 
                cards_dict['structure'][card] = blocks[card]
    cards_dict['vibration'] = {}
    for card in vibrational_cards:
            if card in blocks: 
                cards_dict['vibration'][card] = blocks[card]

    import json
    with open('feff.json','w') as f:
        json.dump(cards_dict,f,indent=2)
