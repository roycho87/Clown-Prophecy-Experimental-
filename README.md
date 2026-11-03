# Geiru Prophecy (Experimental)

> Was **Clown Prophecy**. Only the names you see changed (it's named after the clown, Geiru, now, like the [Geiru Context Suite](https://github.com/roycho87/clown_context_suite)); the internal node names are the same, so saved workflows still load.

ComfyUI nodes for MiniMax H3 chains that render a clean ending for each shot before the shot exists, and pin it to the back of the shot.

**These nodes moved here from [Geiru Context Suite](https://github.com/roycho87/clown_context_suite).** It was moved here because it is too inconsistent and experimental to be considered a finished node. Keystone and Capstone are a much more promising direction. For long videos without degradation, use **Geiru Keystone** and **Geiru Late Lock** (or **Geiru Hybrid Windows**) in Geiru Context Suite.

## Needs Geiru Context Suite

Install [Geiru Context Suite](https://github.com/roycho87/clown_context_suite) too. The workflows here use its **Geiru Context**, **Geiru Anchoring**, **Geiru Shot Counter** and **Geiru Chain** nodes. If your copy of Geiru Context Suite is older and still has the Prophecy nodes in it, update it (`git pull`) so the two packs don't clash.

## Credits

Built on the work of **seitanism** and **nikodemon**. All credit to them for laying the groundwork.

## How it works

Give the model a target. Before a shot is rendered, **Geiru Prophecy Sampler** renders a short, clean ending for that shot from the shot's own prompt and reference pictures. **Geiru Anchoring** pins that ending to the back of the shot, so the shot has to land on good-quality frames.

Do this every two shots or so and the quality never drops far enough to notice. Use it when you also want to steer where each shot ends up; it needs a local language model and an extra render on the shots it runs.

## Nodes

| Node | What it does |
|---|---|
| **Geiru Prophecy Sampler** | Renders the clean ending for the shot, before the shot exists. |
| **Geiru Prophecy Prompt** | How the ending is worded: an LLM (Ollama, LM Studio…) rewrites the prompt so it only describes the ending, your own text, or the shot prompt as is. |
| **Clown Carryover** | On Prophecy shots, adds a frame from an earlier shot as one more reference picture, so the background and layout stay put. Can turn the frame into a canny, depth or pose map first. |

Everything shows up under the **Geiru Context Suite** category.

## Geiru Prophecy Sampler

| Setting | Meaning |
|---|---|
| `bypass` | On = Prophecy does nothing and the workflow runs normally, with the main sampler making its own sound. Lets you drop the node into any workflow. |
| `run_every` | 1–10. Prophecy only runs on shots that are multiples of this (3 = shots 3, 6, 9…). Other shots run normally. |
| `prophecy_frames` | Length of the ending (5, 22, 39, 56, 73…). Match Geiru Anchoring's `tail_frames`. |
| `seed` | Seed for the ending only. |
| `audio_mask` | How much the main sampler may change the shot's sound: 0 = keep it exactly, 1 = remake it. Ignored when the sound is already in the latent with its own mask (see below). |
| `accept` | Off = render a candidate ending, show it, and stop. Run again to reroll. On = use that ending and render the shot. On with no candidate yet = render one and use it straight away. |
| `lock_accept` | On = `accept` turns on and stays on, so every Prophecy shot runs hands-free. Off = `accept` turns off; when you turn `accept` on, it's used for one Prophecy shot and then switches itself off, so the next Prophecy shot stops for review. Turning `accept` off by hand also turns the lock off. |
| `continue_audio` | Off by default. On = when Prophecy makes the shot's sound, it holds the previous shot's last few seconds of audio at the start, so the new sound carries on from it. Needs `previous_shot` wired. How much it holds is copied from Geiru Context's `head_frames`. Skipped on the first shot or when nothing is saved yet. |
| `prophecy_latent_folder` | Folder in `output/` where the endings are saved. |

| Input | Meaning |
|---|---|
| `previous_shot` | Optional. The same Load Latent that feeds Geiru Context. Only used when `continue_audio` is on, and only loaded on Prophecy shots. |

The shot's sound: if the latent going in already carries sound (put in with ComfyUI's **Concat AV Latent**), Prophecy uses it. Otherwise it makes the shot's sound with a tiny quick render first, so the ending and the full shot share the same sound. With `continue_audio` on, that quick render continues the previous shot's sound.

## Clown Carryover

Sits between **MiniMax H3 Reference to Video** and the samplers: positive and latent in, positive and latent out. On the shots Prophecy runs, it takes a frame from an earlier shot, adds it as the next `<Picture N>`, and adds lines to the prompt saying it's the scene layout reference. The Prophecy Sampler sees the extra picture too, so the ending is made with it. On other shots it passes everything through. `bypass` and `run_every` are copied from the Prophecy Sampler when you queue (hidden on the node).

The picture follows the H3 prompting rules: a line in `subject_definitions` saying what it shows and a line in `retention_analysis` saying how closely to follow it.

| Setting | Meaning |
|---|---|
| `enabled` | On / off. |
| `first_shot` | On this shot and earlier there's no earlier shot to use, so it's off. |
| `carry_lighting` | Also tell H3 to follow the picture's lighting. |
| `carry_positions` | Also tell H3 to follow where the subjects stand. |
| `retention` | How closely H3 follows the picture: `fully_preserved`, `partially_preserved` (default), `weak_reference`. Or `canny` / `depth map` / `pose attribute_transfer`: the frame is turned into that map first and only its outlines / layout / poses are followed. |
| `frame_source` | `previous shot` = the shot before (follows the scene, but copies its drift). `selected clip` = always the clip in `clip_number` (1 = the first shot), so drift doesn't build up. |
| `clip_number` | Which saved clip to use with `selected clip`. |
| `frame_position` | `last frame` (default) or `first frame` of that shot. |

| Input / output | Meaning |
|---|---|
| `previous_shot` | The same Load Latent that feeds Geiru Context. Its folder is also where `selected clip` looks. |
| `optional_frame` | Your own picture, used instead. |
| `frame` (output) | The picture that was added (or its map), for a Preview Image. Nothing on shots it's off. |

H3 takes up to 9 pictures. If there are already 9, Carryover passes everything through.

Canny works out of the box. The depth and pose options use [ComfyUI's ControlNet Auxiliary Preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux) (Depth Anything V2 and DWPose); their models download by themselves the first time.

## Writing prompts for Geiru Prophecy

In `ollama` and `manual` mode, Geiru Prophecy Prompt rewrites your shot prompt so it only describes the ending. To do that it has to find the parts of your prompt, so **use the standard H3 reference-mode layout**.

**Easiest way to get the format right:** write your prompts with the [H3 Prompt IDE](https://github.com/ethanfel/ComfyUI-H3-Prompt-IDE) node. It outputs the standard layout Geiru Prophecy expects. Just make sure every shot after the first has a start time.

- **H3 Prompt IDE:** https://github.com/ethanfel/ComfyUI-H3-Prompt-IDE
- **Official MiniMax H3 prompting rules (Ref2VA):** https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md

The layout looks like this:

```
subject_definitions:
<Subject 1> is the pilot in <Picture 1>.

summary:
[reference generation] What happens in the whole clip.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved.

detailed_description:
One or two sentences of overall style and lighting.

[Shot 1]
What happens in the first shot.

[Shot 2] 00:05.000
What happens from 5 seconds on.

overall_soundscape:
Ambient sound.

non_diegetic_music:
N/A
```

- **Section names on their own line**, ending in a colon, spelled exactly like above. Blank lines between sections are fine either way.
- **Shots labelled `[Shot 1]`, `[Shot 2]`…** inside `detailed_description`.
- **Every shot after the first needs a start time** right after its label: `[Shot 2] 00:05.000` or `[Shot 2] At 00:05.000,`. The node uses these times to work out which shots fall in the ending. Without them, it can only use the last shot.
- **One-shot prompts** just need `[Shot 1]`.

The node cuts out the shots that fall in the ending, renumbers them for the short clip, and fixes the shot numbers in `retention_analysis` to match. In `ollama` mode the LLM then rewrites those shots to show how the action ends.

If your prompts use a different layout, use `as is` mode (your prompt unchanged) or `manual` mode (type the ending yourself).

**How well the ending is written depends on your LLM.** Bigger models that follow instructions well do best. Always look at the candidate before accepting it: reroll, or switch to `manual`, if it's wrong.

**The `llm_sees` switch** on Geiru Prophecy Prompt sets how much of your prompt the LLM gets:

| Setting | The LLM gets | Use it for |
|---|---|---|
| **trim all but ending [Shots] (weak LLMs)** | The subject definitions and only the shots that fall in the ending | Smaller or quantized models, which tend to copy the opening shot if they see it |
| **provide full [Shot] description (strong LLMs)** (default) | The whole prompt for context, plus the ending's shots | Strong models that can use the extra context |

If your endings keep looking like the start of the shot, switch it to the trim setting.

## Using it with a Chain node

Set the counter's `shot_counter` to **follow motion context**. The counter then copies the `clip_index` from the Motion Context **Save Latent** node every run, so Prophecy's `run_every` lines up with the Chain node's count (Geiru Chain or Motion Context's Chain). The counter only reads that number and never changes it; the Chain node stays in charge. Leave Load and Save Latent's `clip_index` as widgets (not wired) so the Chain buttons can move them.

How a session goes, with `run_every` 4 and `lock_accept` off:

1. Press **Chain**. Shots 1–3 run hands-free.
2. On shot 4 Prophecy renders a candidate ending and the chain stops there (nothing is saved for that shot yet).
3. Not happy? Press **Run/Re-roll** for a new candidate.
4. Happy? Turn `accept` on and press **Run/Re-roll**. Shot 4 renders with that ending, and `accept` switches itself back off.
5. Press **Chain** to carry on. It stops again at shot 8.

Don't press **Approve** or **Chain** right after a candidate: both move to the next shot first, so the shot with the candidate would be skipped.

With `lock_accept` on, Chain runs straight through every shot, Prophecy shots included.

## Geiru Anchoring and Geiru Context

Geiru Anchoring (holds Prophecy's ending at the back of the shot) and Geiru Context are in [Geiru Context Suite](https://github.com/roycho87/clown_context_suite); see its README for [their settings](https://github.com/roycho87/clown_context_suite#clown-context-and-clown-anchoring) and for [joining the clips](https://github.com/roycho87/clown_context_suite#joining-the-clips). Settings that work with Prophecy: Geiru Context `head_frames` 39, `drop_last` 17; Geiru Anchoring `tail_frames` 56, `drop_first` 17. The Anchoring frames must outnumber the Context frames.

## Example workflows

### Geiru Prophecy example

[`example_workflows/sane_person_example.json`](example_workflows/sane_person_example.json) is a normal H3 Motion Context-style chain with the Clown nodes in, driven by the **Geiru Chain** buttons. It only uses the Load / Save Latent nodes that Motion Context and Motion Context MultiRef both have, so it opens with no missing nodes whichever one you installed.

1. Load your reference pictures and write the prompt in the **H3 Prompt IDE** node.
2. Press **Chain** (or **Run/Re-roll** for one shot). Don't use ComfyUI's Run button.
3. The counter is on `follow motion context` and `lock_accept` is off, so every Prophecy shot stops so you can check the ending. Turn `accept` on and press **Run/Re-roll** to use it, then **Chain** to carry on. Raise `run_every` so Chain runs some shots on its own in between.

Keep Load Latent, Save Latent and Geiru Chain inside their group.

### Clown Carryover example

A 10-clip test made with the sane_clown_example workflow. The sound was replaced afterwards.

https://github.com/user-attachments/assets/6e446991-2ac2-4c9a-b476-169040baf0ce



[`example_workflows/sane_clown_example.json`](example_workflows/sane_clown_example.json) is the Geiru Chain example with **Clown Carryover** added. The Prophecy Sampler's `previous_shot` is wired, so you can turn `continue_audio` on. It runs the same way: write the prompt, press **Chain**. Carryover adds the first clip's last frame as a scene reference on every Prophecy shot (`frame_source` = `selected clip`, `clip_number` 1). Plug its `frame` output into the Preview Image to see what it added.

The model group also has ComfyUI's **Model Attention Backend** node (comfy kitchen attention), bypassed. It does the same job as the Sage attention patch, so turn on one or the other.

### Vlog example

[`example_workflows/insane_example.json`](example_workflows/insane_example.json) makes a talking vlog from pre-split audio clips and one prompt file per shot.

1. Set the prompt folder in **Load Text Batch From Dir** and the audio folder in **Shot Audio (one file per shot)**. One `.txt` and one audio file per shot, numbered in order.
2. Load your two reference pictures.
3. Set the batch count to the number of shots and run. With the counter on `increment` and `lock_accept` on, every shot renders in one go.

Each shot's audio goes into the latent with native nodes: **VAE Encode Audio** (H3 audio VAE) → **Set Latent Noise Mask** (a Solid Mask at 0, so the sampler keeps the sound exactly) → **Concat AV Latent** (with the Reference to Video latent). If the audio is shorter than the shot, the model makes up sound for the rest.

Video Settings is set to 8-second shots (192 frames), Geiru Context to 39 / drop_last 17 to match a 39-frame audio overlap, and Prophecy to run every 2 shots.

### Other packs the examples use

- [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) or [ComfyUI-H3-Motion-Context-MultiRef](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef) (save / load latent). Install one, not both: they use the same node names.
- [ComfyUI-H3-Prompt-IDE](https://github.com/ethanfel/ComfyUI-H3-Prompt-IDE)
- [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)
- [rgthree-comfy](https://github.com/rgthree/rgthree-comfy)
- [ComfyUI-Custom-Scripts](https://github.com/pythongosssss/ComfyUI-Custom-Scripts)
- [ComfyUI-Easy-Use](https://github.com/yolain/ComfyUI-Easy-Use)
- [ComfyMath](https://github.com/evanspearman/ComfyMath)
- [ComfyUI's ControlNet Auxiliary Preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux) (only for Clown Carryover's depth / pose options)
- Load Text Batch From Dir, Load Audio Batch From Dir, LoadImageCrop, VideoResolutionNode, and the MiniMax low-VRAM nodes

Geiru Prophecy Prompt in `ollama` mode needs a local LLM server: [Ollama](https://ollama.com) (`http://127.0.0.1:11434`), [LM Studio](https://lmstudio.ai) (`http://127.0.0.1:1234`), or any other OpenAI-compatible server. Put its address in `ollama_url`.

Geiru Prophecy Prompt in `ollama` mode needs a local LLM server: [Ollama](https://ollama.com) (`http://127.0.0.1:11434`), [LM Studio](https://lmstudio.ai) (`http://127.0.0.1:1234`), or any other OpenAI-compatible server. Put its address in `ollama_url`.

## Install

Install [Geiru Context Suite](https://github.com/roycho87/clown_context_suite) first, then clone this into `ComfyUI/custom_nodes/` and restart ComfyUI:

```
cd ComfyUI/custom_nodes
git clone https://github.com/roycho87/Clown-Prophecy-Experimental-
```

## License

GPL-3.0, like Geiru Context Suite.
