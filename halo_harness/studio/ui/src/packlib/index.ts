// api.lib (3.3.13.0 R2, extension API 1.2; docs/EXTENSION_API.md "api.lib"): what a pack's bundle shares with the
// shell instead of bundling its own -- one React, one ReactDOM, the lib/ui primitives, the live feed, the theme,
// a JSON client scoped to the pack (3.3.14.0 R1: packlib/scoped.ts), the panel workspace, the shell's composite
// widgets, keys and palette lines. It follows the shell's major version (`version`): a minor Studio only adds to it.
//
// The same parts are `globalThis.__haloStudioLib`, because a bundle built with the kit's Vite config
// (vite.pack.config.ts) takes React and the `@halo/<part>` modules from it when its module is evaluated -- hooks
// imported at the top, a `memo()` or a store made at module level -- before `mount` is called. 3.3.14.0 R1: while one
// pack's module is evaluated the global is that pack's lib (its own client; routes/packs/importPack.ts imports pack
// modules one at a time); otherwise it is LIB, whose client is scoped to no pack (read-only GETs).
import * as React from "react";
import { createPortal, flushSync } from "react-dom";
import * as ReactDOMClient from "react-dom/client";
import * as jsxRuntime from "react/jsx-runtime";
import * as ui from "../lib/ui";
import * as events from "./events";
import { commandsFor, kbd } from "./kbd";
import { scopedApi } from "./scoped";
import * as store from "./store";
import * as theme from "./theme";
import * as util from "./util";
import * as widgets from "./widgets";
import * as workspace from "./workspace";

export const SHELL_MAJOR = "3";

function parts(pack: string, key: string) {
  const api = Object.freeze(scopedApi(pack, key));
  return Object.freeze({
    version: SHELL_MAJOR,
    React,
    ReactDOM: Object.freeze({ ...ReactDOMClient, createPortal, flushSync }),
    jsxRuntime,
    ui,
    api,
    events,
    store,
    theme,
    util,
    widgets,
    workspace,
    kbd,
    fetchJson: api.fetchJson,
    authUrl: api.authUrl,
    css: theme.css,
  });
}

/** The parts with a client scoped to no pack: the global between pack imports. */
export const LIB = parts("", "");

export type StudioLib = typeof LIB & { commands: ReturnType<typeof commandsFor> };

/** The `lib` one pack's bundle gets: the shared parts, its own client (`key`: its registry key) and palette lines. */
export function libFor(pack: string, key: string): StudioLib {
  return { ...parts(pack, key), commands: commandsFor(pack) };
}

/** Set the global the `@halo/<part>` reads take (importPack.ts: a pack's lib while its module evaluates, then LIB). */
export function installLib(lib: typeof LIB = LIB): void {
  (globalThis as { __haloStudioLib?: unknown }).__haloStudioLib = lib;
}
