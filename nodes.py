"""
Clown Prophecy (Experimental) for MiniMax H3
--------------------------------------------
Moved out of Clown Context Suite. Needs Clown Context Suite installed for Clown Context, Clown Anchoring, Clown Shot
Counter and Clown Chain.

    Clown Prophecy Sampler  renders a clean ending for the shot before the shot exists
    Clown Prophecy Prompt   how the ending is worded (Ollama rewrite, manual, or as is)

Audio runs at 40 Hz against 24 fps video, so F frames = round(F * 40/24) audio steps.
"""

import math
import os
import re

import torch

try:
    from comfy.nested_tensor import NestedTensor
except Exception:  # very old ComfyUI
    NestedTensor = None


CATEGORY = "Clown Context Suite"

FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
FPS = 24.0
AUDIO_HZ = 40.0
FRAME_RESCALE = AUDIO_HZ / FPS          # 5/3 audio steps per video frame


# --------------------------------------------------------------------------- helpers

def _need_nested(who):
    if NestedTensor is None:
        raise RuntimeError(f"{who}: this ComfyUI has no comfy.nested_tensor; update ComfyUI.")


def _as_tensor(part):
    if isinstance(part, dict) and "samples" in part:
        return part["samples"]
    return part


def _split(value):
    """NestedTensor / list / tensor -> list of tensors, video (5-D) first."""
    if NestedTensor is not None and isinstance(value, NestedTensor):
        parts = list(value.unbind())
    elif isinstance(value, (list, tuple)):
        parts = [_as_tensor(p) for p in value]
    else:
        parts = [value]
    return parts


def _has_samples(lat):
    if lat is None or not isinstance(lat, dict):
        return False
    s = lat.get("samples", None)
    if s is None:
        return False
    if isinstance(s, (list, tuple)) and (len(s) == 0 or any(p is None for p in s)):
        return False
    return True


def _frames_of(n_latents):
    return sum(FRAME_PER_TOKEN[k % 5] for k in range(n_latents))


def _audio_index(parts):
    """Index of the audio stream in a split AV latent, or None.

    The video stream is 5-D [B, C, T, H, W]; H3's audio stream is 4-D
    [B, C, 2, T] (or 3-D unbatched). Anything else is left alone.
    """
    vi = max(range(len(parts)), key=lambda i: parts[i].ndim)
    for i, p in enumerate(parts):
        if i != vi and p.ndim in (3, 4):
            return i
    return None


def _audio_steps(frames):
    """Video frames -> 40 Hz audio latent steps, rounded the way H3 allocates the grid."""
    return int(round(float(frames) * FRAME_RESCALE))


def _audio_len(a):
    return int(a.shape[-1])


def _pack(latent, parts, masks, packed, who):
    out = {kk: v for kk, v in latent.items() if kk not in ("samples", "noise_mask")}
    if packed or len(parts) > 1:
        _need_nested(who)
        out["samples"] = NestedTensor(tuple(parts))
        out["noise_mask"] = NestedTensor(tuple(masks))
    else:
        out["samples"] = parts[0]
        out["noise_mask"] = masks[0]
    return out


# --------------------------------------------------------------------------- repack


# --------------------------------------------------------------------------- context (head)


# --------------------------------------------------------------------------- anchoring (tail)


# --------------------------------------------------------------------------- tail refresh (latent only)

def _video_audio(latent, who):
    samples = latent["samples"]
    packed = NestedTensor is not None and isinstance(samples, NestedTensor)
    parts = _split(samples)
    vi = max(range(len(parts)), key=lambda i: parts[i].ndim)
    if parts[vi].ndim != 5:
        raise ValueError(f"{who}: expected a 5-D video latent [B, C, T, H, W], got {tuple(parts[vi].shape)}.")
    return parts, packed, vi, _audio_index(parts)


# --------------------------------------------------------------------------- reference lock


# --------------------------------------------------------------------------- color match to a chosen clip


# --------------------------------------------------------------------------- Clown Prophecy Sampler
PROPHECY_LLM_RULES = """You edit MiniMax H3 video prompts. A separate short clip will be generated that shows ONLY THE LAST
{secs:.2f} SECONDS of a longer video. {source}

Rewrite two sections for the short clip:
1. summary: one short English paragraph about the last {secs:.2f} seconds only. Keep the same square-bracketed
   task-type prefix as the original (for example [reference generation]).
2. detailed_description: start from the cut-out part you were given. Keep its opening style sentence(s) and its shot
   labels and timestamps exactly as given (they are already correct for the short clip). Rewrite each shot so it shows
   how that action ENDS: where the subjects, poses, expressions, camera and framing are during the last
   {secs:.2f} seconds. Do not go back to how the video or the shot started. Keep the same (VISUAL) / (SOUND) style
   if the original uses it. No new shots, cuts or timestamps.

Rules: write in English. Keep every reference label exactly as written (<Subject 1>, <Picture 1>, <Video 1>,
<Audio 1> and so on) and keep the same subjects, outfits, setting, lighting and camera style. Describe only visible
and audible things.
Answer with JSON only: {{"summary": "...", "detailed_description": "..."}}"""

_LLM_SOURCE_FULL = ("You get the full prompt of the longer video for context, then the part of its detailed_description that "
                    "falls in those last {secs:.2f} seconds, already cut out and renumbered for the short clip.")
_LLM_SOURCE_ENDING = ("You get the subject definitions and the part of the video's detailed_description that falls in those last "
                      "{secs:.2f} seconds, already cut out and renumbered for the short clip. That part is all you need.")

_SECTION_NAMES = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
                  "overall_soundscape", "non_diegetic_music")
_SECTION_RE = re.compile(r"(?mi)^[ \t]*(" + "|".join(_SECTION_NAMES) + r")[ \t]*:[ \t]*")
_SHOT_RE = re.compile(r"\[Shot\s*(\d+)\]", re.I)
_TIME_RE = re.compile(r"^\s*(?:at[ \t]+)?(\d{1,2}):(\d{2}(?:\.\d+)?)[ \t]*,?", re.I)


def _sections(prompt):
    """{name: (content_start, content_end)} for every known section header, in any spacing."""
    hits = list(_SECTION_RE.finditer(prompt))
    out = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(prompt)
        out.setdefault(m.group(1).lower(), (m.end(), end))
    return out


def _get_section(prompt, name):
    sec = _sections(prompt).get(name)
    return prompt[sec[0]:sec[1]].strip() if sec else None


def _set_section(prompt, name, text):
    sec = _sections(prompt).get(name)
    if not sec:
        return prompt, False
    start, end = sec
    tail = prompt[end:]
    sep = "\n\n" if tail.strip() else "\n"
    return prompt[:start].rstrip(" \t") + "\n" + text.strip() + sep + tail.lstrip("\r\n"), True


def _parse_shots(detailed):
    """-> (preamble, [(number, start_seconds or None, body)]). body is the text after the label and timestamp."""
    marks = list(_SHOT_RE.finditer(detailed or ""))
    if not marks:
        return (detailed or "").strip(), []
    shots = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(detailed)
        body = detailed[m.end():end]
        t = _TIME_RE.match(body)
        start = None
        if t:
            start = int(t.group(1)) * 60 + float(t.group(2))
            body = body[t.end():]
        shots.append((int(m.group(1)), start, body.strip()))
    if shots and shots[0][1] is None:
        shots[0] = (shots[0][0], 0.0, shots[0][2])
    return detailed[:marks[0].start()].strip(), shots


def _ending_slice(detailed, total_s, ending_s):
    """Cut the shots that fall in the last ending_s seconds out of detailed_description and renumber them.

    -> (sliced_text, {old_shot_number: new_shot_number}, note)."""
    pre, shots = _parse_shots(detailed)
    if not shots:
        return (detailed or "").strip(), {}, "no [Shot N] labels - whole description passed on"
    w0 = max(0.0, total_s - ending_s)
    if any(st is None for _, st, _ in shots[1:]):
        keep = [shots[-1]]
        note = "some shots have no timestamp - using the last shot"
    else:
        keep = []
        for i, (num, st, body) in enumerate(shots):
            nxt = shots[i + 1][1] if i + 1 < len(shots) else total_s
            if nxt > w0 + 1e-6 and st < total_s - 1e-6:
                keep.append((num, st, body))
        if not keep:
            keep = [shots[-1]]
        note = (f"ending = {w0:.2f}-{total_s:.2f} s, inside original shot(s) "
                + ", ".join(str(n) for n, _, _ in keep))
    mapping, blocks = {}, []
    for k, (num, st, body) in enumerate(keep, start=1):
        mapping[num] = k
        if k == 1:
            head = "[Shot 1]"
        else:
            rel = max(0.0, (st or 0.0) - w0)
            head = f"[Shot {k}] At {int(rel // 60):02d}:{rel % 60:06.3f},"
        blocks.append(head + ("\n" if body.startswith("(") else " ") + body)
    return ((pre + "\n\n") if pre else "") + "\n\n".join(blocks), mapping, note


def _fix_retention(prompt, mapping):
    """Point retention_analysis shot references at the ending's shots: renumber, drop shots that aren't in it."""
    ret = _get_section(prompt, "retention_analysis")
    det = _get_section(prompt, "detailed_description") or ""
    if ret is None:
        return prompt
    present = sorted({int(n) for n in _SHOT_RE.findall(det)}) or [1]

    def fix_list(m):
        olds = [int(n) for n in _SHOT_RE.findall(m.group(0))]
        news = []
        for o in olds:
            n = mapping.get(o) if mapping else (o if o in present else None)
            if n is not None and n in present and n not in news:
                news.append(n)
        if not news:
            news = present
        return ", ".join(f"[Shot {n}]" for n in sorted(news))

    new_ret = re.sub(r"\[Shot\s*\d+\](?:\s*,\s*\[Shot\s*\d+\])*", fix_list, ret, flags=re.I)
    return _set_section(prompt, "retention_analysis", new_ret)[0]


def _replace_sections(prompt, summary, detailed, who, mapping=None):
    out, notes = prompt, []
    if summary and summary.strip():
        out, ok = _set_section(out, "summary", summary)
        if not ok:
            notes.append("no 'summary:' section found - summary not replaced")
    if detailed and detailed.strip():
        out, ok = _set_section(out, "detailed_description", detailed)
        if not ok:
            notes.append("no 'detailed_description:' section found - description not replaced")
        else:
            out = _fix_retention(out, mapping)
    for nmsg in notes:
        print(f"[{who}] {nmsg}")
    return out, notes


def _llm_json(text):
    """First JSON object in an LLM reply. Thinking blocks and code fences are skipped."""
    import json as _json
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"^.*?</think>", "", text, flags=re.S | re.I)  # reply that starts mid-thought
    dec = _json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _ollama(url, model, system, prompt, seed, who):
    """Ask an LLM server for the ending's summary and detailed_description.

    Uses the OpenAI-compatible /v1/chat/completions endpoint, which Ollama, LM Studio and most other local
    servers all serve. `url` is the server base (http://127.0.0.1:11434 for Ollama, http://127.0.0.1:1234 for
    LM Studio); /v1 is added if it's missing.
    """
    import json as _json
    import urllib.request
    import urllib.error
    base = url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    endpoint = base + "/chat/completions"
    body = {"model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "temperature": 0.7,
            "seed": int(seed) % (2 ** 31),
            "stream": False}
    req = urllib.request.Request(endpoint, data=_json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = _json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"{who}: the LLM server at {endpoint} refused the request ({e.code}) for model '{model}'. "
                           f"Is that model loaded? {detail}")
    except Exception as e:
        raise RuntimeError(f"{who}: couldn't reach an LLM server at {endpoint} with model '{model}' ({e}). "
                           f"Ollama: run 'ollama serve' and 'ollama pull {model}'. "
                           f"LM Studio: start the local server and load the model.")
    try:
        text = resp["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError):
        raise RuntimeError(f"{who}: unexpected reply from {endpoint}: {str(resp)[:400]}")
    data = _llm_json(text)
    if data is None:
        raise RuntimeError(f"{who}: the LLM didn't return JSON. It said: {text[:400]}")
    return str(data.get("summary", "")), str(data.get("detailed_description", ""))


def _node_args(out):
    for attr in ("args", "result"):
        v = getattr(out, attr, None)
        if v is not None:
            return v
    return out


def _fingerprint(*things):
    """Short hash of everything that goes into a render: tensors by their exact values, everything else by value."""
    import hashlib
    h = hashlib.sha1()

    def feed(x):
        if NestedTensor is not None and isinstance(x, NestedTensor):
            for part in _split(x):
                feed(part)
        elif isinstance(x, torch.Tensor):
            t = x.detach().cpu().contiguous()
            h.update(f"T{tuple(t.shape)}{t.dtype}".encode())
            h.update(t.float().numpy().tobytes())
        elif isinstance(x, dict):
            for k in sorted(x, key=str):
                h.update(f"K{k}".encode())
                feed(x[k])
        elif isinstance(x, (list, tuple)):
            h.update(f"L{len(x)}".encode())
            for v in x:
                feed(v)
        elif x is None or isinstance(x, (str, int, float, bool)):
            h.update(f"V{x!r}".encode())
        else:
            h.update(f"O{type(x).__name__}".encode())

    for t in things:
        feed(t)
    return h.hexdigest()[:16]


class H3ClownProphecyPrompt:
    """How the Prophecy Sampler words the ending: Ollama rewrite, your own text, or the shot prompt as is."""

    CATEGORY = CATEGORY
    RETURN_TYPES = ("PROPHECY_PROMPT",)
    RETURN_NAMES = ("prophecy_prompt",)
    FUNCTION = "build"
    DESCRIPTION = ("Plug into the Clown Prophecy Sampler. ollama: an LLM (Ollama, LM Studio or any OpenAI-compatible server) rewrites the prompt's summary and "
                   "detailed_description so they describe only the ending. manual: your two boxes replace them. "
                   "as is: the shot prompt is used unchanged.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True, "tooltip": "The same prompt that goes into Reference To Video."}),
                "prompt_mode": (["ollama", "manual", "as is"], {"default": "ollama"}),
                "ollama_model": ("STRING", {"default": "qwen3.8:27b"}),
                "ollama_url": ("STRING", {"default": "http://127.0.0.1:11434",
                                          "tooltip": "Any OpenAI-compatible LLM server: Ollama (http://127.0.0.1:11434), "
                                                     "LM Studio (http://127.0.0.1:1234), and others. /v1 is added if missing."}),
                "manual_summary": ("STRING", {"default": "", "multiline": True}),
                "manual_detailed_description": ("STRING", {"default": "", "multiline": True}),
                "llm_sees": ("BOOLEAN", {"default": False,
                                         "label_on": "trim all but ending [Shots] (weak LLMs)",
                                         "label_off": "provide full [Shot] description (strong LLMs)",
                                         "tooltip": "ollama mode only. On: the LLM gets just the subject definitions and the shots "
                                                    "that fall in the ending, so it can't copy the opening shot. Off: it also gets "
                                                    "the whole prompt for context, which strong LLMs can use but weaker ones get "
                                                    "confused by."}),
            }
        }

    def build(self, prompt, prompt_mode, ollama_model, ollama_url, manual_summary, manual_detailed_description,
              llm_sees=False):
        return ({"prompt": prompt, "mode": prompt_mode, "ollama_model": ollama_model, "ollama_url": ollama_url,
                 "summary": manual_summary, "detailed": manual_detailed_description, "ending_only": bool(llm_sees)},)


class H3ClownProphecySampler:
    """Generates a clean ending for the shot before the shot exists, for Clown Anchoring to pin."""

    CATEGORY = CATEGORY
    RETURN_TYPES = ("LATENT", "IMAGE", "STRING", "AUDIO", "STRING", "LATENT")
    RETURN_NAMES = ("prophecy_latent", "preview", "prophecy_prompt", "shot_audio", "report", "audio_latent")
    FUNCTION = "prophesy"
    OUTPUT_NODE = False  # runs only when something downstream needs it
    DESCRIPTION = (
        "Makes the ending of this shot first: a fresh clip of the last prophecy_frames frames, built from Reference "
        "To Video's conditioning and latent (same pictures, same size, same length math). "
        "Accept off: render a candidate, show it, STOP the rest of the workflow. Run again to reroll. "
        "Accept on: use the saved candidate exactly and run the rest, with Clown Anchoring pinning it. "
        "Sound: if the latent already carries sound (e.g. forced audio through LTXV Concat AV Latent), that sound is used "
        "and passed on with its own mask; otherwise the shot's sound is pre-rendered with a tiny H3 render."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE", {"tooltip": "H3 video VAE."}),
                "audio_vae": ("VAE", {"tooltip": "H3 audio VAE."}),
                "sampler": ("SAMPLER",),
                "sigmas": ("SIGMAS",),
                "conditioning": ("CONDITIONING", {"tooltip": "Reference To Video's positive output."}),
                "latent": ("LATENT", {"tooltip": "Reference To Video's LATENT output (gives the size and shot length)."}),
                "bypass": ("BOOLEAN", {"default": False, "label_on": "BYPASSED - workflow runs normally",
                                       "label_off": "prophecy on",
                                       "tooltip": "On = Clown Prophecy does nothing: no ending, the main sampler makes its own sound."}),
                "run_every": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1,
                                      "tooltip": "Run Clown Prophecy only on shots that are multiples of this (3 = shots 3, 6, 9...). "
                                                 "Other shots run normally. 1 = every shot."}),
                "shot_number": ("INT", {"forceInput": True, "tooltip": "From Clown Shot Counter (in a Motion Context workflow, set it to 'follow motion context')."}),
                "prophecy_frames": ("INT", {"default": 56, "min": 5, "max": 4096, "step": 17,
                                            "tooltip": "Length of the ending (5, 22, 39, 56, 73 ...). Match Clown Anchoring's tail_frames."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "control_after_generate": "fixed"}),
                "audio_mask": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                                         "tooltip": "Noise mask on the audio_latent output for the main sampler. "
                                                    "0 = keep the shot audio exactly, 1 = regenerate it, 0.5 = halfway."}),
                "accept": ("BOOLEAN", {"default": False, "label_on": "YES - use this ending, run the rest",
                                       "label_off": "no - render a candidate and stop"}),
                "lock_accept": ("BOOLEAN", {"default": False, "label_on": "locked - accept stays on",
                                            "label_off": "unlocked - accept turns off after one use",
                                            "tooltip": "On = accept turns on and stays on (hands-free). Off = accept turns off, "
                                                       "and when you turn accept on it is used for one Prophecy shot, then switches "
                                                       "itself off so the next Prophecy shot stops for review."}),
                "continue_audio": ("BOOLEAN", {"default": False, "label_on": "sound: continue the previous shot",
                                               "label_off": "sound: fresh",
                                               "tooltip": "When Prophecy pre-renders the shot's sound, hold the previous shot's last "
                                                          "seconds of audio (from previous_shot) at the start so the new sound carries on "
                                                          "from it. Skipped when there's no previous shot (e.g. the first shot)."}),
                "continue_audio_frames": ("INT", {"default": 39, "min": 5, "max": 4096,
                                                  "tooltip": "How many frames of the previous shot's sound to hold (copied from "
                                                             "Clown Context's head_frames when you queue)."}),
                "prophecy_latent_folder": ("STRING", {"default": "clown_prophecy",
                                                      "tooltip": "Folder in output/ for the candidate and accepted endings."}),
            },
            "optional": {
                "prophecy_prompt": ("PROPHECY_PROMPT", {"lazy": True, "tooltip": "From Clown Prophecy Prompt. Empty = the shot prompt as is."}),
                "previous_shot": ("LATENT", {"lazy": True, "tooltip": "The previous shot's latent (the same Load Latent as Clown Context). "
                                                                     "Its sound is continued when continue_audio is on. Only loaded on Prophecy shots."}),
            },
        }

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _sample(model, cond, latent, sampler, sigmas, seed, preview=True):
        import comfy.sample, comfy.utils, comfy.model_management, latent_preview
        from comfy_extras.nodes_custom_sampler import Guider_Basic, Noise_RandomNoise
        guider = Guider_Basic(model)
        guider.set_conds(cond)
        noise = Noise_RandomNoise(seed)
        lat = latent.copy()
        x = comfy.sample.fix_empty_latent_channels(guider.model_patcher, lat["samples"],
                                                    lat.get("downscale_ratio_spacial", None), lat.get("downscale_ratio_temporal", None))
        lat["samples"] = x
        steps = sigmas.shape[-1] - 1
        if preview:
            cb = latent_preview.prepare_callback(guider.model_patcher, steps, {})
        else:  # progress bar only, no preview picture (the 64x64 sound render would show as a black square)
            pbar = comfy.utils.ProgressBar(steps)
            cb = lambda step, x0, x, total: pbar.update_absolute(step + 1, total, None)
        out = guider.sample(noise.generate_noise(lat), x, sampler, sigmas, denoise_mask=lat.get("noise_mask", None),
                            callback=cb, disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED, seed=noise.seed)
        res = lat.copy()
        res["samples"] = out.to(comfy.model_management.intermediate_device())
        res.pop("noise_mask", None)
        return res

    @staticmethod
    def _decode_video(vae, latent, who):
        parts, packed, vi, ai = _video_audio(latent, who)
        img = vae.decode(parts[vi])
        return img.reshape(-1, img.shape[-3], img.shape[-2], img.shape[-1]).float().clamp(0, 1)

    @staticmethod
    def _slice_audio(audio, start_s, dur_s):
        w, sr = audio["waveform"], int(audio["sample_rate"])
        a = int(round(start_s * sr)); b = a + int(round(dur_s * sr))
        a = max(0, min(a, w.shape[-1])); b = max(a, min(b, w.shape[-1]))
        return {"waveform": w[..., a:b].contiguous(), "sample_rate": sr}

    @staticmethod
    def _ref_items_from_blocks(vae, blocks):
        """Rebuild what Reference To Video showed the text encoder, from the reference latents in the conditioning."""
        items = []
        for b in blocks or []:
            kind = b.get("kind")
            if kind == "image":
                img = vae.decode(b["latent"])
                img = img.reshape(-1, img.shape[-3], img.shape[-2], img.shape[-1]).float().clamp(0, 1)[:1]
                items.append({"type": "image", "data": img})
            elif kind in ("video", "video_audio"):
                if kind == "video_audio":
                    items.append({"type": "audio"})
                fr = vae.decode(b["latent"])
                fr = fr.reshape(-1, fr.shape[-3], fr.shape[-2], fr.shape[-1]).float().clamp(0, 1)
                idx = list(range(0, fr.shape[0], int(FPS) // 2))
                items.append({"type": "video", "data": fr[idx], "timestamps": [i / 2.0 for i in range(len(idx))]})
            elif kind == "audio":
                items.append({"type": "audio"})
        return items

    @staticmethod
    def _refs_of(conditioning):
        for c in conditioning:
            if len(c) > 1 and isinstance(c[1], dict) and c[1].get("minimax_refs"):
                return c[1]["minimax_refs"]
        return None

    # ---------------------------------------------------------------- main
    @staticmethod
    def _active(bypass, run_every, shot_number):
        n = max(1, int(run_every))
        return (not bool(bypass)) and int(shot_number) % n == 0

    def check_lazy_status(self, bypass=False, run_every=1, shot_number=1, prophecy_prompt=None, continue_audio=False, **kw):
        if not self._active(bypass, run_every, shot_number):
            return []  # skipped: don't run the Prophecy Prompt (Ollama) or load audio
        need = []
        if prophecy_prompt is None:
            need.append("prophecy_prompt")
        if bool(continue_audio) and int(shot_number) > 1 and "previous_shot" in kw and kw["previous_shot"] is None:
            need.append("previous_shot")
        return need

    def prophesy(self, model, clip, vae, audio_vae, sampler, sigmas, conditioning, latent, bypass, run_every, shot_number,
                 prophecy_frames, seed, audio_mask, accept, prophecy_latent_folder, lock_accept=False, prophecy_prompt=None,
                 continue_audio=False, continue_audio_frames=39, previous_shot=None):
        import folder_paths
        import node_helpers
        from comfy_execution.graph import ExecutionBlocker
        from comfy_extras.nodes_minimax_h3 import _empty_av_latent, _encode_ref_audio, temporal_shape
        from comfy_extras.nodes_lt import LTXVConcatAVLatent
        who = "Clown Prophecy Sampler"
        pp = prophecy_prompt or {"mode": "as is"}
        shot = int(shot_number)
        parts_in, _, vi_in, _ = _video_audio(latent, who)
        v = parts_in[vi_in]
        width, height = int(v.shape[-1]) * 16, int(v.shape[-2]) * 16
        shot_frames = _frames_of(int(v.shape[2]))
        audio_t = int(temporal_shape(shot_frames)[2])

        # forced sound already in the latent (e.g. LTXV Concat AV Latent before Prophecy)?
        ai_in = _audio_index(parts_in)
        lat_audio = parts_in[ai_in] if (ai_in is not None and ai_in != vi_in) else None
        lat_audio_mask = None
        if lat_audio is not None and latent.get("noise_mask") is not None:
            try:
                ms = _split(latent["noise_mask"])
                if len(ms) == len(parts_in) and ms[ai_in].shape == lat_audio.shape:
                    lat_audio_mask = ms[ai_in]
            except Exception:
                lat_audio_mask = None
        forced = lat_audio is not None and float(lat_audio.abs().max()) > 1e-6

        def audio_out(sa):
            if forced:
                m = lat_audio_mask if lat_audio_mask is not None else torch.full_like(lat_audio, float(audio_mask))
                return ({"samples": lat_audio.cpu(), "noise_mask": m.cpu()},)
            z, _ = _encode_ref_audio(audio_vae, sa)
            z = z.cpu()[..., :audio_t]
            if z.shape[-1] < audio_t:
                z = torch.nn.functional.pad(z, (0, audio_t - z.shape[-1]))
            return ({"samples": z, "noise_mask": torch.full_like(z, float(audio_mask))},)
        if not self._active(bypass, run_every, shot):
            # skipped: no ending, the main sampler renders the shot and its sound normally
            ai = _audio_index(parts_in)
            if ai is None or ai == vi_in:
                lat_a, _ = _empty_av_latent(64, 64, shot_frames)
                pa = _split(lat_a["samples"])
                a = pa[_audio_index(pa)].clone()
            else:
                a = parts_in[ai].clone()
            a_mask = torch.ones_like(a)
            if "noise_mask" in latent and latent["noise_mask"] is not None:
                try:
                    ms = _split(latent["noise_mask"])
                    if len(ms) == len(parts_in) and ms[ai].shape == a.shape:
                        a_mask = ms[ai].clone()
                except Exception:
                    pass
            why = "BYPASSED" if bool(bypass) else f"skipped (shot {shot} is not a multiple of {int(run_every)})"
            report = f"{who}: {why}. No ending; the main sampler makes the shot and its sound normally."
            print(report)
            b = ExecutionBlocker(None)
            return {"ui": {"prophecy": [{"accepted": True, "shot": shot}]},
                    "result": (None, b, b, None, report, {"samples": a, "noise_mask": a_mask})}
        audio = None
        if forced:
            wav = audio_vae.decode(lat_audio).movedim(-1, 1)
            audio = {"waveform": wav.cpu(), "sample_rate": int(getattr(audio_vae, "audio_sample_rate", 44100))}
        F = int(prophecy_frames)
        base = os.path.join(folder_paths.get_output_directory(), prophecy_latent_folder)
        os.makedirs(base, exist_ok=True)
        cand_p = os.path.join(base, f"shot_{shot:04d}_candidate.pt")
        sel_p = os.path.join(base, f"shot_{shot:04d}.pt")
        audio_p = os.path.join(base, f"shot_{shot:04d}_audio.pt")
        secs = F / FPS
        ui_state = lambda acc: {"prophecy": [{"accepted": bool(acc), "used": bool(acc), "shot": shot}]}

        # fingerprints: a saved file is only reused if everything that made it is unchanged
        pp_key = {k: pp.get(k) for k in ("mode", "prompt", "summary", "detailed", "ollama_model", "ending_only")}
        prev_audio = _audio_of(previous_shot) if (bool(continue_audio) and not forced and shot > 1) else None
        audio_key = _fingerprint("audio-v2", conditioning, int(seed), shot_frames, sigmas, prev_audio,
                                 int(continue_audio_frames) if prev_audio is not None else 0)
        ending_key = _fingerprint("ending-v1", conditioning, pp_key, int(seed), F, width, height, shot_frames,
                                  sigmas, lat_audio if forced else None)

        # ---------------- accepted: reuse the saved candidate exactly, if it was made from these same inputs
        src = d = None
        stale = []
        if accept:
            for p in (cand_p, sel_p):
                if not os.path.exists(p):
                    continue
                dd = torch.load(p, map_location="cpu", weights_only=False)
                if dd.get("key") == ending_key:
                    src, d = p, dd
                    break
                stale.append(os.path.basename(p))
        if stale:
            print(f"[{who}] shot {shot}: saved ending {', '.join(stale)} was made from a different prompt, seed, size "
                  f"or sound - rendering a new one.")
        if src is not None:
            if src == cand_p:
                torch.save(d, sel_p)
                with open(os.path.join(base, f"shot_{shot:04d}_prompt.txt"), "w", encoding="utf-8") as f:
                    f.write(d["prompt"])
            samples = NestedTensor(tuple(d["parts"])) if (NestedTensor is not None and len(d["parts"]) > 1) else d["parts"][0]
            preview = d["preview"].float() / 255.0
            shot_audio = d.get("shot_audio") or audio
            report = (f"{who}: shot {shot} ACCEPTED (seed {d['seed']}, {F} frames). Using the saved ending exactly "
                      f"(same prompt, seed and size as when it was rendered); "
                      f"the rest of the workflow runs. Saved as {sel_p}.")
            print(report)
            return {"ui": ui_state(True), "result": ({"samples": samples}, preview, d["prompt"], shot_audio, report) + audio_out(shot_audio)}

        # ---------------- the ending's conditioning
        mode = pp.get("mode", "as is")
        notes = []
        carry = _carryover_lines(conditioning)
        if carry:
            notes.append("Clown Carryover's picture used (its prompt lines added)")
        if mode == "as is":
            cond = conditioning
            new_prompt = _add_carryover_lines(pp.get("prompt") or "(shot prompt as is)", carry)
        else:
            prompt = _add_carryover_lines(pp["prompt"], carry)
            if mode == "manual":
                new_prompt, more = _replace_sections(prompt, pp.get("summary", ""), pp.get("detailed", ""), who)
                notes += more
            else:
                total_s = shot_frames / FPS
                sliced, mapping, snote = _ending_slice(_get_section(prompt, "detailed_description") or "", total_s, secs)
                notes.append(snote)
                window = ("THE LAST %.2f SECONDS (%.2f-%.2f s of the %.2f s video), cut out and renumbered for the short clip:"
                          "\n\n%s" % (secs, max(0.0, total_s - secs), total_s, total_s, sliced))
                if pp.get("ending_only", False):
                    old_sum = _get_section(prompt, "summary") or ""
                    tag = re.match(r"\s*(\[[^\]]*\])", old_sum)
                    ask = ("subject_definitions:\n" + (_get_section(prompt, "subject_definitions") or "") + "\n\n"
                           + ("Start the summary with: " + tag.group(1) + "\n\n" if tag else "") + window)
                    source = _LLM_SOURCE_ENDING
                    notes.append("LLM saw only the ending's shots")
                else:
                    ask = prompt + "\n\n---\n" + window
                    source = _LLM_SOURCE_FULL
                rules = PROPHECY_LLM_RULES.format(secs=secs, source=source.format(secs=secs))
                s_new, d_new = _ollama(pp["ollama_url"], pp["ollama_model"], rules, ask, seed, who)
                if not _SHOT_RE.search(d_new or ""):
                    notes.append("the LLM's description had no [Shot] labels - using the cut-out shots as they are")
                    d_new = sliced
                new_prompt, more = _replace_sections(prompt, s_new, d_new, who, mapping)
                notes += more
            blocks = self._refs_of(conditioning)
            tokens = clip.tokenize(new_prompt, minimax_ref_items=self._ref_items_from_blocks(vae, blocks))
            cond = clip.encode_from_tokens_scheduled(tokens)
            if blocks:
                cond = node_helpers.conditioning_set_values(cond, {"minimax_refs": blocks})

        # ---------------- the shot's audio: given, or pre-rendered with a tiny H3 render
        if audio is None:
            saved = torch.load(audio_p, map_location="cpu", weights_only=False) if os.path.exists(audio_p) else None
            if isinstance(saved, dict) and saved.get("key") == audio_key:
                shot_audio = saved["audio"]
                anote = "pre-rendered shot audio reused (same prompt and seed)"
            else:
                lat_a, _ = _empty_av_latent(64, 64, shot_frames)
                lat_a, held_note = _hold_previous_audio(lat_a, prev_audio, continue_audio_frames, who)
                out_a = self._sample(model, conditioning, lat_a, sampler, sigmas, seed, preview=False)
                parts_a = _split(out_a["samples"])
                wav = audio_vae.decode(parts_a[_audio_index(parts_a)]).movedim(-1, 1)
                shot_audio = {"waveform": wav.cpu(), "sample_rate": int(getattr(audio_vae, "audio_sample_rate", 44100))}
                torch.save({"key": audio_key, "audio": shot_audio}, audio_p)
                anote = ("shot audio pre-rendered with a 64x64 H3 render and saved" + held_note
                         + (" (the saved one was from a different prompt or seed)" if saved is not None else ""))
        else:
            shot_audio = audio
            anote = "the latent's own (forced) sound used"
        tail = self._slice_audio(shot_audio, max(0, shot_frames - F) / FPS, secs)

        # ---------------- ending latent, audio locked
        lat, _ = _empty_av_latent(width, height, F)
        z, _ = _encode_ref_audio(audio_vae, tail)
        lat = _node_args(LTXVConcatAVLatent.execute(video_latent=lat, audio_latent={"samples": z, "noise_mask": torch.zeros_like(z)}))
        if isinstance(lat, (tuple, list)):
            lat = lat[0]

        # ---------------- render the ending
        out = self._sample(model, cond, lat, sampler, sigmas, seed)
        preview = self._decode_video(vae, out, who)
        parts = [p.cpu() for p in _split(out["samples"])]
        torch.save({"key": ending_key, "parts": parts, "prompt": new_prompt, "seed": int(seed), "frames": F,
                    "preview": (preview * 255).round().to(torch.uint8), "shot_audio": shot_audio}, cand_p)
        report = (f"{who}: shot {shot} CANDIDATE rendered (seed {seed}, {F} frames = last {secs:.2f} s of a "
                  f"{shot_frames}-frame {width}x{height} shot; prompt: {mode}; {anote}). The rest of the workflow is "
                  f"stopped. Run again to reroll, or turn 'accept' on and run to use this one."
                  + ("".join("\n  note: " + n for n in notes)))
        if accept:
            # accept was on but there was no matching saved ending: take this render as accepted
            torch.save(torch.load(cand_p, map_location="cpu", weights_only=False), sel_p)
            with open(os.path.join(base, f"shot_{shot:04d}_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(new_prompt)
            report = (f"{who}: shot {shot} rendered and ACCEPTED straight away (accept was on, no matching saved ending; seed {seed}, "
                      f"{F} frames; prompt: {mode}; {anote}). The rest of the workflow runs. Saved as {sel_p}.")
            print(report)
            return {"ui": ui_state(True), "result": ({"samples": out["samples"]}, preview, new_prompt, shot_audio, report) + audio_out(shot_audio)}
        print(report)
        return {"ui": ui_state(False), "result": (ExecutionBlocker(None), preview, new_prompt, shot_audio, report) + audio_out(shot_audio)}


def _carryover_lines(conditioning):
    """The prompt lines Clown Carryover added with its extra reference picture ({} when it didn't)."""
    for c in conditioning or []:
        if len(c) > 1 and isinstance(c[1], dict):
            if c[1].get("clown_carryover_lines"):
                return c[1]["clown_carryover_lines"]
            if c[1].get("clown_carryover_line"):  # older Clown Carryover
                return {"subject_definitions": c[1]["clown_carryover_line"]}
    return {}

def _add_carryover_lines(prompt, lines):
    """Each line at the end of its section (a missing subject_definitions goes on top; other missing sections are skipped)."""
    for name in ("subject_definitions", "retention_analysis"):
        line = lines.get(name)
        if not line or line in prompt:
            continue
        body = _get_section(prompt, name)
        if body is None:
            if name == "subject_definitions":
                prompt = line + "\n\n" + prompt
            continue
        prompt, _ = _set_section(prompt, name, body.rstrip() + "\n" + line)
    return prompt

def _audio_of(latent):
    """Audio part of a saved shot latent (Load Latent's output), or None (nothing loaded / no sound)."""
    if not _has_samples(latent):
        return None
    s = latent["samples"]
    if isinstance(s, (list, tuple)):
        s = [p for p in s if p is not None]
    parts = _split(s)
    ai = _audio_index(parts)
    if ai is None:
        return None
    a = parts[ai]
    if a.ndim < 3 or float(a.abs().max()) < 1e-6:
        return None
    return a.contiguous()

def _hold_previous_audio(lat, prev_audio, frames, who):
    """Put the previous shot's last `frames` frames of audio at the start of the latent's audio, mask 0 there."""
    if prev_audio is None:
        return lat, ""
    parts = _split(lat["samples"])
    ai = _audio_index(parts)
    if ai is None:
        return lat, ""
    ta, sa = parts[ai], prev_audio
    if sa.ndim == ta.ndim - 1:
        sa = sa.unsqueeze(0)
    if sa.shape[1:-1] != ta.shape[1:-1]:
        print(f"[{who}] previous shot's audio {tuple(sa.shape)} doesn't match {tuple(ta.shape)} - sound made fresh")
        return lat, ""
    n = min(_audio_steps(int(frames)), _audio_len(sa), _audio_len(ta))
    if n <= 0:
        return lat, ""
    ta = ta.clone()
    ta[..., :n] = sa[..., _audio_len(sa) - n:].to(device=ta.device, dtype=ta.dtype)
    parts[ai] = ta
    masks = [torch.ones_like(p) for p in parts]
    masks[ai][..., :n] = 0.0
    return _pack(lat, parts, masks, True, who), f", continuing the previous shot's last {n / AUDIO_HZ:.2f}s of sound"


NODE_CLASS_MAPPINGS = {
    "H3ClownProphecySampler": H3ClownProphecySampler,
    "H3ClownProphecyPrompt": H3ClownProphecyPrompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3ClownProphecySampler": "Clown Prophecy Sampler",
    "H3ClownProphecyPrompt": "Clown Prophecy Prompt",
}
