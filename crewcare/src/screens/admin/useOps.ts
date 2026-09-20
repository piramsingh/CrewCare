import { useCallback, useEffect, useState } from 'react'

import { fetchSnapshot, OpsError, type OpsSnapshot } from '../../api/ops'

export type Load<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string }

/**
 * Loads the operations snapshot for a time range.
 *
 * One request per range change and nothing else — the models score the whole
 * network in a single call and the server caches the upstream fetch, so
 * re-requesting per panel would only burn the Open-Meteo budget.
 */
export function useOps(range: string) {
  const [state, setState] = useState<Load<OpsSnapshot>>({ status: 'loading' })

  const reload = useCallback(() => {
    let cancelled = false
    setState({ status: 'loading' })
    fetchSnapshot(range)
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((error) => {
        if (cancelled) return
        setState({
          status: 'error',
          message: error instanceof OpsError ? error.message : 'Something went wrong.',
        })
      })
    return () => {
      cancelled = true
    }
  }, [range])

  useEffect(() => reload(), [reload])

  return { state, reload }
}
