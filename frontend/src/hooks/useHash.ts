import { useEffect, useState } from 'react'

/** The part of the URL after `#`, so a reload or a shared link opens the same screen. */
export function useHash(): string {
  const [hash, setHash] = useState(() => location.hash.slice(1) || '/')
  useEffect(() => {
    const update = () => setHash(location.hash.slice(1) || '/')
    addEventListener('hashchange', update)
    return () => removeEventListener('hashchange', update)
  }, [])
  return hash
}
export const go = (path: string) => { location.hash = path }
