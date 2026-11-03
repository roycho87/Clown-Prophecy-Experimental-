// Geiru Prophecy Sampler helpers.
// lock_accept: on = accept on and stays on. off = accept off; an accept turned on by hand is used for one Prophecy shot,
// then switches itself off. Turning accept off by hand unlocks.
// A Prophecy candidate (accept off) stops a running Chain (Motion Context's or Geiru Chain), so it doesn't move past an
// unsaved shot. "increment after accept" on the Geiru Shot Counter (Geiru Context Suite) bumps it after an accepted run.
import { app } from "../../scripts/app.js";

function counterFor(node) {
    const inp = node.inputs?.find((i) => i.name === "shot_number");
    if (inp?.link != null) {
        const link = node.graph.links[inp.link] ?? node.graph.links.get?.(inp.link);
        const src = link ? node.graph.getNodeById(link.origin_id) : null;
        if (src?.type === "H3ClownShotCounter") return src;
    }
    const all = (app.graph._nodes || app.graph.nodes || []).filter((x) => x.type === "H3ClownShotCounter");
    return all.length === 1 ? all[0] : null;
}

function isClassic(counter) {
    const c = counter?.widgets?.find((x) => x.name === "use_classic_counter");
    return c ? c.value !== false : true;
}

const MC_SAVE = "MiniMaxH3MotionContextSaveLatent";
const MC_CHAIN = "MiniMaxH3MotionContextChain";
const CLOWN_CHAIN = "H3ClownChain";

function allNodes() {
    return app.graph?._nodes || app.graph?.nodes || [];
}

function stopChains() {
    for (const c of allNodes()) {
        const t = c.comfyClass || c.type;
        const st = t === MC_CHAIN ? c._h3mc : t === CLOWN_CHAIN ? c._clownChain : null;
        if (st?.chaining) { st.chaining = false; st.remaining = 0; }
    }
}

function bump(counter, by = 1) {
    if (!isClassic(counter)) return;
    const w = counter?.widgets?.find((x) => x.name === "shot_number");
    if (!w) return;
    w.value = Math.max(1, Number(w.value) + by);
    w.callback?.(w.value);
    counter.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "clown.prophecy.sampler",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "H3ClownProphecySampler") {
            const W = (node, name) => node.widgets?.find((x) => x.name === name);
            const onCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onCreated?.apply(this, arguments);
                const node = this, acc = W(node, "accept"), lock = W(node, "lock_accept");
                // continue_audio_frames <- Geiru Context head_frames (hidden)
                const ctx = () => {
                    const all = allNodes().filter((n) => /ClownContext/.test(n.comfyClass || n.type || ""));
                    return all.length ? all[0] : null;
                };
                for (const [name, from] of [["continue_audio_frames", () => ctx()?.widgets?.find((x) => x.name === "head_frames")]]) {
                    const w = W(node, name);
                    if (!w) continue;
                    const prev = w.serializeValue;
                    w.serializeValue = async function () {
                        const src = from();
                        if (src && src.value !== undefined && src.value !== "") w.value = src.value;
                        return prev ? await prev.apply(this, arguments) : w.value;
                    };
                    w.hidden = true;
                    w.computeSize = () => [0, -4];
                    w.draw = () => {};
                }
                requestAnimationFrame(() => node.setSize?.([node.size[0], node.computeSize()[1]]));
                if (acc && lock) {
                    const lcb = lock.callback;
                    lock.callback = function (v) {
                        const rr = lcb?.apply(this, arguments);
                        acc.value = !!lock.value;  // lock on -> accept on, lock off -> accept off
                        node.setDirtyCanvas?.(true, true);
                        return rr;
                    };
                    const acb = acc.callback;
                    acc.callback = function (v) {
                        const rr = acb?.apply(this, arguments);
                        if (!acc.value && lock.value) lock.value = false;  // accept off by hand -> unlock
                        node.setDirtyCanvas?.(true, true);
                        return rr;
                    };
                }
                return r;
            };
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function (info) {
                const r = onConfigure?.apply(this, arguments);
                // widget order is ... accept, lock_accept, (continue_audio, continue_audio_frames,) prophecy_latent_folder. Fix workflows saved in older orders:
                //   before lock_accept existed: ... accept, folder          (accept used to stay on -> lock = accept)
                //   first lock_accept version:  ... accept, folder, lock
                const acc = W(this, "accept"), lock = W(this, "lock_accept"), folder = W(this, "prophecy_latent_folder");
                const vals = info?.widgets_values;
                const ia = acc ? this.widgets.indexOf(acc) : -1;
                if (acc && lock && folder && Array.isArray(vals) && ia >= 0 && typeof vals[ia + 1] === "string") {
                    folder.value = vals[ia + 1];
                    lock.value = typeof vals[ia + 2] === "boolean" ? vals[ia + 2] : !!vals[ia];
                }
                // now ... lock_accept, continue_audio, continue_audio_frames, folder. Saved before the move:
                //   ... lock_accept, folder [, continue_audio, continue_audio_frames]
                const ca = W(this, "continue_audio"), caf = W(this, "continue_audio_frames");
                if (acc && lock && folder && ca && Array.isArray(vals) && ia >= 0 && typeof vals[ia + 1] === "boolean"
                    && typeof vals[ia + 2] === "string") {
                    folder.value = vals[ia + 2];
                    ca.value = typeof vals[ia + 3] === "boolean" ? vals[ia + 3] : false;
                    if (caf) caf.value = typeof vals[ia + 4] === "number" ? vals[ia + 4] : 39;
                }
                return r;
            };
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (output) {
                onExecuted?.apply(this, arguments);
                const state = output?.prophecy?.[0];
                if (!state) return;
                if (!state.accepted) {  // candidate rendered, the rest is stopped: don't let Chain move past this shot
                    stopChains();
                    this.setDirtyCanvas?.(true, true);
                    return;
                }
                const acc = W(this, "accept"), lock = W(this, "lock_accept");
                if (state.used && acc && lock && !lock.value) acc.value = false;  // unlocked: one use only
                const counter = counterFor(this);
                const mode = counter?.widgets?.find((x) => x.name === "shot_counter")?.value;
                if (mode === "increment after accept") bump(counter);
                this.setDirtyCanvas?.(true, true);
            };
        }
    },
});
