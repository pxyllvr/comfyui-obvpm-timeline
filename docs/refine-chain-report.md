# OBVPM-Timeline: Refine-Chain

One clip at a time upscaling for MiniMax H3, with neighbor latent context.

## What it does

A clip on the timeline can be upscaled on its own and stay consistent with
its already-upscaled neighbors. The timeline no longer has to render in one
run. Queue a clip, or queue several clips at once. Each job uses the sidecars the
previous one wrote, and is kept track through a JSON file for each clip that logs its upscaled takes. This feature takes into account that some users might want to upscale using multiple passes (Example - base generation at 0.4mp, upscale pass 1 at 0.98mp/720p, and pass 2 at 2mp/1080p). It is designed to work for users who want to do just one upscale pass, or as many as they'd like.

## How it works

**Neighbor context.** `H3 Attach Neighbor Context` splices the neighbor's
pass-matched latent onto the clip before sampling. Pass 1 uses the
neighbor's pass 1, pass 2 uses pass 2. The neighbor's detail is pulled into
the body's edge, one way, so the boundary is blended before the sampler
runs. The spliced context is held at denoise 0 so the neighbor is not
rewritten.

**One window.** A spliced latent is kept in a single context window, so no
second window samples the body without the held context.

**Trim.** `H3 Trim Attached Context` crops the splice off after sampling, so
the next pass gets the body only. The timeline, full preview, and export all
play the base clip's cut, so an upscale stays aligned with its base even
when the timeline trimmed it to fit.

**The chain.** Each take is recorded with its sidecar, conditioning, pass,
and job ID. The timeline plays and exports whichever take is selected.

## Timeline UI

- A pass dropdown and take cycler per clip. Arrows stay visible and dim when
  a pass has only one take.
- A progress bar along each clip, derived from the chains on the strip. Base
  is white, a pass short of the top is yellow, the top pass is green. The
  top is the highest pass found anywhere, so a 1-pass and a 3-pass project
  both read correctly. Hover shows `pass 2 of 2`.
- Quick playback, full preview, and export all use the selected takes and
  the base clip's trim.
- A refresh button reloads chains without waiting for the Comfy job to finish, or the need to do a browser refresh.

## Key Files Changed

- `nodes_joint.py`: Attach (splice, one-way detail pull, hold), window
  growth for a spliced latent, trim.
- `h3_mctx_ui.js`: take selector, progress bar, trim carried into preview
  and export, refresh button.
- `__init__.py`: node registration.
- `nodes_render.py`: decode and save. Trims the spliced context off after
  decode, in pixel space, and composes that with the base clip's cut so the
  file matches what the timeline plays.

## Extend vs prepend

Extend works. The neighbor is before the clip, so its context goes at the
head, the body is sampled continuing from it, and the head is trimmed off.
The detail carries through because the sampler sees the context first.

Prepend is harder, because the neighbor is after the clip and causal
sampling generates the body before it reaches a tail context. The fix is to
put the neighbor's context at both ends: a head copy, so the body is sampled
continuing from it the way an extend is, and a tail copy to anchor the end.
Both are trimmed off. The detail carries through.

What the prepend work established:

- The pin is the authority, not the sidecar lineage. A prepend the timeline
  linked with a pin can still read as a hard cut in the lineage, and that
  check was rejecting the splice entirely. A run with no warp and no detail
  carryover means the neighbor was never spliced, not that the blend failed.
- The trim is in pixel space, after decode, and the direction matters. The
  match sits a fixed number of frames past the step the latent grid snapped
  to. Cutting the head instead of the tail shifts the whole clip by that
  many frames. Cutting the tail keeps the start and drops the extra context.
- A file that is already trimmed to the join plays from frame 0. Re-applying
  the base clip's enter offset on top of it skips into the file and misses
  the join.
- The exact frame offset is clip-specific and has to be measured, not
  guessed. The step grid cannot land on it.

## Known limits

- A slight drift can remain at the seam. The structure and detail still hold excellently.
  What is left is polish, whether in latent or in pixel space.
- Prepend trim precision: the end
  lands a few frames off the join. The offset is clip-specific, measured in
  pixel space after decode, and should be derived from the clip length and
  the latent grid rather than a fixed frame count. It needs testing across
  clip lengths.
- Prepend upscaling is noticeably slower. The context sits at both the head
  and the tail, which adds about 3 seconds of latent to sample instead of
  1.5. Upscale from left to right when you can.
- Bridging is head-only. The left neighbour's context goes at the head, and
  that is enough to hold the detail, so the right side adds nothing. Both
  ends is reserved for a pure prepend, which has no left neighbour. A pin
  overrides the hard-cut check on either side.
- The progress bar reflects the selected pass, not whether the take is
  seamless with its neighbor. Seam consistency is a separate question and
  the UI should address it.

## Ideas I have but not implemented

- Deleting unused takes to save disk space. A checkmark per clip to lock the
  chosen take and drop the rest.
- A seam indicator separate from the pass bar. The bar shows how far a clip
  is upscaled. It does not say whether the selected take actually blends with
  its neighbour. A second mark for that: blends, base-only against an
  upscale, or two upscales that don't meet.
- Skip pass 1. Re-upscaling pass 2 means going through the pass 1 group.
  Loading the existing pass 1 latent and conditioning straight into pass 2 while automatically muting the pass 1 group.
