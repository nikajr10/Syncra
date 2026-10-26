import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { token } from '@/api/client'
import { api } from '@/api/endpoints'
import type { Me } from '@/api/types'
import { go } from './useHash'

/** The signed-in user; null when signed out or the saved token is rejected. */
export function useMe() {
  return useQuery<Me | null>({
    queryKey: ['me'],
    queryFn: () => (token.get() ? api.me() : null),
    staleTime: Infinity,
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) => {
      token.set((await api.login(username, password)).token)
      return api.me()
    },
    onSuccess: me => qc.setQueryData(['me'], me),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.logout().catch(() => null), // signed out locally even if the API is down
    onSettled: () => {
      token.set(null)
      qc.clear()
      qc.setQueryData(['me'], null)
      go('/')
    },
  })
}
