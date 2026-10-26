import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { SourceView, Tool } from '@/api/types'

type Sources = Awaited<ReturnType<typeof api.sources>>

/** Sources and tool credentials. Polled so a sync in progress shows up without a refresh. */
export function useSources() {
  return useQuery({ queryKey: ['sources'], queryFn: api.sources, refetchInterval: 10_000 })
}

function useReplaceSource() {
  const qc = useQueryClient()
  return (view: SourceView) =>
    qc.setQueryData<Sources>(['sources'], d => d && { ...d, sources: d.sources.map(x => (x.id === view.id ? view : x)) })
}

export function useAddSource() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, externalId, name }: { kind: Tool; externalId: string; name: string }) => api.addSource(kind, externalId, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sources'] }),
  })
}

/** Pause or resume a source; the switch flips at once and flips back if the API refuses. */
export function useToggleSource() {
  const replace = useReplaceSource()
  return useMutation({
    mutationFn: ({ source, enabled }: { source: SourceView; enabled: boolean }) => api.setSource(source.id, enabled),
    onMutate: ({ source, enabled }) => replace({ ...source, enabled }),
    onError: (_err, { source }) => replace(source),
    onSuccess: replace,
  })
}

export function useSyncSource() {
  const replace = useReplaceSource()
  return useMutation({ mutationFn: (id: number) => api.syncSource(id), onSuccess: replace })
}

export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: api.users })
}

export function useLinkAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ username, tool, accountId, displayName }: { username: string; tool: Tool; accountId: string; displayName: string }) =>
      api.linkAccount(username, tool, accountId, displayName),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}

/** Item counts, sources and recent problems, every 30 s. */
export function useStatus() {
  return useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 30_000 })
}
