// His own old map file named auto or starter (3.6.0.5 A5, decision 3): Halo never runs, renames, moves or deletes it;
// its one button [Copy as my-map] (the Map's bar and Setup's row alike) reads HIS file by its scope and writes the copy
// under the first free my-map name (no `from:` added), then opens the copy in Agents -> 3 · Map. The only write is the copy.
import { api } from "../../../lib/api";
import { goSection } from "../../../lib/store";
import { loadMaps, maps, msg, openMap } from "./mapStore";
import type { MapDetail } from "./mapTypes";
import { copyName, mapUrl } from "./pickerRows";

export { copyName };

/** Copy his old file `name` (opened by `scope`) as my-map; false when it was refused (the map store's `error` says why). */
export async function copyOld(name: string, scope: string): Promise<boolean> {
  try {
    if (!maps.get().listed) await loadMaps();
    const detail = await api.get<MapDetail>(mapUrl(name, scope));
    const as = copyName(maps.get().rows.map((r) => r.name));
    await api.put<MapDetail>(`crew/map/${as}`, { map: { ...detail.map, name: as } });
    await loadMaps();
    goSection("agents", "map");
    await openMap(as);
    return true;
  } catch (e) {
    maps.update(() => ({ error: msg(e) }));
    return false;
  }
}
