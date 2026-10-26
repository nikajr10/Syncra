import { QueryClient } from '@tanstack/react-query'
import { setOnUnauthorized, token } from '@/api/client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
})

// A token the API no longer accepts: forget it and everything loaded with it; App shows the login.
setOnUnauthorized(() => {
  token.set(null)
  queryClient.removeQueries({ predicate: q => q.queryKey[0] !== 'me' })
  queryClient.setQueryData(['me'], null)
})
