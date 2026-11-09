// api.lib.store (3.3.13.0 R2, extension API 1.2): the shell's store helpers a pack's page uses -- a store of its
// own (createStore / useStore), the browser's per-user memory (writeLocal), the shell's own state (studio: the
// section on screen, the theme), a toast, and a section switch.
export { createStore, goSection, studio, toast, useStore, writeLocal, type SectionId, type Store } from "../lib/store";
