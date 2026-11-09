// api.lib (3.3.13.0 R2, extension API 1.2; docs/EXTENSION_API.md "api.lib"): what a pack's bundle shares with the
// shell instead of bundling its own -- one React, one ReactDOM, the lib/ui primitives, the live feed, the theme,
// Studio's JSON client with the token, the panel workspace, the shell's composite widgets, keys and palette lines.
// It follows the shell's major version (`version`): a minor Studio only adds to it.
//
// The same object (without the per-pack `commands`) is `globalThis.__haloStudioLib`, set before any pack module
// loads (main.tsx), because a bundle built with the kit's Vite config (vite.pack.config.ts) takes React and the
// `@halo/<part>` modules from it when its module is evaluated -- hooks imported at the top, a `memo()` or a store
// made at module level -- before `mount` is called.
import * as React from "react";
import { createPortal, flushSync } from "react-dom";
import * as ReactDOMClient from "react-dom/client";
import * as jsxRuntime from "react/jsx-runtime";
import * as ui from "../lib/ui";
import * as api from "./api";
import * as events from "./events";
import { commandsFor, kbd } from "./kbd";
import * as store from "./store";
import * as theme from "./theme";
import * as util from "./util";
import * as widgets from "./widgets";
import * as workspace from "./workspace";

export const SHELL_MAJOR = "3";

export const LIB = Object.freeze({
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

export type StudioLib = typeof LIB & { commands: ReturnType<typeof commandsFor> };

/** The `lib` one pack's bundle gets: the shared parts and its own palette lines. */
export function libFor(pack: string): StudioLib {
  return { ...LIB, commands: commandsFor(pack) };
}

/** main.tsx, before the shell draws: pack modules evaluated later find the shared parts. */
export function installLib(): void {
  (globalThis as { __haloStudioLib?: unknown }).__haloStudioLib = LIB;
}
