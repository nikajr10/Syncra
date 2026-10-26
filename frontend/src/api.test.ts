// npm test (Node strips the types)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { takeEvents } from './api.ts'

test('events split across network chunks come out whole and in order', () => {
  const stream = 'event: token\ndata: {"text": "Alice"}\n\nevent: token\ndata: {"text": " built [E1] ü"}\n\nevent: done\ndata: {"path": "question"}\n\n'
  for (const size of [1, 3, 7, 50, stream.length]) {
    let buffer = ''
    const seen: unknown[] = []
    for (let i = 0; i < stream.length; i += size) {
      const { events, rest } = takeEvents(buffer + stream.slice(i, i + size))
      buffer = rest
      seen.push(...events.map(e => [e.event, e.data]))
    }
    assert.deepEqual(seen, [['token', { text: 'Alice' }], ['token', { text: ' built [E1] ü' }], ['done', { path: 'question' }]])
    assert.equal(buffer, '')
  }
})
