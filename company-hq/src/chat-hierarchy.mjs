/** Arrange real HQ conversations by their explicit reviewing chat. */
export function chatHierarchy(teams, profiles = {}, deleted = []) {
  const visible = teams.filter(team => !deleted.includes(team.name));
  const byName = new Map(visible.map(team => [team.name, team]));
  const children = new Map();
  for (const team of visible) {
    const profile = profiles[team.name] || {};
    const parent = profile.supervisedBy;
    if (!byName.has(parent) || parent === team.name || !profile.projectRoot ||
        profiles[parent]?.projectRoot !== profile.projectRoot) continue;
    children.set(parent, [...(children.get(parent) || []), team.name]);
  }
  const originalOrder = new Map(visible.map((team, index) => [team.name, index]));
  const recent = new Map();
  function latestInGroup(name, ancestors = new Set()) {
    if (recent.has(name)) return recent.get(name);
    if (ancestors.has(name)) return 0;
    const next = new Set(ancestors).add(name);
    const own = Number(byName.get(name)?.lastActivityAt) || 0;
    const latest = Math.max(own, ...(children.get(name) || []).map(child => latestInGroup(child, next)));
    recent.set(name, latest);
    return latest;
  }
  const newestFirst = (a, b) => latestInGroup(b.name) - latestInGroup(a.name) ||
    originalOrder.get(a.name) - originalOrder.get(b.name);
  const output = [], visited = new Set();
  function visit(team, depth = 0) {
    if (visited.has(team.name)) return;
    visited.add(team.name);
    output.push({team, depth});
    for (const child of (children.get(team.name) || []).map(name => byName.get(name)).sort(newestFirst)) visit(child, depth + 1);
  }
  for (const team of [...visible].sort(newestFirst)) {
    const parent = profiles[team.name]?.supervisedBy;
    if (!parent || !children.get(parent)?.includes(team.name)) visit(team);
  }
  for (const team of [...visible].sort(newestFirst)) visit(team);
  return output;
}

/** The conversations visible below one supervisor, including nested specialists. */
export function chatDescendants(teams, profiles, parent, deleted = []) {
  const ordered = chatHierarchy(teams, profiles, deleted);
  const visible = new Set(ordered.map(({team}) => team.name));
  const root = profiles[parent]?.projectRoot;
  return ordered.filter(({team}) => {
    if (!root || profiles[team.name]?.projectRoot !== root) return false;
    const seen = new Set([team.name]);
    let current = team.name;
    while (profiles[current]?.supervisedBy) {
      current = profiles[current].supervisedBy;
      if (current === parent) return true;
      if (!visible.has(current) || seen.has(current)) return false;
      seen.add(current);
    }
    return false;
  }).map(({team}) => team);
}
