"""Refine chain: append-only history of refined takes per clip.

Stored as a parallel JSON file next to the clip (clip.mp4 -> clip.refine_chain.json)
so the large .mctx sidecar does not need rewriting. Empty file or missing
means no history (today's behavior).

Key is the part id when present, else the clip path (same space as upscale_skip).
"""

import json
import os

from . import mctx
from . import nodes_load


def chain_path(clip_path):
    """clip_00001.mp4 -> clip_00001.refine_chain.json"""
    base, _ = os.path.splitext(clip_path)
    return base + ".refine_chain.json"


def load_chain(clip_path):
    """Return the chain list, or [] if none.
    Accepts an output-relative path; resolves it first."""
    resolved = resolve_clip(clip_path)
    path = chain_path(resolved)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_chain(clip_path, chain):
    """Atomic write of the chain list."""
    path = chain_path(clip_path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chain, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def append_entry(clip_path, entry):
    """Append one entry (dict) to the clip's chain. Returns the new chain.
    clip_path may be output-relative; it is resolved first."""
    resolved = resolve_clip(clip_path)
    chain = load_chain(resolved)
    chain.append(entry)
    save_chain(resolved, chain)
    return chain


def resolve_clip(clip):
    """Resolve a sequence clip line to a filesystem path (output-relative or abs)."""
    return nodes_load.resolve_clip_path(clip)


def seed_from_sidecar(take_path):
    """Pull seed from a take's .mctx user_meta if present, else None."""
    sidecar = mctx.sidecar_path(take_path)
    if not os.path.isfile(sidecar):
        return None
    try:
        meta = mctx.read_header(sidecar)
        user = meta.get("user_meta") or ""
        if user:
            data = json.loads(user)
            if isinstance(data, dict) and "seed" in data:
                return data["seed"]
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return None


def check_green_compatibility(layouts):
    """Refuse if any green-linked pair of clips in the layouts have mismatched
    resolution (width/height from their headers). Different resolutions are
    OK only across white (hard-cut / gap) seams.

    layouts: list of layout dicts (one per segment). Each has 'clips' and
    the headers are loaded on demand.
    """
    # For M1 we only check the current run's source clips. Later passes
    # will check against active refined entries.
    seen = {}
    for lay in layouts or []:
        clips = lay.get("clips") or []
        if len(clips) < 2:
            continue
        # within a segment the seams are green (no gap between them)
        for clip in clips:
            path = resolve_clip(clip)
            if path in seen:
                continue
            try:
                header = mctx.read_header(mctx.sidecar_path(path))
                w = int(header.get("width", 0) or 0)
                h = int(header.get("height", 0) or 0)
                seen[path] = (w, h, clip)
            except (OSError, ValueError):
                seen[path] = (0, 0, clip)
        # now check consecutive in this segment
        for a, b in zip(clips, clips[1:]):
            pa, pb = resolve_clip(a), resolve_clip(b)
            ra, rb = seen.get(pa, (0, 0, a)), seen.get(pb, (0, 0, b))
            if ra[0] and rb[0] and (ra[0], ra[1]) != (rb[0], rb[1]):
                raise ValueError(
                    "H3 Timeline: green seam between %s (%dx%d) and %s (%dx%d) "
                    "has mismatched resolution. Refusing the run. Different "
                    "resolutions are allowed only across white seams."
                    % (os.path.basename(a), ra[0], ra[1],
                       os.path.basename(b), rb[0], rb[1]))
