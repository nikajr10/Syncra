import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/endpoints'
import type { Card } from '@/api/types'

/** The user's approval cards, newest first. Polled so a card approved elsewhere updates here. */
export function useActions() {
  return useQuery({ queryKey: ['actions'], queryFn: api.actions, refetchInterval: 30_000 })
}

/** Approve or reject a pending card; the returned card replaces it in the list. */
export function useDecideAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: 'approve' | 'reject' }) => api[decision](id),
    onSuccess: card => qc.setQueryData<Card[]>(['actions'], list => list?.map(a => (a.id === card.id ? card : a))),
  })
}
