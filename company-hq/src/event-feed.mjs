/** Keep streaming text as one item so token chunks cannot evict whole messages. */
export function mergeRuntimeEvents(previous, incoming, limit = 500) {
  const result = previous.map(event => ({...event, data: {...event.data}}));
  const seen = new Set(result.map(event => event.seq));
  const streams = new Map();
  const key = event => `${event.threadId || ''}:${event.itemId || event.turnId || event.seq}`;
  result.forEach((event, index) => {
    if (event.type === 'message.delta' || event.type === 'message.completed') streams.set(key(event), index);
  });
  for (const event of incoming) {
    if (seen.has(event.seq)) continue;
    seen.add(event.seq);
    if (event.type === 'message.delta' || event.type === 'message.completed') {
      const itemKey = key(event), index = streams.get(itemKey);
      if (index !== undefined) {
        const old = result[index];
        if (event.seq <= old.seq || old.type === 'message.completed') continue;
        result[index] = event.type === 'message.completed' ? event : {
          ...event, data: {...event.data, text: ((old.data?.text || '') + (event.data?.text || '')).slice(-4 * 1024 * 1024)},
        };
        continue;
      }
      streams.set(itemKey, result.length);
    }
    result.push(event);
  }
  return result.slice(-limit);
}
